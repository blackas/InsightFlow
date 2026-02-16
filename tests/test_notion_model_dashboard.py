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


# ---------------------------------------------------------------------------
# Task 3: Upsert logic tests
# ---------------------------------------------------------------------------

_FULL_MODEL = {
    "model_id": "gpt-5",
    "name": "GPT-5",
    "creator": "OpenAI",
    "intelligence_index": 95.2,
    "coding_index": 88.1,
    "math_index": 91.5,
    "speed_index": 75.0,
    "price_input": 2.50,
    "price_output": 10.00,
    "speed_tokens_per_sec": 150.0,
    "ttft_seconds": 0.3,
}

_SPARSE_MODEL = {
    "model_id": "sparse-model",
    "name": "Sparse",
    "creator": None,
    "intelligence_index": 80.0,
    "coding_index": None,
    "math_index": None,
    "speed_index": None,
    "price_input": 1.0,
    "price_output": None,
    "speed_tokens_per_sec": None,
    "ttft_seconds": None,
}


class TestFindModelPage:
    def test_find_existing_model(self, mock_notion_client):
        mock_notion_client.data_sources.query.return_value = {
            "results": [{"id": "page-123"}]
        }
        from src.notion_model_dashboard import _find_model_page

        result = _find_model_page(mock_notion_client, "ds-id", "model-abc")

        mock_notion_client.data_sources.query.assert_called_once_with(
            data_source_id="ds-id",
            filter={"property": "모델 ID", "rich_text": {"equals": "model-abc"}},
        )
        assert result == "page-123"

    def test_find_nonexistent_model(self, mock_notion_client):
        mock_notion_client.data_sources.query.return_value = {"results": []}
        from src.notion_model_dashboard import _find_model_page

        assert _find_model_page(mock_notion_client, "ds-id", "model-xyz") is None


class TestBuildDashboardProperties:
    def test_all_fields_mapped(self):
        from src.notion_model_dashboard import _build_dashboard_properties

        props = _build_dashboard_properties(_FULL_MODEL, rank=1)

        assert props["모델명"]["title"][0]["text"]["content"] == "GPT-5"
        assert props["모델 ID"]["rich_text"][0]["text"]["content"] == "gpt-5"
        assert props["제작사"]["select"]["name"] == "OpenAI"
        assert props["종합 지능"]["number"] == 95.2
        assert props["코딩 지수"]["number"] == 88.1
        assert props["수학 지수"]["number"] == 91.5
        assert props["속도 지수"]["number"] == 75.0
        assert props["입력 가격"]["number"] == 2.50
        assert props["출력 가격"]["number"] == 10.00
        assert props["처리 속도"]["number"] == 150.0
        assert props["TTFT"]["number"] == 0.3
        assert props["순위"]["number"] == 1
        assert "start" in props["마지막 업데이트"]["date"]

    def test_none_values_omitted(self):
        from src.notion_model_dashboard import _build_dashboard_properties

        props = _build_dashboard_properties(_SPARSE_MODEL, rank=5)

        # Present
        assert props["모델명"]["title"][0]["text"]["content"] == "Sparse"
        assert props["종합 지능"]["number"] == 80.0
        assert props["입력 가격"]["number"] == 1.0
        assert props["순위"]["number"] == 5

        # Omitted (None values)
        for absent in (
            "코딩 지수",
            "수학 지수",
            "속도 지수",
            "출력 가격",
            "처리 속도",
            "TTFT",
            "제작사",
        ):
            assert absent not in props, f"{absent} should be omitted when value is None"


class TestUpsertModel:
    def test_upsert_creates_new_model(self, mock_notion_client):
        mock_notion_client.data_sources.query.return_value = {"results": []}
        from src.notion_model_dashboard import _upsert_model

        result = _upsert_model(mock_notion_client, "ds-id", _FULL_MODEL, rank=3)

        assert result == "created"
        mock_notion_client.pages.create.assert_called_once()
        mock_notion_client.pages.update.assert_not_called()
        create_kwargs = mock_notion_client.pages.create.call_args
        assert create_kwargs.kwargs["parent"]["data_source_id"] == "ds-id"

    def test_upsert_updates_existing_model(self, mock_notion_client):
        mock_notion_client.data_sources.query.return_value = {
            "results": [{"id": "existing-page-id"}]
        }
        from src.notion_model_dashboard import _upsert_model

        result = _upsert_model(mock_notion_client, "ds-id", _FULL_MODEL, rank=2)

        assert result == "updated"
        mock_notion_client.pages.update.assert_called_once()
        mock_notion_client.pages.create.assert_not_called()
        assert (
            mock_notion_client.pages.update.call_args.kwargs["page_id"]
            == "existing-page-id"
        )


class TestSyncModelsToDashboard:
    def test_sync_returns_zero_when_none(self, monkeypatch):
        monkeypatch.setattr(config, "NOTION_API_KEY", "test-key")
        monkeypatch.setattr(config, "DRY_RUN", False)
        from src.notion_model_dashboard import sync_models_to_dashboard

        assert sync_models_to_dashboard(None) == 0

    def test_sync_returns_zero_when_empty(self, monkeypatch):
        monkeypatch.setattr(config, "NOTION_API_KEY", "test-key")
        monkeypatch.setattr(config, "DRY_RUN", False)
        from src.notion_model_dashboard import sync_models_to_dashboard

        assert sync_models_to_dashboard([]) == 0

    def test_sync_skips_when_dry_run(self, monkeypatch):
        monkeypatch.setattr(config, "NOTION_API_KEY", "test-key")
        monkeypatch.setattr(config, "DRY_RUN", True)
        from src.notion_model_dashboard import sync_models_to_dashboard

        assert sync_models_to_dashboard([{"model_id": "test"}]) == 0

    def test_sync_skips_when_no_api_key(self, monkeypatch):
        monkeypatch.setattr(config, "NOTION_API_KEY", None)
        monkeypatch.setattr(config, "DRY_RUN", False)
        from src.notion_model_dashboard import sync_models_to_dashboard

        assert sync_models_to_dashboard([{"model_id": "test"}]) == 0

    @patch("src.notion_model_dashboard.get_client")
    @patch("src.notion_model_dashboard.ensure_model_dashboard_db", return_value="ds-id")
    @patch("src.notion_model_dashboard._upsert_model")
    @patch("src.notion_model_dashboard.time")
    def test_sync_upserts_models_sorted_by_intelligence(
        self, mock_time, mock_upsert, mock_ensure_db, mock_get_client, monkeypatch
    ):
        monkeypatch.setattr(config, "NOTION_API_KEY", "test-key")
        monkeypatch.setattr(config, "DRY_RUN", False)
        mock_upsert.return_value = "created"

        models = [
            {"model_id": "b", "name": "ModelB", "intelligence_index": 80.0},
            {"model_id": "a", "name": "ModelA", "intelligence_index": 95.0},
            {"model_id": "c", "name": "ModelC", "intelligence_index": 70.0},
        ]

        from src.notion_model_dashboard import sync_models_to_dashboard

        result = sync_models_to_dashboard(models)

        assert result == 3
        assert mock_upsert.call_count == 3

        # Verify sorted by intelligence_index descending (rank 1 = highest)
        calls = mock_upsert.call_args_list
        # First call should be ModelA (95.0, rank 1)
        assert calls[0].args[2]["model_id"] == "a"
        assert calls[0].args[3] == 1  # rank
        # Second: ModelB (80.0, rank 2)
        assert calls[1].args[2]["model_id"] == "b"
        assert calls[1].args[3] == 2
        # Third: ModelC (70.0, rank 3)
        assert calls[2].args[2]["model_id"] == "c"
        assert calls[2].args[3] == 3

        # Rate limiting: sleep called between upserts (n-1 times)
        assert mock_time.sleep.call_count == 2
        mock_time.sleep.assert_called_with(0.35)
