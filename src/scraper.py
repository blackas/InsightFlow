from __future__ import annotations

import asyncio
import calendar
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import cast

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import aiohttp
import feedparser
import requests
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

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
    tags: list[str] = field(default_factory=list)


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
                pub_dt = datetime.fromtimestamp(
                    calendar.timegm(cast(time.struct_time, published)),
                    tz=timezone.utc,
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
            summary="",
            score=data.get("score", 0),
            published_at=published_iso,
        )

    except Exception:
        logger.warning("Failed to fetch HN item %d", item_id)
        return None


async def fetch_hackernews(count: int = 30) -> list[Article]:
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            top_url = f"{config.HN_API_BASE}topstories.json"
            async with session.get(top_url) as resp:
                if resp.status != 200:
                    logger.error("Failed to fetch HN top stories: HTTP %d", resp.status)
                    return []
                story_ids = await resp.json()

            story_ids = story_ids[:count]
            tasks = [_fetch_hn_item(session, sid) for sid in story_ids]
            results = await asyncio.gather(*tasks)

        articles = [a for a in results if a is not None]
        logger.info("Fetched %d articles from Hacker News", len(articles))
        return articles

    except Exception:
        logger.exception("Error fetching Hacker News")
        return []


TLDR_AI_URL = "https://tldr.tech/api/latest/ai"

TLDR_SECTIONS = {
    "Headlines & Launches",
    "Deep Dives & Analysis",
    "Engineering & Research",
    "Miscellaneous",
    "Quick Links",
}


def _strip_utm_params(url: str) -> str:
    """Remove all utm_* query parameters from a URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    cleaned = {k: v for k, v in params.items() if not k.startswith("utm_")}
    new_query = urlencode(cleaned, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def fetch_tldr_ai() -> list[Article]:
    """Fetch and parse articles from the TLDR AI newsletter."""
    try:
        resp = requests.get(
            TLDR_AI_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        articles: list[Article] = []

        for section in soup.find_all("section"):
            header = section.find("header")
            if not header:
                continue

            h3_header = header.find("h3")
            if not h3_header:
                continue

            section_name = h3_header.get_text(strip=True)
            if section_name not in TLDR_SECTIONS:
                continue

            for article_tag in section.find_all("article"):
                link_tag = article_tag.find("a", class_="font-bold")
                if not link_tag:
                    continue

                title_tag = link_tag.find("h3")
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)

                if "(Sponsor)" in title:
                    continue

                raw_url = link_tag.get("href", "")
                if not raw_url:
                    continue

                clean_url = _strip_utm_params(raw_url)

                desc_div = article_tag.find("div", class_="newsletter-html")
                summary = desc_div.get_text(strip=True)[:500] if desc_div else ""

                articles.append(
                    Article(
                        source="tldrai",
                        source_id=clean_url,
                        title=title,
                        url=clean_url,
                        discussion_url=clean_url,
                        summary=summary,
                        score=0,
                        published_at=today_iso,
                    )
                )

        logger.info("Fetched %d articles from TLDR AI", len(articles))
        return articles

    except Exception:
        logger.exception("Error fetching TLDR AI newsletter")
        return []


async def scrape_all() -> list[Article]:
    loop = asyncio.get_event_loop()
    geeknews_task = loop.run_in_executor(None, fetch_geeknews)
    hackernews_task = fetch_hackernews(count=config.HN_TOP_N)
    tldrai_task = loop.run_in_executor(None, fetch_tldr_ai)

    geeknews_articles, hackernews_articles, tldrai_articles = await asyncio.gather(
        geeknews_task, hackernews_task, tldrai_task
    )

    all_articles = geeknews_articles + hackernews_articles + tldrai_articles
    logger.info(
        "Total articles collected: %d (GeekNews: %d, HN: %d, TLDR AI: %d)",
        len(all_articles),
        len(geeknews_articles),
        len(hackernews_articles),
        len(tldrai_articles),
    )
    return all_articles
