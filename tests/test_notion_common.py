"""Tests for src.notion_common module — Task 8."""

from unittest.mock import MagicMock, patch


class TestNotionCommon:
    """Verify shared utilities exist in notion_common and duplication is removed."""

    def test_get_client_returns_notion_client(self):
        """get_client() should create and return a Notion API client."""
        with patch("src.notion_common.config") as mock_config:
            mock_config.NOTION_API_KEY = "test-key"
            with patch("src.notion_common.notion_client.Client") as mock_client_cls:
                from src.notion_common import get_client

                result = get_client()
                mock_client_cls.assert_called_once_with(auth="test-key")
                assert result == mock_client_cls.return_value

    def test_both_handlers_use_common_functions(self):
        """notion_handler.py and notion_model_handler.py must NOT define _get_client or _resolve_data_source_id."""
        from src import notion_handler, notion_model_handler

        nh_source = open(notion_handler.__file__).read()
        nmh_source = open(notion_model_handler.__file__).read()

        assert "def _get_client" not in nh_source, (
            "_get_client still defined in notion_handler.py"
        )
        assert "def _get_client" not in nmh_source, (
            "_get_client still defined in notion_model_handler.py"
        )
        assert "def _resolve_data_source_id" not in nh_source, (
            "_resolve_data_source_id still defined in notion_handler.py"
        )
        assert "def _resolve_data_source_id" not in nmh_source, (
            "_resolve_data_source_id still defined in notion_model_handler.py"
        )

    def test_notion_common_exports(self):
        """notion_common module should export get_client and resolve_data_source_id."""
        from src.notion_common import get_client, resolve_data_source_id

        assert callable(get_client)
        assert callable(resolve_data_source_id)
