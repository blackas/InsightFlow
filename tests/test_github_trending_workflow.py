from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/github-trending.yml")


def test_github_trending_workflow_is_manual_only() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text


def test_github_trending_workflow_uses_minimal_permissions() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "issues: write" not in text


def test_github_trending_workflow_only_sends_trending_digest() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "fetch_github_trending" in text
    assert "send_digest([], trending_repos=repos)" in text
    assert "python -m src.main" not in text
    assert "git add data/" not in text
