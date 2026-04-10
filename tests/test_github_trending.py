"""Tests for GitHub Trending repository tracking."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.github_trending import (
    TrendingRepo,
    fetch_github_trending,
    save_daily_trending_repos,
)


_TRENDING_HTML = """
<html>
  <body>
    <article class="Box-row">
      <h2>
        <a href="/owner-one/repo.one">
          owner-one / repo.one
        </a>
      </h2>
      <p>First repo description</p>
      <span itemprop="programmingLanguage">Python</span>
      <a href="/owner-one/repo.one/stargazers">12,345</a>
      <a href="/owner-one/repo.one/forks">678</a>
      <span class="d-inline-block float-sm-right">123 stars today</span>
    </article>
    <article class="Box-row">
      <h2>
        <a href="/owner_two/repo-two">
          owner_two / repo-two
        </a>
      </h2>
      <p>Second repo description</p>
      <a href="/owner_two/repo-two/stargazers">2,000</a>
      <a href="/owner_two/repo-two/forks">50</a>
      <span class="d-inline-block float-sm-right">42 stars today</span>
    </article>
  </body>
</html>
"""


@patch("src.github_trending.requests.get")
def test_fetch_github_trending_parses_repositories(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.text = _TRENDING_HTML
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    repos = fetch_github_trending(count=10)

    assert len(repos) == 2
    assert repos[0] == TrendingRepo(
        name="owner-one/repo.one",
        url="https://github.com/owner-one/repo.one",
        description="First repo description",
        language="Python",
        stars=12345,
        today_stars=123,
        forks=678,
    )
    assert repos[1].name == "owner_two/repo-two"
    assert repos[1].language is None
    assert repos[1].today_stars == 42


@patch("src.github_trending.requests.get")
def test_fetch_github_trending_respects_count(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.text = _TRENDING_HTML
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    repos = fetch_github_trending(count=1)

    assert [repo.name for repo in repos] == ["owner-one/repo.one"]


@patch("src.github_trending.requests.get")
def test_fetch_github_trending_returns_empty_on_network_error(
    mock_get: MagicMock,
) -> None:
    mock_get.side_effect = requests.RequestException("timeout")

    assert fetch_github_trending() == []


@patch("src.github_trending.requests.get")
def test_fetch_github_trending_warns_when_selectors_parse_nothing(
    mock_get: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_resp = MagicMock()
    mock_resp.text = "<html><body>No trending rows</body></html>"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    repos = fetch_github_trending()

    assert repos == []
    assert "selectors may be broken" in caplog.text


def test_save_daily_trending_repos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import src.github_trending as github_trending

    monkeypatch.setattr(github_trending, "DATA_DIR", tmp_path)
    repos = [
        TrendingRepo(
            name="owner/repo",
            url="https://github.com/owner/repo",
            description="Description",
            language="Python",
            stars=10,
            today_stars=2,
            forks=1,
        )
    ]

    path = save_daily_trending_repos(repos, "2026-04-11")

    assert path == tmp_path / "github_trending" / "2026" / "04" / "11.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["name"] == "owner/repo"
