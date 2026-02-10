"""Article persistence, deduplication, and GitHub Issues creation."""

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

import requests

from src import config
from src.scraper import Article

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
SEEN_IDS_PATH = DATA_DIR / "seen_ids.json"
MAX_ISSUES_PER_RUN = 5


def load_seen_ids() -> set[str]:
    """Load seen IDs from data/seen_ids.json. Returns empty set if missing."""
    if not SEEN_IDS_PATH.exists():
        return set()

    try:
        with open(SEEN_IDS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    except (json.JSONDecodeError, OSError):
        logger.exception("Failed to load seen_ids.json, starting fresh")
        return set()


def save_seen_ids(seen_ids: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(SEEN_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen_ids), f, indent=2, ensure_ascii=False)

    logger.info("Saved %d seen IDs", len(seen_ids))


def filter_new_articles(articles: list[Article], seen_ids: set[str]) -> list[Article]:
    """SIDE EFFECT: adds new article IDs to seen_ids."""
    new_articles: list[Article] = []

    for article in articles:
        article_id = f"{article.source}:{article.source_id}"
        if article_id not in seen_ids:
            seen_ids.add(article_id)
            new_articles.append(article)

    logger.info(
        "Filtered articles: %d new out of %d total",
        len(new_articles),
        len(articles),
    )
    return new_articles


def save_daily_articles(articles: list[Article], date_str: str) -> Path:
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")

    year, month, day = parts
    dir_path = DATA_DIR / year / month
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"{day}.json"

    existing: list[dict] = []
    if file_path.exists():
        try:
            with open(file_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read existing %s, overwriting", file_path)

    new_data = [asdict(article) for article in articles]
    combined = existing + new_data

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    logger.info(
        "Saved %d articles to %s (total: %d)", len(articles), file_path, len(combined)
    )
    return file_path


def create_github_issues(articles: list[Article]) -> int:
    """Create GitHub Issues for high-relevance articles.

    Only articles with relevance_score >= ISSUE_THRESHOLD are posted.
    Maximum MAX_ISSUES_PER_RUN issues created per run.
    Skipped in dry-run mode.

    Args:
        articles: Articles to potentially create issues for.

    Returns:
        Number of issues created.
    """
    if config.DRY_RUN:
        logger.info("[DRY RUN] Skipping GitHub Issues creation")
        return 0

    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repo:
        logger.warning(
            "GITHUB_TOKEN or GITHUB_REPOSITORY not set, skipping Issues creation"
        )
        return 0

    # Filter by relevance threshold
    notable = [a for a in articles if a.relevance_score >= config.ISSUE_THRESHOLD]
    if not notable:
        logger.info("No articles above issue threshold (%.1f)", config.ISSUE_THRESHOLD)
        return 0

    # Cap at max issues per run
    notable = notable[:MAX_ISSUES_PER_RUN]

    api_url = f"https://api.github.com/repos/{github_repo}/issues"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    created_count = 0

    for article in notable:
        title = f"[{article.source}] {article.title}"
        body = (
            f"## 기사 정보\n"
            f"- **원본 URL**: {article.url}\n"
            f"- **토론**: {article.discussion_url}\n"
            f"- **소스**: {article.source}\n"
            f"- **관련성 점수**: {article.relevance_score}\n"
            f"\n"
            f"## AI 요약\n"
            f"{article.ai_summary}\n"
        )
        labels = [f"source:{article.source}", "auto-collected"]

        payload = {"title": title, "body": body, "labels": labels}

        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            issue_number = resp.json().get("number", "?")
            logger.info("Created issue #%s: %s", issue_number, title)
            created_count += 1
        except requests.RequestException:
            logger.exception("Failed to create issue: %s", title)

    logger.info("Created %d/%d GitHub Issues", created_count, len(notable))
    return created_count
