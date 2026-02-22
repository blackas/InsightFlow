"""Tests for _normalize_model() and _first_not_none() helpers."""

from __future__ import annotations

from src.model_tracker import _first_not_none, _normalize_model


# -- _first_not_none --------------------------------------------------------


def test_first_not_none_returns_first_value():
    assert _first_not_none(1, 2, 3) == 1


def test_first_not_none_skips_nones():
    assert _first_not_none(None, None, 42) == 42


def test_first_not_none_preserves_zero():
    """0 is a valid value — must not be treated as None."""
    assert _first_not_none(0, 99) == 0


def test_first_not_none_preserves_empty_string():
    assert _first_not_none("", "fallback") == ""


def test_first_not_none_all_none():
    assert _first_not_none(None, None) is None


# -- _normalize_model: nested API format ------------------------------------


def _make_api_model() -> dict:
    """Return a realistic Artificial Analysis API response model."""
    return {
        "id": "2dad8957-4c16-4e74-bf2d-8b21514e0ae9",
        "name": "o3-mini",
        "slug": "o3-mini",
        "model_creator": {
            "id": "e67e56e3-15cd-43db-b679-da4660a69f41",
            "name": "OpenAI",
            "slug": "openai",
        },
        "evaluations": {
            "artificial_analysis_intelligence_index": 62.9,
            "artificial_analysis_coding_index": 55.8,
            "artificial_analysis_math_index": 87.2,
        },
        "pricing": {
            "price_1m_blended_3_to_1": 1.925,
            "price_1m_input_tokens": 1.1,
            "price_1m_output_tokens": 4.4,
        },
        "median_output_tokens_per_second": 153.831,
        "median_time_to_first_token_seconds": 14.939,
    }


def test_normalize_extracts_nested_api_fields():
    raw = _make_api_model()
    result = _normalize_model(raw)

    assert result["model_id"] == "2dad8957-4c16-4e74-bf2d-8b21514e0ae9"
    assert result["name"] == "o3-mini"
    assert result["creator"] == "OpenAI"
    assert result["intelligence_index"] == 62.9
    assert result["coding_index"] == 55.8
    assert result["math_index"] == 87.2
    assert result["price_input"] == 1.1
    assert result["price_output"] == 4.4
    assert result["speed_tokens_per_sec"] == 153.831
    assert result["ttft_seconds"] == 14.939
    assert result["speed_index"] is None  # not in API response


# -- _normalize_model: flat (SQLite / legacy) format -----------------------


def test_normalize_passthrough_flat_format():
    """Data already in flat format (e.g. read back from SQLite) stays intact."""
    flat = {
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
    }
    result = _normalize_model(flat)

    for key, value in flat.items():
        assert result[key] == value, f"Mismatch on {key}"


# -- _normalize_model: edge cases ------------------------------------------


def test_normalize_handles_none_evaluations():
    raw = _make_api_model()
    raw["evaluations"] = None
    result = _normalize_model(raw)
    assert result["intelligence_index"] is None
    assert result["coding_index"] is None
    assert result["math_index"] is None


def test_normalize_handles_missing_model_creator():
    raw = _make_api_model()
    del raw["model_creator"]
    result = _normalize_model(raw)
    assert result["creator"] is None


def test_normalize_handles_string_model_creator():
    """If model_creator is a string instead of dict, don't crash."""
    raw = _make_api_model()
    raw["model_creator"] = "OpenAI"  # type: ignore[assignment]
    result = _normalize_model(raw)
    # Falls back to None since it's not a dict
    assert result["creator"] is None


def test_normalize_handles_missing_pricing():
    raw = _make_api_model()
    raw["pricing"] = None
    result = _normalize_model(raw)
    assert result["price_input"] is None
    assert result["price_output"] is None
