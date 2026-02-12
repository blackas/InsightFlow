"""Tests for notifier module - model update formatting."""

from src.notifier import format_digest


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
