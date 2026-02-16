from __future__ import annotations

import logging
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
