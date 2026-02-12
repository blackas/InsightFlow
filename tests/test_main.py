"""Tests for src.main pipeline orchestration."""

from unittest.mock import MagicMock, call, patch

import pytest


class TestSeenIdsSaveTiming:
    """Task 3: Verify seen_ids are saved immediately after processing,
    before notifications (GitHub Issues, Notion, Telegram)."""

    @patch("src.main.send_digest")
    @patch("src.main.send_model_updates_to_notion", return_value=0)
    @patch("src.main.send_to_notion")
    @patch("src.main.create_github_issues")
    @patch("src.main.save_seen_ids")
    @patch("src.main.save_daily_articles")
    @patch("src.main.filter_and_summarize")
    @patch("src.main.filter_new_articles")
    @patch("src.main.load_seen_ids")
    @patch("src.main.scrape_all")
    @patch("src.main.fetch_model_data")
    @patch("src.main.save_model_snapshots")
    @patch("src.main.get_model_updates")
    def test_seen_ids_saved_after_processing(
        self,
        mock_get_model_updates,
        mock_save_snapshots,
        mock_fetch_model,
        mock_scrape,
        mock_load_seen,
        mock_filter_new,
        mock_filter_summarize,
        mock_save_daily,
        mock_save_seen,
        mock_create_issues,
        mock_send_notion,
        mock_send_model_notion,
        mock_send_digest,
        sample_articles,
    ):
        """save_seen_ids() must be called BEFORE create_github_issues/send_to_notion/send_digest."""
        from src.main import main

        # Setup mocks
        mock_scrape.return_value = sample_articles
        mock_load_seen.return_value = set()
        mock_filter_new.return_value = sample_articles
        mock_filter_summarize.return_value = sample_articles
        mock_get_model_updates.return_value = {"new_models": [], "rank_changes": [], "price_changes": []}

        # Track call order using a shared manager
        manager = MagicMock()
        manager.attach_mock(mock_save_daily, "save_daily")
        manager.attach_mock(mock_save_seen, "save_seen")
        manager.attach_mock(mock_create_issues, "create_issues")
        manager.attach_mock(mock_send_notion, "send_notion")
        manager.attach_mock(mock_send_digest, "send_digest")

        main(dry_run=False)

        # Extract method names in call order
        call_names = [c[0] for c in manager.mock_calls if c[0] in (
            "save_daily", "save_seen", "create_issues", "send_notion", "send_digest"
        )]

        # save_seen must come after save_daily but before any notifications
        assert "save_seen" in call_names, "save_seen_ids() was never called"
        assert "save_daily" in call_names, "save_daily_articles() was never called"

        save_seen_idx = call_names.index("save_seen")
        save_daily_idx = call_names.index("save_daily")

        assert save_seen_idx > save_daily_idx, (
            f"save_seen_ids() (pos {save_seen_idx}) should come after "
            f"save_daily_articles() (pos {save_daily_idx})"
        )

        # save_seen must be before all notification calls
        for notify_name in ("create_issues", "send_notion", "send_digest"):
            if notify_name in call_names:
                notify_idx = call_names.index(notify_name)
                assert save_seen_idx < notify_idx, (
                    f"save_seen_ids() (pos {save_seen_idx}) must come before "
                    f"{notify_name} (pos {notify_idx})"
                )

    @patch("src.main.send_digest", side_effect=Exception("Telegram API error"))
    @patch("src.main.send_failure_notification")
    @patch("src.main.send_model_updates_to_notion", return_value=0)
    @patch("src.main.send_to_notion")
    @patch("src.main.create_github_issues")
    @patch("src.main.save_seen_ids")
    @patch("src.main.save_daily_articles")
    @patch("src.main.filter_and_summarize")
    @patch("src.main.filter_new_articles")
    @patch("src.main.load_seen_ids")
    @patch("src.main.scrape_all")
    @patch("src.main.fetch_model_data")
    @patch("src.main.save_model_snapshots")
    @patch("src.main.get_model_updates")
    def test_seen_ids_not_lost_on_notification_failure(
        self,
        mock_get_model_updates,
        mock_save_snapshots,
        mock_fetch_model,
        mock_scrape,
        mock_load_seen,
        mock_filter_new,
        mock_filter_summarize,
        mock_save_daily,
        mock_save_seen,
        mock_create_issues,
        mock_send_notion,
        mock_send_model_notion,
        mock_send_failure,
        mock_send_digest,
        sample_articles,
    ):
        """Even if Telegram send fails, seen_ids must already have been saved."""
        from src.main import main

        mock_scrape.return_value = sample_articles
        mock_load_seen.return_value = set()
        mock_filter_new.return_value = sample_articles
        mock_filter_summarize.return_value = sample_articles
        mock_get_model_updates.return_value = {"new_models": [], "rank_changes": [], "price_changes": []}

        # main() will raise because send_digest raises, but seen_ids should be saved
        with pytest.raises(Exception, match="Telegram API error"):
            main(dry_run=False)

        # Verify save_seen_ids was called despite the failure
        mock_save_seen.assert_called_once()

class TestErrorLoggingPreservesTraceback:
    """Task 6: Verify error handlers use logger.exception to preserve tracebacks."""

    def test_error_logging_preserves_traceback(self):
        """main.py error handlers must use logger.exception, not logger.error."""
        from src import main

        source = open(main.__file__).read()

        assert 'logger.error("Pipeline failed:' not in source, (
            "Pipeline error handler still uses logger.error — "
            "should use logger.exception to preserve traceback"
        )
        assert 'logger.error("Failed to send failure notification")' not in source, (
            "Failure notification error handler still uses logger.error — "
            "should use logger.exception to preserve traceback"
        )


class TestDryRunNoGlobalMutation:
    """Task 5: Verify dry_run does not mutate config.DRY_RUN global state."""

    def test_dry_run_does_not_mutate_config(self):
        """main.py must NOT contain 'config.DRY_RUN =' assignment."""
        from src import main

        source = open(main.__file__).read()
        assert "config.DRY_RUN =" not in source, (
            "main.py still mutates config.DRY_RUN global state. "
            "Thread dry_run as a parameter instead."
        )

    @patch("src.main.send_digest")
    @patch("src.main.send_model_updates_to_notion", return_value=0)
    @patch("src.main.send_to_notion")
    @patch("src.main.create_github_issues")
    @patch("src.main.save_seen_ids")
    @patch("src.main.save_daily_articles")
    @patch("src.main.filter_and_summarize")
    @patch("src.main.filter_new_articles")
    @patch("src.main.load_seen_ids")
    @patch("src.main.scrape_all")
    @patch("src.main.fetch_model_data")
    @patch("src.main.save_model_snapshots")
    @patch("src.main.get_model_updates")
    def test_dry_run_skips_all_side_effects(
        self,
        mock_get_model_updates,
        mock_save_snapshots,
        mock_fetch_model,
        mock_scrape,
        mock_load_seen,
        mock_filter_new,
        mock_filter_summarize,
        mock_save_daily,
        mock_save_seen,
        mock_create_issues,
        mock_send_notion,
        mock_send_model_notion,
        mock_send_digest,
        sample_articles,
    ):
        """In dry_run mode, Telegram/Notion/GitHub Issues should be skipped."""
        from src.main import main

        mock_scrape.return_value = sample_articles
        mock_load_seen.return_value = set()
        mock_filter_new.return_value = sample_articles
        mock_filter_summarize.return_value = sample_articles
        mock_get_model_updates.return_value = {"new_models": [], "rank_changes": [], "price_changes": []}

        main(dry_run=True)

        # In dry_run mode, these should NOT be called
        mock_create_issues.assert_not_called()
        mock_send_notion.assert_not_called()
        mock_send_digest.assert_not_called()
        mock_send_model_notion.assert_not_called()
