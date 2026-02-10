import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp
import feedparser

from src import config

logger = logging.getLogger(__name__)

USER_AGENT = "InsightFlow/1.0 (GitHub Actions; +https://github.com)"


@dataclass
class Article:
    source: str  # "geeknews" | "hackernews"
    source_id: str
    title: str
    url: str  # original article URL
    discussion_url: str
    summary: str
    score: int
    published_at: str  # ISO 8601
    ai_summary: str = ""
    relevance_score: float = 0.0
    notable: bool = False


def _extract_url_from_content(content_html: str) -> str | None:
    match = re.search(r'href=["\']([^"\']+)["\']', content_html)
    if match:
        url = match.group(1)
        # Skip anchor links and javascript: schemes
        if url.startswith(("http://", "https://")):
            return url
    return None


def fetch_geeknews() -> list[Article]:
    try:
        feed = feedparser.parse(
            config.GEEKNEWS_RSS_URL,
            request_headers={"User-Agent": USER_AGENT},
        )

        if feed.bozo and not feed.entries:
            logger.error("Failed to parse GeekNews feed: %s", feed.bozo_exception)
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        articles: list[Article] = []

        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_dt = datetime(
                    year=int(published[0]),
                    month=int(published[1]),
                    day=int(published[2]),
                    hour=int(published[3]),
                    minute=int(published[4]),
                    second=int(published[5]),
                    tzinfo=timezone.utc,
                )
                if pub_dt < cutoff:
                    continue
                published_iso = pub_dt.isoformat()
            else:
                published_iso = datetime.now(timezone.utc).isoformat()

            discussion_url: str = str(entry.get("link", ""))

            original_url = discussion_url
            content_list = entry.get("content", [])
            if content_list:
                content_html: str = str(content_list[0].get("value", ""))
                extracted = _extract_url_from_content(content_html)
                if extracted:
                    original_url = extracted
                summary = re.sub(r"<[^>]+>", "", content_html).strip()[:500]
            else:
                summary = str(entry.get("summary", ""))

            source_id: str = str(entry.get("id", discussion_url))

            articles.append(
                Article(
                    source="geeknews",
                    source_id=source_id,
                    title=str(entry.get("title", "")),
                    url=original_url,
                    discussion_url=discussion_url,
                    summary=summary,
                    score=0,
                    published_at=published_iso,
                )
            )

        logger.info("Fetched %d articles from GeekNews", len(articles))
        return articles

    except Exception:
        logger.exception("Error fetching GeekNews feed")
        return []


async def _fetch_hn_item(
    session: aiohttp.ClientSession, item_id: int
) -> Article | None:
    """Fetch a single HN item by ID."""
    url = f"{config.HN_API_BASE}item/{item_id}.json"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

        if not data or data.get("type") != "story":
            return None

        title = data.get("title", "")
        item_url = data.get("url", "")
        discussion_url = f"https://news.ycombinator.com/item?id={item_id}"

        # Self-posts have no external URL
        if not item_url:
            item_url = discussion_url

        timestamp = data.get("time", 0)
        published_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

        return Article(
            source="hackernews",
            source_id=str(item_id),
            title=title,
            url=item_url,
            discussion_url=discussion_url,
            summary="",  # HN API doesn't provide summaries
            score=data.get("score", 0),
            published_at=published_iso,
        )

    except Exception:
        logger.warning("Failed to fetch HN item %d", item_id)
        return None


async def fetch_hackernews(count: int = 30) -> list[Article]:
    """Fetch top stories from Hacker News API using async parallel requests.

    Args:
        count: Number of top stories to fetch (default: 30).

    Returns:
        List of Article objects. Failed individual items are skipped.
        Returns empty list on complete failure.
    """
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            # Step 1: Get top story IDs
            top_url = f"{config.HN_API_BASE}topstories.json"
            async with session.get(top_url) as resp:
                if resp.status != 200:
                    logger.error("Failed to fetch HN top stories: HTTP %d", resp.status)
                    return []
                story_ids = await resp.json()

            # Take top `count` IDs
            story_ids = story_ids[:count]

            # Step 2: Fetch items in parallel
            tasks = [_fetch_hn_item(session, sid) for sid in story_ids]
            results = await asyncio.gather(*tasks)

        articles = [a for a in results if a is not None]
        logger.info("Fetched %d articles from Hacker News", len(articles))
        return articles

    except Exception:
        logger.exception("Error fetching Hacker News")
        return []


async def scrape_all() -> list[Article]:
    """Fetch articles from all sources and combine results.

    Each source fails independently - a failure in one source
    does not affect the other.
    """
    # Run GeekNews (sync) in executor to not block event loop
    loop = asyncio.get_event_loop()
    geeknews_task = loop.run_in_executor(None, fetch_geeknews)
    hackernews_task = fetch_hackernews(count=config.HN_TOP_N)

    geeknews_articles, hackernews_articles = await asyncio.gather(
        geeknews_task, hackernews_task
    )

    all_articles = geeknews_articles + hackernews_articles
    logger.info(
        "Total articles collected: %d (GeekNews: %d, HN: %d)",
        len(all_articles),
        len(geeknews_articles),
        len(hackernews_articles),
    )
    return all_articles
