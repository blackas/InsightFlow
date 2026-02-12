"""AI processing module - keyword filtering and Gemini batch summarization."""

import json
import logging
import time

import google.generativeai as genai

from src import config
from src.scraper import Article

logger = logging.getLogger(__name__)


def keyword_filter(articles: list[Article]) -> list[Article]:
    """Filter articles by keywords. HN and TLDR AI articles bypass keyword filter (already curated)."""
    keywords_lower = [kw.lower() for kw in config.KEYWORDS]
    filtered: list[Article] = []

    for article in articles:
        if article.source in ("hackernews", "tldrai"):
            filtered.append(article)
            continue
        text = f"{article.title} {article.summary}".lower()
        if any(kw in text for kw in keywords_lower):
            filtered.append(article)

    logger.info("Keyword filter: %d -> %d articles", len(articles), len(filtered))
    return filtered


def batch_summarize(articles: list[Article]) -> list[Article]:
    """Call Gemini in BATCH_SIZE groups for relevance scores + Korean summaries.

    Retries 429 errors with exponential backoff (5s, 15s, 45s).
    On failure, returns articles unchanged (graceful degradation).
    """
    if not articles:
        return articles

    if not config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, skipping AI summarization")
        return articles

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
    except Exception:
        logger.exception("Failed to initialize Gemini model")
        return articles

    batch_size = config.BATCH_SIZE

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]

        articles_text = ""
        has_tldrai = False
        for idx, article in enumerate(batch, 1):
            articles_text += (
                f"[{idx}] 제목: {article.title}\n    요약: {article.summary}\n"
            )
            if article.source == "tldrai":
                has_tldrai = True

        tags_list = ", ".join(config.NOTION_TAGS)

        # Adjust prompt for TLDR AI articles (already curated, extract key points from existing summary)
        if has_tldrai:
            prompt = (
                f"다음 기술 기사들을 분석해주세요. 각 기사에 대해:\n"
                f"1. 개발자 관련성 점수 (0.0~1.0)\n"
                f"2. 한국어로 2-3개 핵심 포인트 추출 (TLDR AI 뉴스레터에서 이미 요약된 내용이므로 기존 요약에서 핵심만 추출)\n"
                f"3. 태그 분류 (다음 목록에서 최대 3개 태그 선택: {tags_list})\n\n"
                f"기사 목록:\n{articles_text}\n"
                f"JSON 형식으로 응답해주세요:\n"
                f'[{{"index": 1, "relevance": 0.85, "summary": "...", "tags": ["AI/ML", "Tool"]}}, ...]'
            )
        else:
            prompt = (
                f"다음 기술 기사들을 분석해주세요. 각 기사에 대해:\n"
                f"1. 개발자 관련성 점수 (0.0~1.0)\n"
                f"2. 한국어로 3줄 핵심 요약\n"
                f"3. 태그 분류 (다음 목록에서 최대 3개 태그 선택: {tags_list})\n\n"
                f"기사 목록:\n{articles_text}\n"
                f"JSON 형식으로 응답해주세요:\n"
                f'[{{"index": 1, "relevance": 0.85, "summary": "...", "tags": ["AI/ML", "Tool"]}}, ...]'
            )

        response_data = None
        response_text = ""
        backoff_times = [5, 15, 45]

        for attempt in range(4):
            try:
                response = model.generate_content(prompt)
                response_text = response.text

                response_data = json.loads(response_text)
                break

            except json.JSONDecodeError:
                logger.warning(
                    "Batch %d: Failed to parse JSON response (attempt %d)",
                    i // batch_size + 1,
                    attempt + 1,
                )
                # Gemini sometimes wraps JSON in markdown code blocks
                if response_text:
                    try:
                        cleaned = response_text.strip()
                        if cleaned.startswith("```"):
                            cleaned = cleaned.split("\n", 1)[1]
                            cleaned = cleaned.rsplit("```", 1)[0]
                        response_data = json.loads(cleaned)
                        break
                    except (json.JSONDecodeError, IndexError):
                        pass
                if attempt < 3:
                    time.sleep(backoff_times[min(attempt, 2)])

            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "quota" in error_str.lower()

                if is_rate_limit and attempt < 3:
                    wait = backoff_times[min(attempt, 2)]
                    logger.warning(
                        "Batch %d: Rate limited, retrying in %ds (attempt %d/3)",
                        i // batch_size + 1,
                        wait,
                        attempt + 1,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Batch %d: Gemini call failed (attempt %d): %s",
                        i // batch_size + 1,
                        attempt + 1,
                        e,
                    )
                    break

        if response_data and isinstance(response_data, list):
            valid_tags = set(config.NOTION_TAGS)
            for item in response_data:
                idx = item.get("index", 0) - 1
                if 0 <= idx < len(batch):
                    batch[idx].ai_summary = item.get("summary", "")
                    batch[idx].relevance_score = float(item.get("relevance", 0.0))
                    raw_tags = item.get("tags", [])
                    if isinstance(raw_tags, list):
                        filtered = [t for t in raw_tags if t in valid_tags][:3]
                        batch[idx].tags = filtered if filtered else ["Other"]
                    else:
                        batch[idx].tags = ["Other"]
        else:
            logger.warning(
                "Batch %d: No valid response, keeping original articles",
                i // batch_size + 1,
            )

        if i + batch_size < len(articles):
            time.sleep(2)

    return articles


def filter_and_summarize(articles: list[Article]) -> list[Article]:
    """Pipeline: keyword_filter -> batch_summarize -> relevance threshold -> notable flag."""
    filtered = keyword_filter(articles)
    if not filtered:
        logger.info("No articles passed keyword filter")
        return []

    summarized = batch_summarize(filtered)

    result: list[Article] = []
    for article in summarized:
        if article.relevance_score >= config.RELEVANCE_THRESHOLD:
            if article.relevance_score >= config.ISSUE_THRESHOLD:
                article.notable = True
            result.append(article)

    logger.info(
        "Filter pipeline: %d input -> %d keyword -> %d final (%d notable)",
        len(articles),
        len(filtered),
        len(result),
        sum(1 for a in result if a.notable),
    )
    return result
