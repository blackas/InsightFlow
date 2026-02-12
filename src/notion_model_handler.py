from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, cast

import notion_client

from src import config
from src.notion_common import get_client, resolve_data_source_id

logger = logging.getLogger(__name__)

_MODEL_TRACKER_PROPERTIES: dict[str, Any] = {
    "제목": {"type": "title", "title": {}},
    "유형": {
        "type": "select",
        "select": {
            "options": [
                {"name": "신규 모델", "color": "green"},
                {"name": "순위 변동", "color": "blue"},
                {"name": "가격 변동", "color": "orange"},
            ]
        },
    },
    "모델명": {"type": "rich_text", "rich_text": {}},
    "세부 내용": {"type": "rich_text", "rich_text": {}},
    "날짜": {"type": "date", "date": {}},
}


def ensure_model_tracker_db(client: notion_client.Client) -> str:
    """Find or create the persistent 'AI Model Tracker' database.

    Returns:
        The data_source_id for the database.
    """
    if config.NOTION_MODEL_TRACKER_DB_ID:
        logger.info(
            "Using existing Model Tracker database: %s",
            config.NOTION_MODEL_TRACKER_DB_ID,
        )
        return resolve_data_source_id(client, config.NOTION_MODEL_TRACKER_DB_ID)

    db_title = "AI Model Tracker"

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
            data_source_id: str = result["id"]
            logger.info(
                "Reusing Model Tracker database '%s': %s", db_title, data_source_id
            )
            return data_source_id

    logger.info(
        "Creating Model Tracker database '%s' under page %s",
        db_title,
        config.NOTION_PARENT_PAGE_ID,
    )
    data = cast(
        dict[str, Any],
        client.databases.create(
            parent={"type": "page_id", "page_id": config.NOTION_PARENT_PAGE_ID},
            title=[{"type": "text", "text": {"content": db_title}}],
            initial_data_source={"properties": _MODEL_TRACKER_PROPERTIES},
        ),
    )
    data_source_id = data["data_sources"][0]["id"]
    logger.info("Created Model Tracker database '%s': %s", db_title, data_source_id)
    return data_source_id


def _build_model_page(
    data_source_id: str,
    change_type: str,
    title_text: str,
    model_name: str,
    detail_text: str,
) -> dict[str, Any]:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "parent": {"type": "data_source_id", "data_source_id": data_source_id},
        "properties": {
            "제목": {"title": [{"text": {"content": title_text}}]},
            "유형": {"select": {"name": change_type}},
            "모델명": {"rich_text": [{"text": {"content": model_name}}]},
            "세부 내용": {"rich_text": [{"text": {"content": detail_text}}]},
            "날짜": {"date": {"start": today}},
        },
    }


def send_model_updates_to_notion(
    model_updates: dict[str, list[dict[str, Any]]] | None,
) -> int:
    """Write model change entries to the AI Model Tracker Notion database.

    Args:
        model_updates: Dict with keys new_models, rank_changes, price_changes.

    Returns:
        Number of pages created.
    """
    if not config.NOTION_API_KEY:
        logger.warning("NOTION_API_KEY not set, skipping Model Tracker Notion sync")
        return 0

    if config.DRY_RUN:
        logger.info("[DRY RUN] Skipping Model Tracker Notion sync")
        return 0

    if model_updates is None:
        return 0

    new_models = model_updates.get("new_models", [])
    rank_changes = model_updates.get("rank_changes", [])
    price_changes = model_updates.get("price_changes", [])

    if not new_models and not rank_changes and not price_changes:
        return 0

    try:
        client = get_client()
        data_source_id = ensure_model_tracker_db(client)
        created_count = 0

        for model in new_models:
            name = model.get("name", "Unknown")
            creator = model.get("creator", "Unknown")
            intelligence_index = model.get("intelligence_index", 0)
            page_payload = _build_model_page(
                data_source_id=data_source_id,
                change_type="신규 모델",
                title_text=f"🆕 {name} by {creator}",
                model_name=name,
                detail_text=f"Intelligence: {intelligence_index}",
            )
            client.pages.create(**page_payload)
            logger.info("Created Model Tracker page: new model %s", name)
            created_count += 1

        for change in rank_changes:
            name = change.get("name", "Unknown")
            old_rank = change.get("old_rank", "?")
            new_rank = change.get("new_rank", "?")
            intelligence_index = change.get("intelligence_index", 0)
            page_payload = _build_model_page(
                data_source_id=data_source_id,
                change_type="순위 변동",
                title_text=f"📈 {name}: #{old_rank} → #{new_rank}",
                model_name=name,
                detail_text=f"Intelligence: {intelligence_index}",
            )
            client.pages.create(**page_payload)
            logger.info("Created Model Tracker page: rank change %s", name)
            created_count += 1

        for change in price_changes:
            name = change.get("name", "Unknown")
            old_price = change.get("old_price", 0)
            new_price = change.get("new_price", 0)
            change_percent = change.get("change_percent", 0)
            page_payload = _build_model_page(
                data_source_id=data_source_id,
                change_type="가격 변동",
                title_text=f"💰 {name}: ${old_price:.4f} → ${new_price:.4f}",
                model_name=name,
                detail_text=f"{change_percent:+.1%} change",
            )
            client.pages.create(**page_payload)
            logger.info("Created Model Tracker page: price change %s", name)
            created_count += 1

        logger.info("Created %d Model Tracker pages total", created_count)
        return created_count

    except Exception:
        logger.exception("Model tracker Notion sync failed")
        return 0
