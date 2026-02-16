"""Tests for get_latest_models() public wrapper function."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.config import KST
from src.model_tracker import get_latest_models


def test_get_latest_models_with_explicit_date() -> None:
    """Test get_latest_models() with explicit date string."""
    with patch("src.model_tracker._get_today_snapshot") as mock_snapshot:
        mock_snapshot.return_value = [
            {
                "model_id": "gpt-4",
                "name": "GPT-4",
                "creator": "OpenAI",
                "intelligence_index": 90.0,
                "coding_index": 88.0,
                "math_index": 92.0,
                "speed_index": 85.0,
                "price_input": 0.03,
                "price_output": 0.06,
                "speed_tokens_per_sec": 100.0,
                "ttft_seconds": 0.5,
                "fetched_at": "2026-02-16",
            }
        ]
        result = get_latest_models("2026-02-16")
        mock_snapshot.assert_called_once_with("2026-02-16")
        assert len(result) == 1
        assert result[0]["model_id"] == "gpt-4"
        assert result[0]["name"] == "GPT-4"


def test_get_latest_models_without_date() -> None:
    """Test get_latest_models() without date arg uses today's KST date."""
    with patch("src.model_tracker._get_today_snapshot") as mock_snapshot:
        mock_snapshot.return_value = [
            {
                "model_id": "claude-3",
                "name": "Claude 3 Opus",
                "creator": "Anthropic",
                "intelligence_index": 92.0,
                "coding_index": 90.0,
                "math_index": 94.0,
                "speed_index": 88.0,
                "price_input": 0.015,
                "price_output": 0.075,
                "speed_tokens_per_sec": 80.0,
                "ttft_seconds": 0.6,
                "fetched_at": "2026-02-16",
            }
        ]
        result = get_latest_models()

        # Verify it was called with today's KST date
        today_kst = datetime.now(KST).strftime("%Y-%m-%d")
        mock_snapshot.assert_called_once_with(today_kst)
        assert len(result) == 1
        assert result[0]["model_id"] == "claude-3"


def test_get_latest_models_empty_result() -> None:
    """Test get_latest_models() returns empty list when no models found."""
    with patch("src.model_tracker._get_today_snapshot") as mock_snapshot:
        mock_snapshot.return_value = []
        result = get_latest_models("2026-02-15")
        mock_snapshot.assert_called_once_with("2026-02-15")
        assert result == []


def test_config_env_vars_exist() -> None:
    """Test that new config env vars can be imported."""
    from src.config import NOTION_MODEL_TRACKER_PAGE_ID, NOTION_MODEL_DASHBOARD_DB_ID

    # These should be importable (may be None if env vars not set)
    assert NOTION_MODEL_TRACKER_PAGE_ID is None or isinstance(
        NOTION_MODEL_TRACKER_PAGE_ID, str
    )
    assert NOTION_MODEL_DASHBOARD_DB_ID is None or isinstance(
        NOTION_MODEL_DASHBOARD_DB_ID, str
    )
