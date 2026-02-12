"""InsightFlow main orchestrator - collects, filters, summarizes, and delivers tech news."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from src import config
from src.ai_handler import filter_and_summarize
from src.model_tracker import fetch_model_data, get_model_updates, save_model_snapshots
from src.notion_handler import send_to_notion
from src.notion_model_handler import send_model_updates_to_notion
from src.notifier import send_digest, send_failure_notification
from src.scraper import scrape_all
from src.storage import (
    create_github_issues,
    filter_new_articles,
    load_seen_ids,
    save_daily_articles,
    save_seen_ids,
)

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main(dry_run: bool = False) -> None:
    if dry_run:
        config.DRY_RUN = True

    try:
        # 1. Data collection
        logger.info("Starting data collection...")
        all_articles = asyncio.run(scrape_all())
        logger.info("Collected %d articles", len(all_articles))

        # 2. Deduplication
        seen_ids = load_seen_ids()
        new_articles = filter_new_articles(all_articles, seen_ids)
        logger.info("New articles: %d", len(new_articles))

        if not new_articles:
            logger.info("No new articles found. Exiting.")
            return

        # 3. Keyword filter + AI summary
        processed = filter_and_summarize(new_articles)
        logger.info("After filtering: %d articles", len(processed))

        # 4. Save data
        today = datetime.now().strftime("%Y-%m-%d")
        save_daily_articles(processed, today)
        save_seen_ids(seen_ids)

        # 5. GitHub Issues
        if not dry_run:
            create_github_issues(processed)
            logger.info("GitHub Issues created")
        else:
            logger.info("[DRY RUN] GitHub Issues creation skipped")

        # 6. Notion
        if not dry_run:
            send_to_notion(processed)
            logger.info("Notion database updated")
        else:
            logger.info("[DRY RUN] Notion update skipped")

        # 7. Model Tracker
        model_updates: dict[str, list[dict[str, object]]] | None = None
        try:
            logger.info("Starting model tracker...")
            models = fetch_model_data()
            save_model_snapshots(models, today)
            updates = get_model_updates(today)
            model_updates = updates
            logger.info(
                "Model tracker done: %d new, %d rank changes, %d price changes",
                len(updates.get("new_models", [])),
                len(updates.get("rank_changes", [])),
                len(updates.get("price_changes", [])),
            )
        except Exception:
            logger.exception("Model tracker failed (non-fatal)")

        # 7.5 Model Tracker → Notion
        if model_updates and not dry_run:
            send_model_updates_to_notion(model_updates)
            logger.info("Model updates synced to Notion")
        else:
            logger.info("[DRY RUN] Model tracker Notion sync skipped")

        # 8. Telegram digest
        if not dry_run:
            send_digest(processed, model_updates=model_updates)
            logger.info("Telegram digest sent")
        else:
            logger.info("[DRY RUN] Telegram send skipped")

        logger.info("Pipeline completed successfully")

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        if not dry_run:
            try:
                send_failure_notification(str(e))
            except Exception:
                logger.error("Failed to send failure notification")
        raise


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="InsightFlow - AI tech news tracker",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run pipeline without sending notifications or creating issues",
    )
    return parser.parse_args()


if __name__ == "__main__":
    setup_logging()
    args = cli()
    dry_run = args.dry_run or config.DRY_RUN
    main(dry_run=dry_run)
