"""Tests for detect_new_models() first-run initial baseline and get_model_updates() flow."""

from __future__ import annotations

from unittest.mock import patch

from src.model_tracker import detect_new_models, get_model_updates


# Test 1: First run — empty yesterday returns Top 20 sorted by intelligence_index desc
def test_detect_new_models_first_run_returns_top_20():
    today = [
        {"model_id": f"m{i}", "name": f"Model {i}", "intelligence_index": float(i)}
        for i in range(50)
    ]
    result = detect_new_models(today, [])
    assert len(result) == 20
    # Verify sorted descending
    assert result[0]["intelligence_index"] == 49.0
    assert result[19]["intelligence_index"] == 30.0


# Test 2: First run — custom initial_top_n
def test_detect_new_models_first_run_custom_top_n():
    today = [
        {"model_id": f"m{i}", "name": f"Model {i}", "intelligence_index": float(i)}
        for i in range(50)
    ]
    result = detect_new_models(today, [], initial_top_n=5)
    assert len(result) == 5
    assert result[0]["intelligence_index"] == 49.0


# Test 3: First run — fewer models than top_n returns all available
def test_detect_new_models_first_run_fewer_than_top_n():
    today = [
        {"model_id": f"m{i}", "name": f"Model {i}", "intelligence_index": float(i)}
        for i in range(10)
    ]
    result = detect_new_models(today, [])
    assert len(result) == 10


# Test 4: First run — models with None intelligence_index are excluded from ranking
def test_detect_new_models_first_run_filters_none_intelligence():
    today = [
        {"model_id": "m1", "name": "Model 1", "intelligence_index": 90.0},
        {"model_id": "m2", "name": "Model 2", "intelligence_index": None},
        {"model_id": "m3", "name": "Model 3", "intelligence_index": 80.0},
    ]
    result = detect_new_models(today, [])
    model_ids = [m["model_id"] for m in result]
    assert "m2" not in model_ids
    assert len(result) == 2
    # Verify order
    assert result[0]["model_id"] == "m1"
    assert result[1]["model_id"] == "m3"


# Test 5: Normal behavior (non-first-run) is completely preserved
def test_detect_new_models_normal_behavior_unchanged():
    yesterday = [{"model_id": "m1"}, {"model_id": "m2"}]
    today = [{"model_id": "m1"}, {"model_id": "m2"}, {"model_id": "m3"}]
    result = detect_new_models(today, yesterday)
    assert len(result) == 1
    assert result[0]["model_id"] == "m3"


# Test 6: get_model_updates with no previous snapshot returns top 20 new_models
def test_get_model_updates_first_run():
    mock_today = [
        {"model_id": f"m{i}", "name": f"Model {i}", "intelligence_index": float(i)}
        for i in range(50)
    ]
    with (
        patch("src.model_tracker._get_today_snapshot", return_value=mock_today),
        patch("src.model_tracker.get_previous_snapshot", return_value=[]),
    ):
        result = get_model_updates("2026-02-17")
        assert len(result["new_models"]) == 20
        assert result["rank_changes"] == []
        assert result["price_changes"] == []
