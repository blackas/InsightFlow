"""Tests for src.scraper module."""

import pytest


class TestTldrConfigDuplication:
    """Task 4: Verify scraper uses config module values, not local duplicates."""

    def test_tldr_uses_config_values(self, monkeypatch):
        """scraper should use config.TLDR_AI_URL and config.TLDR_SECTIONS, not local copies."""
        from src import config

        # Change config values to sentinel values
        monkeypatch.setattr(config, "TLDR_AI_URL", "https://sentinel-url.test/api")
        monkeypatch.setattr(config, "TLDR_SECTIONS", frozenset({"Sentinel Section"}))

        # Re-import to check: if scraper uses config.TLDR_AI_URL at call time,
        # the monkeypatched value should be picked up
        from src import scraper

        # Verify scraper module does NOT have its own TLDR_AI_URL / TLDR_SECTIONS
        import ast

        source = open(scraper.__file__).read()
        tree = ast.parse(source)

        module_level_assigns = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_level_assigns.append(target.id)

        assert "TLDR_AI_URL" not in module_level_assigns, (
            "TLDR_AI_URL is defined locally in scraper.py — should use config.TLDR_AI_URL"
        )
        assert "TLDR_SECTIONS" not in module_level_assigns, (
            "TLDR_SECTIONS is defined locally in scraper.py — should use config.TLDR_SECTIONS"
        )


class TestModernAsyncio:
    """Task 6: Verify scraper uses asyncio.to_thread instead of deprecated get_event_loop."""

    def test_scrape_all_uses_modern_asyncio(self):
        """src/scraper.py must NOT contain get_event_loop (deprecated since Python 3.10)."""
        from src import scraper

        source = open(scraper.__file__).read()
        assert "get_event_loop" not in source, (
            "scraper.py still uses deprecated asyncio.get_event_loop(). "
            "Use asyncio.to_thread() instead."
        )
        assert "to_thread" in source, (
            "scraper.py should use asyncio.to_thread() for running sync functions."
        )
