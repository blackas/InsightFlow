from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import requests

from src import config

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "models.db"

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS model_snapshots (
    model_id TEXT NOT NULL,
    name TEXT NOT NULL,
    creator TEXT,
    intelligence_index REAL,
    coding_index REAL,
    math_index REAL,
    speed_index REAL,
    price_input REAL,
    price_output REAL,
    speed_tokens_per_sec REAL,
    ttft_seconds REAL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (model_id, fetched_at)
);
"""

_INSERT_SQL = """\
INSERT OR REPLACE INTO model_snapshots (
    model_id, name, creator,
    intelligence_index, coding_index, math_index, speed_index,
    price_input, price_output, speed_tokens_per_sec, ttft_seconds,
    fetched_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def _init_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    _ = conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def fetch_model_data() -> list[dict[str, Any]]:
    api_key = config.ARTIFICIAL_ANALYSIS_API_KEY
    if not api_key:
        logger.warning("ARTIFICIAL_ANALYSIS_API_KEY not set, skipping model fetch")
        return []

    url = "https://artificialanalysis.ai/api/v2/data/llms/models"
    headers = {"x-api-key": api_key}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        logger.exception("Failed to fetch models from Artificial Analysis API")
        return []
    except ValueError:
        logger.exception("Invalid JSON response from Artificial Analysis API")
        return []

    if isinstance(data, list):
        models: list[dict[str, Any]] = data
    elif isinstance(data, dict):
        models = data.get("data") or data.get("models") or data.get("results") or []
    else:
        logger.error("Unexpected API response type: %s", type(data).__name__)
        return []

    logger.info("Fetched %d models from Artificial Analysis", len(models))
    return models


def save_model_snapshots(models: list[dict[str, Any]], date: str) -> int:
    conn = _init_db()

    if not models:
        logger.info("No models to save")
        conn.close()
        return 0
    count = 0

    try:
        for model in models:
            model_id = model.get("model_id") or model.get("id")
            name = model.get("name") or model.get("model_name")
            if not model_id or not name:
                continue

            row = (
                str(model_id),
                str(name),
                model.get("creator"),
                model.get("intelligence_index"),
                model.get("coding_index"),
                model.get("math_index"),
                model.get("speed_index"),
                model.get("price_input"),
                model.get("price_output"),
                model.get("speed_tokens_per_sec"),
                model.get("ttft_seconds"),
                date,
            )
            _ = conn.execute(_INSERT_SQL, row)
            count += 1

        conn.commit()
        logger.info("Saved %d model snapshots for %s", count, date)
    except sqlite3.Error:
        logger.exception("Database error while saving model snapshots")
        conn.rollback()
        count = 0
    finally:
        conn.close()

    return count


def get_previous_snapshot(date: str) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []

    conn = _init_db()
    try:
        cursor = conn.execute(
            (
                "SELECT DISTINCT fetched_at FROM model_snapshots "
                "WHERE fetched_at < ? ORDER BY fetched_at DESC LIMIT 1"
            ),
            (date,),
        )
        row = cursor.fetchone()
        if not row:
            return []

        prev_date: str = row[0]
        cursor = conn.execute(
            (
                "SELECT model_id, name, creator, "
                "intelligence_index, coding_index, math_index, speed_index, "
                "price_input, price_output, speed_tokens_per_sec, ttft_seconds, "
                "fetched_at "
                "FROM model_snapshots WHERE fetched_at = ?"
            ),
            (prev_date,),
        )
        columns: list[str] = [desc[0] for desc in cursor.description]  # type: ignore[misc]
        results: list[dict[str, Any]] = [
            dict(zip(columns, r)) for r in cursor.fetchall()
        ]
        logger.info(
            "Found %d models in previous snapshot (%s)", len(results), prev_date
        )
        return results
    except sqlite3.Error:
        logger.exception("Database error while querying previous snapshot")
        return []
    finally:
        conn.close()


def detect_new_models(
    today_models: list[dict[str, Any]], yesterday_models: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Detect models that exist in today's snapshot but not in yesterday's.

    Args:
        today_models: List of model dicts from today
        yesterday_models: List of model dicts from yesterday

    Returns:
        List of new models (models in today but not in yesterday)
    """
    if not yesterday_models:
        return []

    yesterday_ids = {m.get("model_id") for m in yesterday_models}
    new_models = [m for m in today_models if m.get("model_id") not in yesterday_ids]

    logger.info("Detected %d new models", len(new_models))
    return new_models


def detect_rank_changes(
    today_models: list[dict[str, Any]],
    yesterday_models: list[dict[str, Any]],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """
    Detect rank changes in top N models by intelligence_index.

    Args:
        today_models: List of model dicts from today
        yesterday_models: List of model dicts from yesterday
        top_n: Number of top models to compare (default: 10)

    Returns:
        List of rank change dicts with keys: name, old_rank, new_rank, intelligence_index
    """
    if not yesterday_models:
        return []

    # Sort by intelligence_index descending
    today_sorted = sorted(
        [m for m in today_models if m.get("intelligence_index") is not None],
        key=lambda x: x.get("intelligence_index", 0),
        reverse=True,
    )[:top_n]

    yesterday_sorted = sorted(
        [m for m in yesterday_models if m.get("intelligence_index") is not None],
        key=lambda x: x.get("intelligence_index", 0),
        reverse=True,
    )[:top_n]

    # Build rank maps
    yesterday_ranks = {
        m.get("model_id"): idx + 1 for idx, m in enumerate(yesterday_sorted)
    }

    changes = []
    for idx, model in enumerate(today_sorted):
        model_id = model.get("model_id")
        today_rank = idx + 1
        yesterday_rank = yesterday_ranks.get(model_id)

        if yesterday_rank and yesterday_rank != today_rank:
            changes.append(
                {
                    "name": model.get("name"),
                    "old_rank": yesterday_rank,
                    "new_rank": today_rank,
                    "intelligence_index": model.get("intelligence_index"),
                }
            )

    logger.info("Detected %d rank changes in top %d", len(changes), top_n)
    return changes


def detect_price_changes(
    today_models: list[dict[str, Any]],
    yesterday_models: list[dict[str, Any]],
    threshold: float = 0.10,
) -> list[dict[str, Any]]:
    """
    Detect price changes exceeding threshold.

    Args:
        today_models: List of model dicts from today
        yesterday_models: List of model dicts from yesterday
        threshold: Minimum change percentage to report (default: 0.10 = 10%)

    Returns:
        List of price change dicts with keys: name, old_price, new_price, change_percent
    """
    if not yesterday_models:
        return []

    # Build yesterday price map
    yesterday_prices = {}
    for m in yesterday_models:
        model_id = m.get("model_id")
        price_in = m.get("price_input")
        price_out = m.get("price_output")
        if model_id and price_in is not None and price_out is not None:
            yesterday_prices[model_id] = (price_in + price_out) / 2

    changes = []
    for model in today_models:
        model_id = model.get("model_id")
        price_in = model.get("price_input")
        price_out = model.get("price_output")

        if (
            model_id
            and price_in is not None
            and price_out is not None
            and model_id in yesterday_prices
        ):
            today_price = (price_in + price_out) / 2
            yesterday_price = yesterday_prices[model_id]

            if yesterday_price > 0:
                change_percent = (today_price - yesterday_price) / yesterday_price
                if abs(change_percent) >= threshold:
                    changes.append(
                        {
                            "name": model.get("name"),
                            "old_price": yesterday_price,
                            "new_price": today_price,
                            "change_percent": change_percent,
                        }
                    )

    logger.info(
        "Detected %d price changes exceeding %.1f%%", len(changes), threshold * 100
    )
    return changes


def get_model_updates(date_str: str) -> dict[str, list[dict[str, Any]]]:
    """
    Get all model updates for a given date.

    Args:
        date_str: Date string to check updates for

    Returns:
        Dict with keys: new_models, rank_changes, price_changes
    """
    yesterday_models = get_previous_snapshot(date_str)

    # If no previous snapshot, return empty results
    if not yesterday_models:
        logger.info("No previous snapshot found, returning empty updates")
        return {"new_models": [], "rank_changes": [], "price_changes": []}

    # For this function to work, we need today's models
    # This is a placeholder - caller should provide today's models
    # For now, return empty lists as we don't have today's data in this function
    logger.warning("get_model_updates requires today's models to be passed separately")
    return {"new_models": [], "rank_changes": [], "price_changes": []}
