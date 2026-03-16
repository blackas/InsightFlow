from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/blog-deploy.yml")


def test_blog_workflow_grants_issue_read_permission() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "permissions:" in text
    assert "issues: read" in text
