"""Tests for blog_builder module — static blog from GitHub Issues."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.blog_builder import (
    build_blog,
    extract_title_and_source,
    fetch_open_issues,
    parse_issue_body,
    render_article_html,
    render_index_html,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ISSUE_BODY = (
    "## 기사 정보\n"
    "- **원본 URL**: https://example.com/article\n"
    "- **토론**: https://news.hada.io/topic?id=67890\n"
    "- **소스**: geeknews\n"
    "- **관련성 점수**: 0.92\n"
    "\n"
    "## AI 요약\n"
    "첫 번째 요약 문장입니다.\n"
    "두 번째 요약 문장입니다.\n"
    "세 번째 요약 문장입니다.\n"
)

SAMPLE_ISSUE: dict[str, Any] = {
    "number": 42,
    "title": "[geeknews] WebMCP 공개",
    "body": SAMPLE_ISSUE_BODY,
    "labels": [{"name": "source:geeknews"}, {"name": "auto-collected"}],
    "state": "OPEN",
    "createdAt": "2026-02-21T23:28:00Z",
}

@pytest.fixture
def sample_issue() -> dict[str, Any]:
    return SAMPLE_ISSUE.copy()


@pytest.fixture
def sample_issues() -> list[dict[str, Any]]:
    return [
        SAMPLE_ISSUE.copy(),
        {
            "number": 43,
            "title": "[hackernews] Rust 2.0 발표",
            "body": (
                "## 기사 정보\n"
                "- **원본 URL**: https://example.com/rust\n"
                "- **토론**: https://news.ycombinator.com/item?id=99999\n"
                "- **소스**: hackernews\n"
                "- **관련성 점수**: 0.88\n"
                "\n"
                "## AI 요약\n"
                "Rust 2.0이 발표되었습니다.\n"
            ),
            "labels": [{"name": "source:hackernews"}, {"name": "auto-collected"}],
            "state": "OPEN",
            "createdAt": "2026-02-22T10:00:00Z",
        },
    ]


# ---------------------------------------------------------------------------
# parse_issue_body
# ---------------------------------------------------------------------------


class TestParseIssueBody:
    def test_extracts_all_fields(self) -> None:
        result = parse_issue_body(SAMPLE_ISSUE_BODY)
        assert result["url"] == "https://example.com/article"
        assert result["discussion_url"] == "https://news.hada.io/topic?id=67890"
        assert result["source"] == "geeknews"
        assert result["relevance_score"] == 0.92
        assert "첫 번째 요약 문장입니다." in result["ai_summary"]
        assert "세 번째 요약 문장입니다." in result["ai_summary"]

    def test_empty_body_returns_defaults(self) -> None:
        result = parse_issue_body("")
        assert result["url"] == ""
        assert result["discussion_url"] == ""
        assert result["source"] == ""
        assert result["relevance_score"] == 0.0
        assert result["ai_summary"] == ""

    def test_partial_body(self) -> None:
        body = "## 기사 정보\n- **원본 URL**: https://only-url.com\n"
        result = parse_issue_body(body)
        assert result["url"] == "https://only-url.com"
        assert result["source"] == ""

    def test_multiline_summary_preserves_lines(self) -> None:
        result = parse_issue_body(SAMPLE_ISSUE_BODY)
        lines = result["ai_summary"].split("\n")
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# extract_title_and_source
# ---------------------------------------------------------------------------


class TestExtractTitleAndSource:
    def test_standard_format(self) -> None:
        title, source = extract_title_and_source("[geeknews] WebMCP 공개")
        assert title == "WebMCP 공개"
        assert source == "geeknews"

    def test_hackernews_format(self) -> None:
        title, source = extract_title_and_source("[hackernews] Rust 2.0 발표")
        assert title == "Rust 2.0 발표"
        assert source == "hackernews"

    def test_no_bracket_returns_full_title(self) -> None:
        title, source = extract_title_and_source("Plain Title")
        assert title == "Plain Title"
        assert source == "unknown"


# ---------------------------------------------------------------------------
# fetch_open_issues
# ---------------------------------------------------------------------------


class TestFetchOpenIssues:
    @patch("src.blog_builder.subprocess.run")
    def test_fetches_issues_via_gh_cli(self, mock_run: MagicMock) -> None:
        issues = [SAMPLE_ISSUE]
        mock_run.return_value = MagicMock(stdout=json.dumps(issues), returncode=0)
        result = fetch_open_issues()
        assert len(result) == 1
        assert result[0]["number"] == 42
        mock_run.assert_called_once()
        # Verify gh cli is called with correct args
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "issue" in call_args
        assert "list" in call_args

    @patch("src.blog_builder.subprocess.run")
    def test_raises_on_cli_failure(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "gh")
        with pytest.raises(RuntimeError, match="Failed to fetch GitHub issues"):
            fetch_open_issues()

    @patch("src.blog_builder.subprocess.run")
    def test_raises_on_invalid_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="not json", returncode=0)
        with pytest.raises(RuntimeError, match="Failed to parse GitHub issues JSON"):
            fetch_open_issues()


# ---------------------------------------------------------------------------
# render_article_html
# ---------------------------------------------------------------------------


class TestRenderArticleHtml:
    def test_contains_title(self, sample_issue: dict[str, Any]) -> None:
        html = render_article_html(sample_issue)
        assert "WebMCP 공개" in html

    def test_contains_article_url(self, sample_issue: dict[str, Any]) -> None:
        html = render_article_html(sample_issue)
        assert "https://example.com/article" in html

    def test_contains_ai_summary(self, sample_issue: dict[str, Any]) -> None:
        html = render_article_html(sample_issue)
        assert "첫 번째 요약 문장입니다." in html

    def test_does_not_render_mark_as_read_button(
        self, sample_issue: dict[str, Any]
    ) -> None:
        html = render_article_html(sample_issue)
        assert "읽음" not in html
        assert "/close/42" not in html

    def test_contains_source_badge(self, sample_issue: dict[str, Any]) -> None:
        html = render_article_html(sample_issue)
        assert "geeknews" in html

    def test_is_valid_html(self, sample_issue: dict[str, Any]) -> None:
        html = render_article_html(sample_issue)
        assert html.strip().startswith("<!DOCTYPE html>") or html.strip().startswith(
            "<!"
        )
        assert "</html>" in html

    def test_contains_discussion_url(self, sample_issue: dict[str, Any]) -> None:
        html = render_article_html(sample_issue)
        assert "https://news.hada.io/topic?id=67890" in html

    def test_escapes_xss_in_title(self) -> None:
        malicious_issue: dict[str, Any] = {
            "number": 99,
            "title": '[geeknews] <script>alert("xss")</script>',
            "body": SAMPLE_ISSUE_BODY,
            "labels": [{"name": "auto-collected"}],
            "state": "OPEN",
            "createdAt": "2026-02-21T00:00:00Z",
        }
        result = render_article_html(malicious_issue)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_rejects_javascript_url_scheme(self) -> None:
        malicious_issue: dict[str, Any] = {
            "number": 99,
            "title": "[geeknews] Test",
            "body": (
                "## 기사 정보\n"
                "- **원본 URL**: javascript:alert(1)\n"
                "- **토론**: https://safe.example.com\n"
                "- **소스**: geeknews\n"
                "- **관련성 점수**: 0.5\n"
                "\n"
                "## AI 요약\nTest summary.\n"
            ),
            "labels": [{"name": "auto-collected"}],
            "state": "OPEN",
            "createdAt": "2026-02-21T00:00:00Z",
        }
        result = render_article_html(malicious_issue)
        assert "javascript:alert" not in result

    def test_never_renders_close_form(self, sample_issue: dict[str, Any]) -> None:
        result = render_article_html(sample_issue)
        assert 'method="POST"' not in result
        assert "<form" not in result


# ---------------------------------------------------------------------------
# render_index_html
# ---------------------------------------------------------------------------


class TestRenderIndexHtml:
    def test_contains_all_article_titles(
        self, sample_issues: list[dict[str, Any]]
    ) -> None:
        html = render_index_html(sample_issues)
        assert "WebMCP 공개" in html
        assert "Rust 2.0 발표" in html

    def test_links_to_article_pages(self, sample_issues: list[dict[str, Any]]) -> None:
        html = render_index_html(sample_issues)
        assert "42.html" in html
        assert "43.html" in html

    def test_empty_issues_shows_message(self) -> None:
        html = render_index_html([])
        assert "html" in html.lower()
        # Should still produce valid HTML even with no issues

    def test_is_valid_html(self, sample_issues: list[dict[str, Any]]) -> None:
        html = render_index_html(sample_issues)
        assert "</html>" in html

    def test_sorted_by_date_newest_first(
        self, sample_issues: list[dict[str, Any]]
    ) -> None:
        html = render_index_html(sample_issues)
        # Issue 43 (2026-02-22) should appear before Issue 42 (2026-02-21)
        pos_rust = html.index("Rust 2.0 발표")
        pos_webmcp = html.index("WebMCP 공개")
        assert pos_rust < pos_webmcp

    def test_contains_source_badges(self, sample_issues: list[dict[str, Any]]) -> None:
        html = render_index_html(sample_issues)
        assert "geeknews" in html
        assert "hackernews" in html


# ---------------------------------------------------------------------------
# build_blog (integration)
# ---------------------------------------------------------------------------


class TestBuildBlog:
    @patch("src.blog_builder.fetch_open_issues")
    def test_creates_output_files(
        self,
        mock_fetch: MagicMock,
        sample_issues: list[dict[str, Any]],
        tmp_path: Path,
    ) -> None:
        mock_fetch.return_value = sample_issues
        build_blog(str(tmp_path))

        assert (tmp_path / "index.html").exists()
        assert (tmp_path / "42.html").exists()
        assert (tmp_path / "43.html").exists()

    @patch("src.blog_builder.fetch_open_issues")
    def test_creates_output_dir_if_missing(
        self,
        mock_fetch: MagicMock,
        sample_issues: list[dict[str, Any]],
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "blog_output"
        mock_fetch.return_value = sample_issues
        build_blog(str(output))
        assert output.exists()
        assert (output / "index.html").exists()

    @patch("src.blog_builder.fetch_open_issues")
    def test_empty_issues_still_creates_index(
        self,
        mock_fetch: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_fetch.return_value = []
        build_blog(str(tmp_path))
        assert (tmp_path / "index.html").exists()

    @patch("src.blog_builder.fetch_open_issues")
    def test_article_html_content(
        self,
        mock_fetch: MagicMock,
        sample_issues: list[dict[str, Any]],
        tmp_path: Path,
    ) -> None:
        mock_fetch.return_value = sample_issues
        build_blog(str(tmp_path))

        article_html = (tmp_path / "42.html").read_text(encoding="utf-8")
        assert "WebMCP 공개" in article_html
        assert "/close/42" not in article_html

    @patch("src.blog_builder.fetch_open_issues")
    def test_propagates_fetch_failures(
        self,
        mock_fetch: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_fetch.side_effect = RuntimeError("Failed to fetch GitHub issues")
        with pytest.raises(RuntimeError, match="Failed to fetch GitHub issues"):
            build_blog(str(tmp_path))
