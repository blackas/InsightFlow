from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, cast

import notion_client

from src import config
from src.notion_common import get_client, resolve_data_source_id

logger = logging.getLogger(__name__)

_DASHBOARD_PROPERTIES: dict[str, Any] = {
    "모델명": {"type": "title", "title": {}},
    "모델 ID": {"type": "rich_text", "rich_text": {}},
    "제작사": {
        "type": "select",
        "select": {"options": []},
    },
    "종합 지능": {"type": "number", "number": {"format": "number"}},
    "코딩 지수": {"type": "number", "number": {"format": "number"}},
    "수학 지수": {"type": "number", "number": {"format": "number"}},
    "속도 지수": {"type": "number", "number": {"format": "number"}},
    "입력 가격": {"type": "number", "number": {"format": "number"}},
    "출력 가격": {"type": "number", "number": {"format": "number"}},
    "처리 속도": {"type": "number", "number": {"format": "number"}},
    "TTFT": {"type": "number", "number": {"format": "number"}},
    "순위": {"type": "number", "number": {"format": "number"}},
    "마지막 업데이트": {"type": "date", "date": {}},
}


def ensure_model_dashboard_db(client: notion_client.Client) -> str:
    if config.NOTION_MODEL_DASHBOARD_DB_ID:
        logger.info(
            "Using existing Model Dashboard database: %s",
            config.NOTION_MODEL_DASHBOARD_DB_ID,
        )
        return resolve_data_source_id(client, config.NOTION_MODEL_DASHBOARD_DB_ID)

    db_title = "AI 모델 현황"

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
                "Reusing Model Dashboard database '%s': %s", db_title, data_source_id
            )
            return data_source_id

    parent_page_id = config.NOTION_MODEL_TRACKER_PAGE_ID or config.NOTION_PARENT_PAGE_ID
    logger.info(
        "Creating Model Dashboard database '%s' under page %s",
        db_title,
        parent_page_id,
    )
    data = cast(
        dict[str, Any],
        client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": db_title}}],
            initial_data_source={"properties": _DASHBOARD_PROPERTIES},
        ),
    )
    data_source_id = data["data_sources"][0]["id"]
    logger.info("Created Model Dashboard database '%s': %s", db_title, data_source_id)
    return data_source_id


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

_NUMBER_FIELD_MAP: dict[str, str] = {
    "종합 지능": "intelligence_index",
    "코딩 지수": "coding_index",
    "수학 지수": "math_index",
    "속도 지수": "speed_index",
    "입력 가격": "price_input",
    "출력 가격": "price_output",
    "처리 속도": "speed_tokens_per_sec",
    "TTFT": "ttft_seconds",
}


def _find_model_page(
    client: notion_client.Client, data_source_id: str, model_id: str
) -> str | None:
    """Query dashboard DB for an existing model page by *model_id*.

    Returns:
        The page-id when found, ``None`` otherwise.
    """
    results = cast(
        dict[str, Any],
        client.data_sources.query(
            data_source_id=data_source_id,
            filter={"property": "모델 ID", "rich_text": {"equals": model_id}},
        ),
    )
    pages = results.get("results", [])
    return pages[0]["id"] if pages else None


def _build_dashboard_properties(model: dict[str, Any], rank: int) -> dict[str, Any]:
    """Convert a model snapshot dict + rank into Notion page properties.

    ``None`` numeric values are **omitted** to avoid Notion API errors.
    """
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    props: dict[str, Any] = {
        "모델명": {"title": [{"text": {"content": model.get("name", "Unknown")}}]},
        "모델 ID": {"rich_text": [{"text": {"content": model.get("model_id", "")}}]},
        "순위": {"number": rank},
        "마지막 업데이트": {"date": {"start": today}},
    }

    # Select — creator (omit when None/empty)
    creator = model.get("creator")
    if creator:
        props["제작사"] = {"select": {"name": creator}}

    # Number fields — omit when the value is None
    for notion_key, model_key in _NUMBER_FIELD_MAP.items():
        value = model.get(model_key)
        if value is not None:
            props[notion_key] = {"number": value}

    return props


def _upsert_model(
    client: notion_client.Client,
    data_source_id: str,
    model: dict[str, Any],
    rank: int,
) -> str:
    """Upsert a single model to the dashboard.

    Returns:
        ``"created"`` or ``"updated"``.
    """
    model_id = model.get("model_id", "")
    page_id = _find_model_page(client, data_source_id, model_id)
    properties = _build_dashboard_properties(model, rank)

    if page_id:
        client.pages.update(page_id=page_id, properties=properties)
        return "updated"

    client.pages.create(
        parent={"type": "data_source_id", "data_source_id": data_source_id},
        properties=properties,
    )
    return "created"
