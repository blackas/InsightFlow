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
