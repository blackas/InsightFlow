"""Tests for src.notion_model_dashboard — Living Dashboard DB schema & ensure function."""

import pytest
from unittest.mock import MagicMock, patch

from src import config


@pytest.fixture
def mock_notion_client():
    return MagicMock()


class TestEnsureModelDashboardDb:
    """Tests for ensure_model_dashboard_db() find-or-create logic."""

    def test_ensure_db_with_explicit_id(self, mock_notion_client, monkeypatch):
        """When NOTION_MODEL_DASHBOARD_DB_ID is set, resolve and return its data_source_id."""
        monkeypatch.setattr(config, "NOTION_MODEL_DASHBOARD_DB_ID", "db-123")
        with patch(
            "src.notion_model_dashboard.resolve_data_source_id",
            return_value="ds-456",
        ) as mock_resolve:
            from src.notion_model_dashboard import ensure_model_dashboard_db

            result = ensure_model_dashboard_db(mock_notion_client)
            mock_resolve.assert_called_once_with(mock_notion_client, "db-123")
            assert result == "ds-456"
            mock_notion_client.search.assert_not_called()
            mock_notion_client.databases.create.assert_not_called()

    def test_ensure_db_search_found(self, mock_notion_client, monkeypatch):
        """When DB ID not set, search for existing DB by title and return its ID."""
        monkeypatch.setattr(config, "NOTION_MODEL_DASHBOARD_DB_ID", "")
        mock_notion_client.search.return_value = {
            "results": [
                {
                    "id": "found-db-id",
                    "title": [{"plain_text": "AI 모델 현황"}],
                }
            ]
        }

        from src.notion_model_dashboard import ensure_model_dashboard_db

        result = ensure_model_dashboard_db(mock_notion_client)

        mock_notion_client.search.assert_called_once_with(
            query="AI 모델 현황",
            filter={"value": "data_source", "property": "object"},
        )
        assert result == "found-db-id"
        mock_notion_client.databases.create.assert_not_called()

    def test_ensure_db_search_not_found_creates(self, mock_notion_client, monkeypatch):
        """When DB not found via search, create a new one under parent page."""
        monkeypatch.setattr(config, "NOTION_MODEL_DASHBOARD_DB_ID", "")
        monkeypatch.setattr(config, "NOTION_MODEL_TRACKER_PAGE_ID", "tracker-page-id")
        monkeypatch.setattr(config, "NOTION_PARENT_PAGE_ID", "parent-page-id")

        mock_notion_client.search.return_value = {"results": []}
        mock_notion_client.databases.create.return_value = {
            "data_sources": [{"id": "new-ds-id"}]
        }

        from src.notion_model_dashboard import (
            ensure_model_dashboard_db,
            _DASHBOARD_PROPERTIES,
        )

        result = ensure_model_dashboard_db(mock_notion_client)

        assert result == "new-ds-id"
        mock_notion_client.databases.create.assert_called_once_with(
            parent={"type": "page_id", "page_id": "tracker-page-id"},
            title=[{"type": "text", "text": {"content": "AI 모델 현황"}}],
            initial_data_source={"properties": _DASHBOARD_PROPERTIES},
        )

    def test_ensure_db_parent_page_fallback(self, mock_notion_client, monkeypatch):
        """When NOTION_MODEL_TRACKER_PAGE_ID is None, fall back to NOTION_PARENT_PAGE_ID."""
        monkeypatch.setattr(config, "NOTION_MODEL_DASHBOARD_DB_ID", "")
        monkeypatch.setattr(config, "NOTION_MODEL_TRACKER_PAGE_ID", None)
        monkeypatch.setattr(config, "NOTION_PARENT_PAGE_ID", "fallback-page-id")

        mock_notion_client.search.return_value = {"results": []}
        mock_notion_client.databases.create.return_value = {
            "data_sources": [{"id": "created-ds-id"}]
        }

        from src.notion_model_dashboard import ensure_model_dashboard_db

        result = ensure_model_dashboard_db(mock_notion_client)

        assert result == "created-ds-id"
        create_call = mock_notion_client.databases.create.call_args
        assert create_call.kwargs["parent"]["page_id"] == "fallback-page-id"


class TestDashboardProperties:
    """Verify the _DASHBOARD_PROPERTIES schema definition."""

    def test_properties_count(self):
        """Dashboard should have exactly 13 properties."""
        from src.notion_model_dashboard import _DASHBOARD_PROPERTIES

        assert len(_DASHBOARD_PROPERTIES) == 13

    def test_title_property_is_model_name(self):
        """The title property should be '모델명'."""
        from src.notion_model_dashboard import _DASHBOARD_PROPERTIES

        assert "모델명" in _DASHBOARD_PROPERTIES
        assert _DASHBOARD_PROPERTIES["모델명"]["type"] == "title"

    def test_number_properties(self):
        """All numeric index/price/speed columns should be number type."""
        from src.notion_model_dashboard import _DASHBOARD_PROPERTIES

        number_fields = [
            "종합 지능",
            "코딩 지수",
            "수학 지수",
            "속도 지수",
            "입력 가격",
            "출력 가격",
            "처리 속도",
            "TTFT",
            "순위",
        ]
        for field in number_fields:
            assert field in _DASHBOARD_PROPERTIES, f"Missing property: {field}"
            assert _DASHBOARD_PROPERTIES[field]["type"] == "number", (
                f"{field} should be number type"
            )
