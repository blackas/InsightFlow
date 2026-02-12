"""Shared utilities for Notion integration modules."""

from __future__ import annotations

from typing import Any, cast

import notion_client

from src import config


def get_client() -> notion_client.Client:
    """Create and return a Notion API client."""
    return notion_client.Client(auth=config.NOTION_API_KEY)


def resolve_data_source_id(client: notion_client.Client, database_id: str) -> str:
    """Retrieve the data_source_id from a database_id (Notion API 2025-09-03)."""
    data = cast(dict[str, Any], client.databases.retrieve(database_id=database_id))
    return data["data_sources"][0]["id"]
