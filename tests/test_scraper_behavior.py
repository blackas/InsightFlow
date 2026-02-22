"""Behavior tests for scraper.py with mocked HTTP calls."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scraper import (
    Article,
    _strip_utm_params,
    fetch_geeknews,
    fetch_hackernews,
    fetch_tldr_ai,
    scrape_all,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_struct_time(dt: datetime) -> time.struct_time:
    """Convert datetime to time.struct_time (like feedparser returns)."""
    return dt.timetuple()


def _make_feed_entry(
    title: str = "Test Article",
    link: str = "https://news.hada.io/topic?id=1",
    entry_id: str = "entry-1",
    published_dt: datetime | None = None,
    content_html: str | None = None,
    summary: str = "A summary",
) -> MagicMock:
    """Build a mock feedparser entry."""
    if published_dt is None:
        published_dt = datetime.now(timezone.utc) - timedelta(hours=1)

    entry = MagicMock()
    entry.get = MagicMock(
        side_effect=lambda key, default=None: {
            "title": title,
            "link": link,
            "id": entry_id,
            "published_parsed": _make_struct_time(published_dt),
            "updated_parsed": None,
            "content": [{"value": content_html}] if content_html else [],
            "summary": summary,
        }.get(key, default)
    )
    return entry


# ---------------------------------------------------------------------------
# GeekNews
# ---------------------------------------------------------------------------


class TestFetchGeeknews:
    """Tests for fetch_geeknews() function."""

    @patch("src.scraper.feedparser.parse")
    def test_parses_feed_entries(self, mock_parse: MagicMock) -> None:
        """Mock feedparser.parse with sample feed -> verify Article objects created."""
        now = datetime.now(timezone.utc) - timedelta(hours=1)
        entry = _make_feed_entry(
            title="GeekNews Title",
            link="https://news.hada.io/topic?id=100",
            entry_id="gn-100",
            published_dt=now,
            summary="Some summary text",
        )
        mock_parse.return_value = MagicMock(bozo=False, entries=[entry])

        articles = fetch_geeknews()

        assert len(articles) == 1
        art = articles[0]
        assert art.source == "geeknews"
        assert art.title == "GeekNews Title"
        assert art.source_id == "gn-100"
        assert art.discussion_url == "https://news.hada.io/topic?id=100"

    @patch("src.scraper.feedparser.parse")
    def test_skips_old_articles(self, mock_parse: MagicMock) -> None:
        """Mock feed with articles older than 24h -> verify filtered out."""
        old_dt = datetime.now(timezone.utc) - timedelta(hours=48)
        new_dt = datetime.now(timezone.utc) - timedelta(hours=1)

        old_entry = _make_feed_entry(title="Old", entry_id="old-1", published_dt=old_dt)
        new_entry = _make_feed_entry(title="New", entry_id="new-1", published_dt=new_dt)

        mock_parse.return_value = MagicMock(bozo=False, entries=[old_entry, new_entry])

        articles = fetch_geeknews()

        assert len(articles) == 1
        assert articles[0].title == "New"

    @patch("src.scraper.feedparser.parse")
    def test_returns_empty_on_network_error(self, mock_parse: MagicMock) -> None:
        """Mock feedparser.parse to raise exception -> verify empty list."""
        mock_parse.side_effect = ValueError("Network timeout")

        articles = fetch_geeknews()

        assert articles == []

    @patch("src.scraper.feedparser.parse")
    def test_extracts_url_from_content(self, mock_parse: MagicMock) -> None:
        """Mock feed entry with HTML content -> verify original_url extracted."""
        now = datetime.now(timezone.utc) - timedelta(hours=1)
        content_html = '<a href="https://example.com/original-article">Read more</a>'
        entry = _make_feed_entry(
            title="Content URL Test",
            link="https://news.hada.io/topic?id=200",
            entry_id="gn-200",
            published_dt=now,
            content_html=content_html,
        )
        mock_parse.return_value = MagicMock(bozo=False, entries=[entry])

        articles = fetch_geeknews()

        assert len(articles) == 1
        # url should be extracted from content, not the discussion link
        assert articles[0].url == "https://example.com/original-article"
        assert articles[0].discussion_url == "https://news.hada.io/topic?id=200"


# ---------------------------------------------------------------------------
# HackerNews
# ---------------------------------------------------------------------------


class TestFetchHackernews:
    """Tests for fetch_hackernews() function."""

    @pytest.mark.asyncio
    async def test_returns_articles(self) -> None:
        """Mock aiohttp session -> verify Article objects with correct fields."""
        # Build mock responses
        topstories_resp = AsyncMock()
        topstories_resp.status = 200
        topstories_resp.json = AsyncMock(return_value=[101, 102])

        ts = int(datetime.now(timezone.utc).timestamp())
        item_101_resp = AsyncMock()
        item_101_resp.status = 200
        item_101_resp.json = AsyncMock(
            return_value={
                "type": "story",
                "title": "HN Story 101",
                "url": "https://example.com/101",
                "score": 250,
                "time": ts,
            }
        )

        item_102_resp = AsyncMock()
        item_102_resp.status = 200
        item_102_resp.json = AsyncMock(
            return_value={
                "type": "story",
                "title": "HN Story 102",
                "url": "https://example.com/102",
                "score": 180,
                "time": ts,
            }
        )

        # Map URLs to responses
        def mock_get(url: str) -> AsyncMock:
            if "topstories" in url:
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=topstories_resp)
                ctx.__aexit__ = AsyncMock(return_value=False)
                return ctx
            if "101.json" in url:
                ctx = AsyncMock()
                ctx.__aenter__ = AsyncMock(return_value=item_101_resp)
                ctx.__aexit__ = AsyncMock(return_value=False)
                return ctx
            # 102
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=item_102_resp)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        mock_session = MagicMock()
        mock_session.get = mock_get

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.scraper.aiohttp.ClientSession", return_value=session_ctx):
            articles = await fetch_hackernews(count=2)

        assert len(articles) == 2
        assert articles[0].source == "hackernews"
        assert articles[0].title == "HN Story 101"
        assert articles[0].url == "https://example.com/101"
        assert articles[0].score == 250

    @pytest.mark.asyncio
    async def test_skips_non_story_items(self) -> None:
        """Mock HN item with type != 'story' -> verify skipped."""
        topstories_resp = AsyncMock()
        topstories_resp.status = 200
        topstories_resp.json = AsyncMock(return_value=[201])

        item_resp = AsyncMock()
        item_resp.status = 200
        item_resp.json = AsyncMock(
            return_value={
                "type": "comment",
                "title": "Not a story",
                "time": 0,
            }
        )

        def mock_get(url: str) -> AsyncMock:
            resp = topstories_resp if "topstories" in url else item_resp
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=resp)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        mock_session = MagicMock()
        mock_session.get = mock_get

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.scraper.aiohttp.ClientSession", return_value=session_ctx):
            articles = await fetch_hackernews(count=1)

        assert articles == []

    @pytest.mark.asyncio
    async def test_handles_api_failure(self) -> None:
        """Mock aiohttp to return non-200 -> verify empty list."""
        topstories_resp = AsyncMock()
        topstories_resp.status = 500

        def mock_get(url: str) -> AsyncMock:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=topstories_resp)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        mock_session = MagicMock()
        mock_session.get = mock_get

        session_ctx = AsyncMock()
        session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.scraper.aiohttp.ClientSession", return_value=session_ctx):
            articles = await fetch_hackernews(count=5)

        assert articles == []


# ---------------------------------------------------------------------------
# TLDR AI
# ---------------------------------------------------------------------------

_TLDR_HTML_TEMPLATE = """
<html><body>
<section>
  <header><h3>{section_name}</h3></header>
  {articles}
</section>
</body></html>
"""

_TLDR_ARTICLE_TEMPLATE = """
<article>
  <a class="font-bold" href="{url}">
    <h3>{title}</h3>
  </a>
  <div class="newsletter-html">{summary}</div>
</article>
"""


def _build_tldr_html(
    section_name: str = "Headlines & Launches",
    articles: list[dict[str, str]] | None = None,
) -> str:
    if articles is None:
        articles = [
            {
                "title": "TLDR Article 1",
                "url": "https://example.com/tldr1",
                "summary": "Summary of article 1",
            }
        ]
    article_html = "\n".join(_TLDR_ARTICLE_TEMPLATE.format(**a) for a in articles)
    return _TLDR_HTML_TEMPLATE.format(section_name=section_name, articles=article_html)


class TestFetchTldrAi:
    """Tests for fetch_tldr_ai() function."""

    @patch("src.scraper.requests.get")
    def test_parses_html(
        self, mock_get: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mock requests.get -> verify articles parsed from HTML."""
        from src import config

        monkeypatch.setattr(
            config, "TLDR_SECTIONS", frozenset({"Headlines & Launches"})
        )

        mock_resp = MagicMock()
        mock_resp.text = _build_tldr_html(
            section_name="Headlines & Launches",
            articles=[
                {
                    "title": "AI Breakthrough",
                    "url": "https://example.com/ai",
                    "summary": "Big news",
                },
            ],
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        articles = fetch_tldr_ai()

        assert len(articles) == 1
        assert articles[0].source == "tldrai"
        assert articles[0].title == "AI Breakthrough"
        assert articles[0].url == "https://example.com/ai"
        assert articles[0].summary == "Big news"

    @patch("src.scraper.requests.get")
    def test_skips_sponsor_articles(
        self, mock_get: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mock HTML with (Sponsor) title -> verify skipped."""
        from src import config

        monkeypatch.setattr(
            config, "TLDR_SECTIONS", frozenset({"Headlines & Launches"})
        )

        mock_resp = MagicMock()
        mock_resp.text = _build_tldr_html(
            section_name="Headlines & Launches",
            articles=[
                {
                    "title": "Sponsored Tool (Sponsor)",
                    "url": "https://sponsor.com",
                    "summary": "Ad",
                },
                {
                    "title": "Real Article",
                    "url": "https://example.com/real",
                    "summary": "Content",
                },
            ],
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        articles = fetch_tldr_ai()

        assert len(articles) == 1
        assert articles[0].title == "Real Article"

    def test_strips_utm_params(self) -> None:
        """Verify _strip_utm_params removes utm_* query params."""
        url = "https://example.com/page?utm_source=newsletter&utm_medium=email&ref=home"
        cleaned = _strip_utm_params(url)

        assert "utm_source" not in cleaned
        assert "utm_medium" not in cleaned
        assert "ref=home" in cleaned
        assert cleaned.startswith("https://example.com/page")


# ---------------------------------------------------------------------------
# scrape_all
# ---------------------------------------------------------------------------


class TestScrapeAll:
    """Tests for scrape_all() function."""

    @pytest.mark.asyncio
    async def test_combines_all_sources(self) -> None:
        """Mock all three fetch functions -> verify combined list."""
        gn_article = Article(
            source="geeknews",
            source_id="gn-1",
            title="GN Art",
            url="https://gn.com/1",
            discussion_url="https://gn.com/1",
            summary="gn",
            score=0,
            published_at=datetime.now(timezone.utc).isoformat(),
        )
        hn_article = Article(
            source="hackernews",
            source_id="hn-1",
            title="HN Art",
            url="https://hn.com/1",
            discussion_url="https://hn.com/1",
            summary="hn",
            score=100,
            published_at=datetime.now(timezone.utc).isoformat(),
        )
        tldr_article = Article(
            source="tldrai",
            source_id="tldr-1",
            title="TLDR Art",
            url="https://tldr.com/1",
            discussion_url="https://tldr.com/1",
            summary="tldr",
            score=0,
            published_at=datetime.now(timezone.utc).isoformat(),
        )

        with (
            patch("src.scraper.fetch_geeknews", return_value=[gn_article]),
            patch("src.scraper.fetch_hackernews", AsyncMock(return_value=[hn_article])),
            patch("src.scraper.fetch_tldr_ai", return_value=[tldr_article]),
        ):
            result = await scrape_all()

        assert len(result) == 3
        sources = {a.source for a in result}
        assert sources == {"geeknews", "hackernews", "tldrai"}
