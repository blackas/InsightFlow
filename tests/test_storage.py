"""Behavior tests for storage.py with isolated file I/O."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.scraper import Article
from src.storage import (
    create_github_issues,
    filter_new_articles,
    load_seen_ids,
    save_daily_articles,
    save_seen_ids,
)


class TestLoadSeenIds:
    """Tests for load_seen_ids() function."""

    def test_returns_set_from_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Create seen_ids.json with known IDs → verify set returned."""
        import src.storage as storage

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        seen_file = data_dir / "seen_ids.json"
        seen_file.write_text(json.dumps(["id1", "id2"]), encoding="utf-8")

        monkeypatch.setattr(storage, "DATA_DIR", data_dir)
        monkeypatch.setattr(storage, "SEEN_IDS_PATH", seen_file)

        result = load_seen_ids()
        assert result == {"id1", "id2"}

    def test_returns_empty_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """No file exists → verify empty set returned."""
        import src.storage as storage

        missing_path = tmp_path / "nonexistent" / "seen_ids.json"
        monkeypatch.setattr(storage, "SEEN_IDS_PATH", missing_path)

        result = load_seen_ids()
        assert result == set()

    def test_returns_empty_on_corrupt_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """File contains invalid JSON → verify empty set, no crash."""
        import src.storage as storage

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        corrupt_file = data_dir / "seen_ids.json"
        corrupt_file.write_text("{not valid json!!!", encoding="utf-8")

        monkeypatch.setattr(storage, "DATA_DIR", data_dir)
        monkeypatch.setattr(storage, "SEEN_IDS_PATH", corrupt_file)

        result = load_seen_ids()
        assert result == set()


class TestSaveSeenIds:
    """Tests for save_seen_ids() function."""

    def test_writes_sorted_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Save set → read file → verify sorted JSON list."""
        import src.storage as storage

        data_dir = tmp_path / "data"
        seen_file = data_dir / "seen_ids.json"

        monkeypatch.setattr(storage, "DATA_DIR", data_dir)
        monkeypatch.setattr(storage, "SEEN_IDS_PATH", seen_file)

        save_seen_ids({"cherry", "apple", "banana"})

        assert seen_file.exists()
        content = json.loads(seen_file.read_text(encoding="utf-8"))
        assert content == ["apple", "banana", "cherry"]

    def test_creates_data_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Save when data dir doesn't exist → verify directory created."""
        import src.storage as storage

        data_dir = tmp_path / "new_data"
        seen_file = data_dir / "seen_ids.json"

        monkeypatch.setattr(storage, "DATA_DIR", data_dir)
        monkeypatch.setattr(storage, "SEEN_IDS_PATH", seen_file)

        save_seen_ids({"test"})

        assert data_dir.exists()
        assert seen_file.exists()


class TestFilterNewArticles:
    """Tests for filter_new_articles() function."""

    def test_returns_only_unseen(self, sample_article: Article):
        """Pass articles with some IDs in seen_ids → verify only new returned."""
        seen_ids: set[str] = {"hackernews:12345"}

        new_article = Article(
            source="hackernews",
            source_id="99999",
            title="New Article",
            url="https://example.com/new",
            discussion_url="https://news.ycombinator.com/item?id=99999",
            summary="New article summary",
            score=50,
            published_at="2026-02-17T00:00:00Z",
        )

        result = filter_new_articles([sample_article, new_article], seen_ids)

        assert len(result) == 1
        assert result[0].source_id == "99999"

    def test_adds_to_seen_ids(self, sample_article: Article):
        """Verify side effect: new IDs added to seen_ids set."""
        seen_ids: set[str] = set()

        filter_new_articles([sample_article], seen_ids)

        assert "hackernews:12345" in seen_ids


class TestSaveDailyArticles:
    """Tests for save_daily_articles() function."""

    def test_creates_directory_structure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_article: Article
    ):
        """Save with date 2026-02-17 → verify data/2026/02/17.json created."""
        import src.storage as storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)

        result = save_daily_articles([sample_article], "2026-02-17")

        expected_path = tmp_path / "2026" / "02" / "17.json"
        assert result == expected_path
        assert expected_path.exists()

        content = json.loads(expected_path.read_text(encoding="utf-8"))
        assert len(content) == 1
        assert content[0]["title"] == "Sample HN Article"

    def test_appends_to_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_article: Article
    ):
        """File already has articles → verify new articles appended."""
        import src.storage as storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)

        # Create existing file with one article
        dir_path = tmp_path / "2026" / "02"
        dir_path.mkdir(parents=True)
        existing_article = {
            "source": "geeknews",
            "source_id": "existing-1",
            "title": "Existing Article",
        }
        file_path = dir_path / "17.json"
        file_path.write_text(json.dumps([existing_article]), encoding="utf-8")

        save_daily_articles([sample_article], "2026-02-17")

        content = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(content) == 2
        assert content[0]["title"] == "Existing Article"
        assert content[1]["title"] == "Sample HN Article"

    def test_invalid_date_format_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_article: Article
    ):
        """Invalid date format → verify ValueError raised."""
        import src.storage as storage

        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)

        with pytest.raises(ValueError, match="Invalid date format"):
            save_daily_articles([sample_article], "2026-13")


class TestCreateGitHubIssues:
    """Tests for create_github_issues() function."""

    def test_skips_in_dry_run(self, monkeypatch: pytest.MonkeyPatch):
        """DRY_RUN=True → verify no API calls made."""
        from src import config

        monkeypatch.setattr(config, "DRY_RUN", True)

        result = create_github_issues([])
        assert result == 0

    def test_skips_without_credentials(self, monkeypatch: pytest.MonkeyPatch):
        """No GITHUB_TOKEN → verify returns 0 without API calls."""
        from src import config

        monkeypatch.setattr(config, "DRY_RUN", False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        result = create_github_issues([])
        assert result == 0

    @patch("src.storage.requests.post")
    def test_creates_for_notable_articles(
        self,
        mock_post: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        sample_article: Article,
    ):
        """Mock requests.post → verify issue created with correct payload."""
        from src import config

        monkeypatch.setattr(config, "DRY_RUN", False)
        monkeypatch.setattr(config, "ISSUE_THRESHOLD", 0.5)
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")

        sample_article.relevance_score = 0.9
        sample_article.ai_summary = "Test AI summary"

        mock_response = MagicMock()
        mock_response.json.return_value = {"number": 42}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = create_github_issues([sample_article])

        assert result == 1
        mock_post.assert_called_once()

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["title"] == "[hackernews] Sample HN Article"
        assert "auto-collected" in payload["labels"]
        assert "source:hackernews" in payload["labels"]

        headers = call_kwargs.kwargs["headers"]
        assert headers["Authorization"] == "Bearer fake-token"

    @patch("src.storage.requests.post")
    def test_skips_below_threshold(
        self,
        mock_post: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        sample_article: Article,
    ):
        """Articles below ISSUE_THRESHOLD → verify no API call."""
        from src import config

        monkeypatch.setattr(config, "DRY_RUN", False)
        monkeypatch.setattr(config, "ISSUE_THRESHOLD", 0.8)
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")

        sample_article.relevance_score = 0.3

        result = create_github_issues([sample_article])

        assert result == 0
        mock_post.assert_not_called()
