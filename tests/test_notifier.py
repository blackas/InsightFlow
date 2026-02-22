"""Tests for notifier module - message formatting and URL escaping."""

from src.notifier import _escape_md, _escape_url, format_digest


def test_format_digest_with_new_models(sample_article, sample_model_updates):
    """format_digest should handle new_models with 'name' key (not 'model_name')."""
    updates = {"new_models": sample_model_updates["new_models"], "rank_changes": [], "price_changes": []}
    result = format_digest([sample_article], model_updates=updates)
    # MarkdownV2 escapes hyphens, so GPT-5 becomes GPT\-5
    assert "GPT" in result
    assert "OpenAI" in result
    assert "95" in result  # intelligence_index


def test_format_digest_with_rank_changes(sample_article, sample_model_updates):
    """format_digest should handle rank_changes with 'name' key."""
    updates = {"new_models": [], "rank_changes": sample_model_updates["rank_changes"], "price_changes": []}
    result = format_digest([sample_article], model_updates=updates)
    assert "Claude" in result
    assert "3" in result and "1" in result  # old_rank → new_rank


def test_format_digest_with_price_changes(sample_article, sample_model_updates):
    """format_digest should handle price_changes with 'name' key."""
    updates = {"new_models": [], "rank_changes": [], "price_changes": sample_model_updates["price_changes"]}
    result = format_digest([sample_article], model_updates=updates)
    assert "GPT" in result
    assert "Turbo" in result


def test_format_digest_with_all_model_updates(sample_article, sample_model_updates):
    """format_digest should handle all model update types without crashing."""
    result = format_digest([sample_article], model_updates=sample_model_updates)
    assert "AI Model Updates" in result
    assert "GPT" in result
    assert "Claude" in result
    assert "Turbo" in result

def test_format_digest_with_none_creator(sample_article):
    """format_digest must handle model updates where 'creator' is None (from API)."""
    updates = {
        "new_models": [
            {"name": "MiniMax-M2.5", "creator": None, "intelligence_index": 80.5},
        ],
        "rank_changes": [],
        "price_changes": [],
    }
    result = format_digest([sample_article], model_updates=updates)
    assert "MiniMax" in result
    # Should not crash — creator=None renders as empty string
    assert "80" in result  # intelligence_index


def test_format_digest_with_none_fields_everywhere(sample_article):
    """format_digest must handle None in any field without crashing."""
    updates = {
        "new_models": [
            {"name": None, "creator": None, "intelligence_index": None},
        ],
        "rank_changes": [
            {"name": None, "old_rank": None, "new_rank": None},
        ],
        "price_changes": [
            {"name": None, "old_price": None, "new_price": None, "change_percent": None},
        ],
    }
    # Should not crash
    result = format_digest([sample_article], model_updates=updates)
    assert "AI Model Updates" in result


# --- _escape_url tests ---


def test_escape_url_preserves_normal_url():
    """_escape_url must NOT escape dots, equals, hyphens etc. in URLs."""
    url = "https://example.com/path?key=value&foo=bar"
    assert _escape_url(url) == url


def test_escape_url_escapes_closing_paren():
    """_escape_url must escape ')' to prevent breaking MarkdownV2 link syntax."""
    url = "https://en.wikipedia.org/wiki/AI_(term)"
    assert _escape_url(url) == "https://en.wikipedia.org/wiki/AI_(term\\)"


def test_escape_url_escapes_backslash():
    """_escape_url must escape backslashes."""
    url = "https://example.com/path\\file"
    assert _escape_url(url) == "https://example.com/path\\\\file"


def test_escape_url_handles_none():
    """_escape_url must return empty string for None."""
    assert _escape_url(None) == ""


def test_escape_url_handles_empty_string():
    """_escape_url must return empty string for empty input."""
    assert _escape_url("") == ""


def test_escape_md_over_escapes_url():
    """Confirm _escape_md damages URLs - this is why _escape_url exists."""
    url = "https://example.com/path?key=value"
    escaped = _escape_md(url)
    # _escape_md escapes dots and equals which breaks URLs
    assert "\\." in escaped
    assert "\\=" in escaped


def test_format_digest_urls_not_over_escaped(sample_article):
    """format_digest must produce valid URLs (no escaped dots/equals)."""
    result = format_digest([sample_article])
    # The sample_article URL is https://example.com/article
    # It should appear as-is inside the markdown link, not with escaped dots
    assert "https://example.com/article" in result
    assert "https://news.ycombinator.com/item?id=12345" in result


def test_format_digest_urls_with_special_chars():
    """format_digest must handle URLs containing closing parentheses."""
    from src.scraper import Article
    from datetime import datetime, timezone

    article = Article(
        source="hackernews",
        source_id="99999",
        title="Test",
        url="https://example.com/wiki/AI_(term)",
        discussion_url="https://news.ycombinator.com/item?id=99999",
        summary="Test summary",
        score=50,
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    result = format_digest([article])
    # The closing paren in the URL must be escaped so MarkdownV2 link works
    assert "AI_(term\\)" in result
