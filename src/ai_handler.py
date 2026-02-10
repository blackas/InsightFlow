"""AI processing module - keyword filtering and Gemini batch summarization."""

import json
import logging
import time

import google.generativeai as genai

from src import config
from src.scraper import Article

logger = logging.getLogger(__name__)


def keyword_filter(articles: list[Article]) -> list[Article]:
    """Filter articles containing any config.KEYWORDS in title or summary (case-insensitive)."""
    keywords_lower = [kw.lower() for kw in config.KEYWORDS]
    filtered: list[Article] = []

    for article in articles:
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
        for idx, article in enumerate(batch, 1):
            articles_text += (
                f"[{idx}] 제목: {article.title}\n    요약: {article.summary}\n"
            )

        prompt = (
            f"다음 기술 기사들을 분석해주세요. 각 기사에 대해:\n"
            f"1. 개발자 관련성 점수 (0.0~1.0)\n"
            f"2. 한국어로 3줄 핵심 요약\n\n"
            f"기사 목록:\n{articles_text}\n"
            f"JSON 형식으로 응답해주세요:\n"
            f'[{{"index": 1, "relevance": 0.85, "summary": "..."}}, ...]'
        )

        response_data = None
        backoff_times = [5, 15, 45]

        for attempt in range(4):
            try:
                response = model.generate_content(prompt)
                response_text = response.text

                # Parse JSON response
                response_data = json.loads(response_text)
                break

            except json.JSONDecodeError:
                logger.warning(
                    "Batch %d: Failed to parse JSON response (attempt %d)",
                    i // batch_size + 1,
                    attempt + 1,
                )
                # Try to extract JSON from response text
                if response_text:  # type: ignore[possibly-undefined]
                    try:
                        # Handle cases where JSON is wrapped in markdown
                        cleaned = response_text.strip()  # type: ignore[possibly-undefined]
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

        # Apply results to articles
        if response_data and isinstance(response_data, list):
            for item in response_data:
                idx = item.get("index", 0) - 1  # 1-based to 0-based
                if 0 <= idx < len(batch):
                    batch[idx].ai_summary = item.get("summary", "")
                    batch[idx].relevance_score = float(item.get("relevance", 0.0))
        else:
            logger.warning(
                "Batch %d: No valid response, keeping original articles",
                i // batch_size + 1,
            )

        # Rate limit delay between batches (skip after last batch)
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
