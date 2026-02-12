from __future__ import annotations

import logging
from typing import Any, cast

import notion_client

from src import config
from src.notion_common import get_client, resolve_data_source_id
from src.scraper import Article

logger = logging.getLogger(__name__)

MAX_NOTION_PER_RUN = 5

_DATABASE_PROPERTIES: dict[str, Any] = {
    "제목": {"type": "title", "title": {}},
    "소스": {
        "type": "select",
        "select": {
            "options": [
                {"name": "geeknews", "color": "green"},
                {"name": "hackernews", "color": "orange"},
                {"name": "tldrai", "color": "blue"},
            ]
        },
    },
    "관련성": {"type": "number", "number": {"format": "percent"}},
    "AI 요약": {"type": "rich_text", "rich_text": {}},
    "원문 URL": {"type": "url", "url": {}},
    "토론 URL": {"type": "url", "url": {}},
    "날짜": {"type": "date", "date": {}},
    "읽음": {"type": "checkbox", "checkbox": {}},
    "태그": {
        "type": "multi_select",
        "multi_select": {
            "options": [{"name": tag} for tag in config.NOTION_TAGS],
        },
    },
}


def ensure_database(client: notion_client.Client) -> str:
    # Backward-compatible: use explicit DB ID if set
    if config.NOTION_DATABASE_ID:
        logger.info("Using existing Notion database: %s", config.NOTION_DATABASE_ID)
        return resolve_data_source_id(client, config.NOTION_DATABASE_ID)

    week_id = config.get_week_identifier()  # e.g. "2026-W07"
    db_title = f"{week_id} Articles"

    # 1. Search for existing weekly DB
    results = cast(
        dict[str, Any],
        client.search(
            query=db_title,
            filter={"value": "data_source", "property": "object"},
        ),
    )
    for result in results.get("results", []):
        title_parts = result.get("title", [])
        if title_parts and title_parts[0].get("plain_text") == db_title:
            ds_id = result["id"]  # search result id is the data_source_id
            logger.info("Reusing weekly database '%s': %s", db_title, ds_id)
            return ds_id

    # 2. Create new weekly DB (uses initial_data_source to work around SDK pick() bug)
    logger.info(
        "Creating weekly database '%s' under page %s",
        db_title,
        config.NOTION_PARENT_PAGE_ID,
    )
    data = cast(
        dict[str, Any],
        client.databases.create(
            parent={"type": "page_id", "page_id": config.NOTION_PARENT_PAGE_ID},
            title=[{"type": "text", "text": {"content": db_title}}],
            initial_data_source={"properties": _DATABASE_PROPERTIES},
        ),
    )
    ds_id = data["data_sources"][0]["id"]
    logger.info("Created weekly database '%s': %s", db_title, ds_id)
    return ds_id


def _is_duplicate(
    client: notion_client.Client,
    data_source_id: str,
    source: str,
    source_id: str,
) -> bool:
    response = cast(
        dict[str, Any],
        client.data_sources.query(
            data_source_id=data_source_id,
            filter={"property": "제목", "title": {"contains": f"{source}:{source_id}"}},
        ),
    )
    return len(response.get("results", [])) > 0


def _build_page_properties(
    article: Article,
    data_source_id: str,
) -> dict[str, Any]:
    return {
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
                "rich_text": [{"text": {"content": (article.ai_summary or "")[:2000]}}]
            },
            "원문 URL": {"url": article.url},
            "토론 URL": {"url": article.discussion_url},
            "날짜": {"date": {"start": article.published_at}},
            "읽음": {"checkbox": False},
            "태그": {"multi_select": [{"name": tag} for tag in article.tags]},
        },
    }


def send_to_notion(articles: list[Article]) -> int:
    if not config.NOTION_API_KEY:
        logger.warning("NOTION_API_KEY not set, skipping Notion sync")
        return 0

    if config.DRY_RUN:
        logger.info("[DRY RUN] Skipping Notion sync")
        return 0

    try:
        client = get_client()
        data_source_id = ensure_database(client)

        notable = [a for a in articles if a.relevance_score >= config.ISSUE_THRESHOLD]
        if not notable:
            logger.info(
                "No articles above issue threshold (%.1f)", config.ISSUE_THRESHOLD
            )
            return 0

        notable = notable[:MAX_NOTION_PER_RUN]
        created_count = 0

        for article in notable:
            if _is_duplicate(client, data_source_id, article.source, article.source_id):
                logger.info(
                    "Skipping duplicate: %s:%s", article.source, article.source_id
                )
                continue

            page_payload = _build_page_properties(article, data_source_id)
            client.pages.create(**page_payload)
            logger.info("Created Notion page: [%s] %s", article.source, article.title)
            created_count += 1

        logger.info("Created %d/%d Notion pages", created_count, len(notable))
        return created_count

    except Exception:
        logger.exception("Notion sync failed")
        return 0
