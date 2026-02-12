#!/usr/bin/env python3
"""
One-time migration script to backfill Notion database with GitHub Issues.

This script reads all GitHub Issues and saves them to the existing Notion database.
It parses issue body to extract article data and creates Notion pages for each.

Usage:
    uv run python backfill_notion.py
"""

import json
import logging
import re
import subprocess
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from src.notion_common import get_client
from src.notion_handler import ensure_database
from src.scraper import Article

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _extract_source_id(discussion_url: str, source: str) -> str:
    """Extract source_id from discussion URL.

    For geeknews: Extract topic ID from URL path (last part)
    For hackernews: Extract item ID from ?id= parameter
    """
    if source == "geeknews":
        # URL format: https://geeknews.geeknews.com/x/12345
        match = re.search(r"/(\d+)/?$", discussion_url)
        if match:
            return match.group(1)
        return discussion_url
    elif source == "hackernews":
        # URL format: https://news.ycombinator.com/item?id=46911581
        match = re.search(r"[?&]id=(\d+)", discussion_url)
        if match:
            return match.group(1)
        return discussion_url
    return discussion_url


def _parse_issue_body(body: str) -> dict[str, Any]:
    """Parse GitHub issue body to extract article data.

    Expected format:
    ## 기사 정보
    - **원본 URL**: https://...
    - **토론**: https://...
    - **소스**: geeknews
    - **관련성 점수**: 0.85

    ## AI 요약
    Line 1
    Line 2
    Line 3
    """
    data: dict[str, Any] = {
        "url": "",
        "discussion_url": "",
        "source": "",
        "relevance_score": 0.0,
        "ai_summary": "",
    }

    # Extract URL
    url_match = re.search(r"\*\*원본 URL\*\*:\s*(\S+)", body)
    if url_match:
        data["url"] = url_match.group(1)

    # Extract discussion URL
    discussion_match = re.search(r"\*\*토론\*\*:\s*(\S+)", body)
    if discussion_match:
        data["discussion_url"] = discussion_match.group(1)

    # Extract source
    source_match = re.search(r"\*\*소스\*\*:\s*(\w+)", body)
    if source_match:
        data["source"] = source_match.group(1)

    # Extract relevance score
    score_match = re.search(r"\*\*관련성 점수\*\*:\s*([\d.]+)", body)
    if score_match:
        data["relevance_score"] = float(score_match.group(1))

    # Extract AI summary (everything after "## AI 요약")
    summary_match = re.search(r"## AI 요약\n(.*?)(?:\n##|$)", body, re.DOTALL)
    if summary_match:
        summary_text = summary_match.group(1).strip()
        # Clean up the summary (remove extra whitespace, keep line breaks)
        data["ai_summary"] = "\n".join(
            line.strip() for line in summary_text.split("\n") if line.strip()
        )

    return data


def _extract_title_and_source(issue_title: str) -> tuple[str, str]:
    """Extract source and title from issue title.

    Format: [source] Article Title
    Example: [geeknews] WebMCP 공개
    """
    match = re.match(r"\[(\w+)\]\s+(.*)", issue_title)
    if match:
        return match.group(2), match.group(1)
    return issue_title, "unknown"


def _fetch_github_issues() -> list[dict[str, Any]]:
    """Fetch all GitHub issues using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--json", "title,body,createdAt", "--limit", "100"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Failed to fetch GitHub issues: %s", e.stderr)
        return []
    except json.JSONDecodeError as e:
        logger.error("Failed to parse GitHub issues JSON: %s", e)
        return []


def _convert_iso_to_date(iso_string: str) -> str:
    """Convert ISO 8601 timestamp to YYYY-MM-DD format."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        logger.warning("Failed to parse date: %s", iso_string)
        return datetime.now().strftime("%Y-%m-%d")


def backfill_notion() -> None:
    """Main backfill function."""
    logger.info("Starting Notion backfill from GitHub Issues...")

    # Fetch all GitHub issues
    issues = _fetch_github_issues()
    if not issues:
        logger.warning("No GitHub issues found")
        return

    logger.info("Found %d GitHub issues", len(issues))

    # Initialize Notion client — get/create weekly database
    client = get_client()
    data_source_id = ensure_database(client)
    logger.info("Using Notion database with data_source_id: %s", data_source_id)

    created_count = 0
    skipped_count = 0

    for issue in issues:
        try:
            # Extract title and source from issue title
            title, source = _extract_title_and_source(issue["title"])

            # Parse issue body
            parsed = _parse_issue_body(issue["body"])

            # Validate required fields
            if (
                not parsed["url"]
                or not parsed["discussion_url"]
                or not parsed["source"]
            ):
                logger.warning("Skipping issue with missing fields: %s", issue["title"])
                skipped_count += 1
                continue

            # Extract source_id from discussion URL
            source_id = _extract_source_id(parsed["discussion_url"], parsed["source"])

            # Convert createdAt to date format
            published_at = _convert_iso_to_date(issue["createdAt"])

            # Create Article object
            article = Article(
                source=parsed["source"],
                source_id=source_id,
                title=title,
                url=parsed["url"],
                discussion_url=parsed["discussion_url"],
                summary="",
                score=0,
                published_at=published_at,
                ai_summary=parsed["ai_summary"],
                relevance_score=parsed["relevance_score"],
                tags=["Other"],
            )

            # Create Notion page
            page_payload = {
                "parent": {"type": "data_source_id", "data_source_id": data_source_id},
                "properties": {
                    "제목": {
                        "title": [
                            {
                                "text": {
                                    "content": f"{article.source}:{article.source_id} {article.title}"
                                }
                            }
                        ]
                    },
                    "소스": {"select": {"name": article.source}},
                    "관련성": {"number": article.relevance_score},
                    "AI 요약": {
                        "rich_text": [
                            {"text": {"content": (article.ai_summary or "")[:2000]}}
                        ]
                    },
                    "원문 URL": {"url": article.url},
                    "토론 URL": {"url": article.discussion_url},
                    "날짜": {"date": {"start": article.published_at}},
                    "읽음": {"checkbox": False},
                    "태그": {"multi_select": [{"name": tag} for tag in article.tags]},
                },
            }
            client.pages.create(**page_payload)

            logger.info(
                "Created Notion page: [%s] %s (relevance: %.2f)",
                article.source,
                article.title,
                article.relevance_score,
            )
            created_count += 1

        except Exception as e:
            logger.error("Failed to process issue %s: %s", issue["title"], e)
            skipped_count += 1
            continue

    logger.info(
        "Backfill complete: %d created, %d skipped, %d total",
        created_count,
        skipped_count,
        len(issues),
    )


if __name__ == "__main__":
    backfill_notion()
