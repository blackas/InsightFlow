"""Shared pytest fixtures for InsightFlow test suite."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from src.scraper import Article


@pytest.fixture
def sample_article() -> Article:
    """Sample HackerNews article for testing."""
    return Article(
        source="hackernews",
        source_id="12345",
        title="Sample HN Article",
        url="https://example.com/article",
        discussion_url="https://news.ycombinator.com/item?id=12345",
        summary="This is a sample article summary",
        score=100,
        published_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def sample_tldrai_article() -> Article:
    """Sample TLDR AI article for testing."""
    return Article(
        source="tldrai",
        source_id="https://example.com/tldr",
        title="Sample TLDR AI Article",
        url="https://example.com/tldr",
        discussion_url="https://example.com/tldr",
        summary="TLDR AI newsletter article summary",
        score=0,
        published_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def sample_geeknews_article() -> Article:
    """Sample GeekNews article for testing."""
    return Article(
        source="geeknews",
        source_id="https://news.hada.io/topic?id=67890",
        title="Sample GeekNews Article",
        url="https://example.com/geeknews",
        discussion_url="https://news.hada.io/topic?id=67890",
        summary="GeekNews article summary",
        score=0,
        published_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def sample_articles(
    sample_article: Article,
    sample_tldrai_article: Article,
    sample_geeknews_article: Article,
) -> list[Article]:
    """List of sample articles from all three sources."""
    return [sample_article, sample_tldrai_article, sample_geeknews_article]


@pytest.fixture
def mock_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock configuration values to prevent external API calls."""
    import src.config as config

    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "dummy-gemini-key")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "dummy-telegram-token")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "dummy-chat-id")
    monkeypatch.setattr(config, "NOTION_API_KEY", "dummy-notion-key")
    monkeypatch.setattr(config, "NOTION_DATABASE_ID", "dummy-database-id")
    monkeypatch.setattr(config, "NOTION_PARENT_PAGE_ID", "dummy-parent-page-id")
    monkeypatch.setattr(config, "ARTIFICIAL_ANALYSIS_API_KEY", "dummy-aa-key")
    monkeypatch.setattr(config, "BATCH_SIZE", 2)
    monkeypatch.setattr(config, "HN_TOP_N", 5)


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_model_updates() -> dict[str, Any]:
    """Sample model tracker updates for testing notification formatting."""
    return {
        "new_models": [
            {
                "model_id": "gpt-5",
                "name": "GPT-5",
                "creator": "OpenAI",
                "intelligence_index": 95.5,
            }
        ],
        "rank_changes": [
            {
                "name": "Claude 3 Opus",
                "old_rank": 3,
                "new_rank": 1,
                "intelligence_index": 92.0,
            }
        ],
        "price_changes": [
            {
                "name": "GPT-4 Turbo",
                "old_price": 0.01,
                "new_price": 0.008,
                "change_percent": -20.0,
            }
        ],
    }
