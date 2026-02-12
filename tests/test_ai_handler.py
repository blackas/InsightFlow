"""Tests for src.ai_handler module."""

from unittest.mock import MagicMock, patch, call
import json

import pytest

from src.scraper import Article


def _make_article(source: str, title: str) -> Article:
    """Helper to create test articles with minimal fields."""
    return Article(
        source=source,
        source_id=f"{source}_id_{title}",
        title=title,
        url=f"https://example.com/{title}",
        discussion_url=f"https://example.com/{title}/discuss",
        summary=f"Summary of {title}",
        score=10,
        published_at="2026-02-12",
    )


class TestBatchSeparatesBySource:
    """Task 7: Verify batches are separated by source to use correct prompts."""

    @patch("src.ai_handler.genai")
    def test_batch_separates_by_source(self, mock_genai):
        """When TLDR and HN articles are mixed, they must be sent in separate batches
        with different prompts."""
        from src.ai_handler import batch_summarize
        from src import config

        # Create mixed articles: 3 TLDR + 3 HN
        articles = [
            _make_article("tldrai", "TLDR Article 1"),
            _make_article("hackernews", "HN Article 1"),
            _make_article("tldrai", "TLDR Article 2"),
            _make_article("hackernews", "HN Article 2"),
            _make_article("tldrai", "TLDR Article 3"),
            _make_article("hackernews", "HN Article 3"),
        ]

        # Mock Gemini to track prompts
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        # Return valid JSON responses for each batch call
        def make_response(articles_in_batch):
            data = [{"index": i + 1, "relevance": 0.8, "summary": "요약", "tags": ["AI/ML"]}
                    for i in range(len(articles_in_batch))]
            mock_resp = MagicMock()
            mock_resp.text = json.dumps(data)
            return mock_resp

        # We'll capture calls and return appropriate responses
        prompts_captured = []

        def capture_prompt(prompt):
            prompts_captured.append(prompt)
            # Count articles in this prompt by counting [N] patterns
            import re
            count = len(re.findall(r'\[\d+\]', prompt))
            data = [{"index": i + 1, "relevance": 0.8, "summary": "요약", "tags": ["AI/ML"]}
                    for i in range(count)]
            mock_resp = MagicMock()
            mock_resp.text = json.dumps(data)
            return mock_resp

        mock_model.generate_content.side_effect = capture_prompt

        with patch.object(config, "GEMINI_API_KEY", "fake-key"):
            with patch.object(config, "BATCH_SIZE", 8):  # Large enough to hold all in one batch
                batch_summarize(articles)

        # With 6 articles and BATCH_SIZE=8, if no separation:
        # → 1 batch with mixed articles
        # With proper separation:
        # → 1 batch for TLDR (3 articles), 1 batch for HN (3 articles) = 2 batches
        assert len(prompts_captured) >= 2, (
            f"Expected at least 2 separate batches (TLDR + HN), got {len(prompts_captured)}"
        )

        # Verify TLDR batch uses TLDR prompt (핵심 포인트 추출)
        tldr_prompts = [p for p in prompts_captured if "핵심 포인트 추출" in p]
        other_prompts = [p for p in prompts_captured if "3줄 핵심 요약" in p]

        assert len(tldr_prompts) >= 1, "No TLDR-specific prompt found (should contain '핵심 포인트 추출')"
        assert len(other_prompts) >= 1, "No standard prompt found (should contain '3줄 핵심 요약')"

    @patch("src.ai_handler.genai")
    def test_all_tldrai_batch_uses_tldrai_prompt(self, mock_genai):
        """A batch with only TLDR articles must use TLDR-specific prompt."""
        from src.ai_handler import batch_summarize
        from src import config

        articles = [_make_article("tldrai", f"TLDR {i}") for i in range(3)]

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        prompts_captured = []

        def capture_prompt(prompt):
            prompts_captured.append(prompt)
            data = [{"index": i + 1, "relevance": 0.8, "summary": "요약", "tags": ["AI/ML"]}
                    for i in range(3)]
            mock_resp = MagicMock()
            mock_resp.text = json.dumps(data)
            return mock_resp

        mock_model.generate_content.side_effect = capture_prompt

        with patch.object(config, "GEMINI_API_KEY", "fake-key"):
            batch_summarize(articles)

        assert len(prompts_captured) == 1
        assert "핵심 포인트 추출" in prompts_captured[0], (
            "Pure TLDR batch should use TLDR prompt with '핵심 포인트 추출'"
        )

    @patch("src.ai_handler.genai")
    def test_all_hn_batch_uses_standard_prompt(self, mock_genai):
        """A batch with only HN articles must use standard prompt."""
        from src.ai_handler import batch_summarize
        from src import config

        articles = [_make_article("hackernews", f"HN {i}") for i in range(3)]

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        prompts_captured = []

        def capture_prompt(prompt):
            prompts_captured.append(prompt)
            data = [{"index": i + 1, "relevance": 0.8, "summary": "요약", "tags": ["AI/ML"]}
                    for i in range(3)]
            mock_resp = MagicMock()
            mock_resp.text = json.dumps(data)
            return mock_resp

        mock_model.generate_content.side_effect = capture_prompt

        with patch.object(config, "GEMINI_API_KEY", "fake-key"):
            batch_summarize(articles)

        assert len(prompts_captured) == 1
        assert "3줄 핵심 요약" in prompts_captured[0], (
            "Pure HN batch should use standard prompt with '3줄 핵심 요약'"
        )
