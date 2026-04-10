"""GitHub Trending repository tracking."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from src import config
from src.scraper import USER_AGENT

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


@dataclass
class TrendingRepo:
    name: str
    url: str
    description: str
    language: str | None
    stars: int
    today_stars: int
    forks: int


def _parse_count(text: str | None) -> int:
    """Parse GitHub count text like ``12,345`` or ``1.2k`` into an int."""
    if not text:
        return 0

    cleaned = text.strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])?", cleaned)
    if not match:
        return 0

    value = float(match.group(1))
    suffix = match.group(2)
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)
    return int(value * multiplier)


def _clean_repo_name(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def fetch_github_trending(count: int | None = None) -> list[TrendingRepo]:
    """Fetch GitHub Trending repositories from the daily all-language page."""
    limit = count or config.GITHUB_TRENDING_COUNT

    try:
        resp = requests.get(
            config.GITHUB_TRENDING_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Error fetching GitHub Trending")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    repos: list[TrendingRepo] = []

    for article in soup.select("article.Box-row"):
        link = article.select_one("h2 a")
        if not link:
            continue

        href = str(link.get("href", "")).strip()
        name = _clean_repo_name(link.get_text(" ", strip=True))
        if not href or not name:
            continue

        description_tag = article.select_one("p")
        language_tag = article.select_one('[itemprop="programmingLanguage"]')
        stars_tag = article.find("a", href=re.compile(r"/stargazers$"))
        forks_tag = article.find("a", href=re.compile(r"/forks$"))
        today_tag = article.find(string=re.compile(r"stars?\s+today", re.I))

        repos.append(
            TrendingRepo(
                name=name,
                url=urljoin("https://github.com", href),
                description=description_tag.get_text(" ", strip=True)
                if description_tag
                else "",
                language=language_tag.get_text(strip=True) if language_tag else None,
                stars=_parse_count(stars_tag.get_text(" ", strip=True))
                if stars_tag
                else 0,
                today_stars=_parse_count(str(today_tag)) if today_tag else 0,
                forks=_parse_count(forks_tag.get_text(" ", strip=True))
                if forks_tag
                else 0,
            )
        )

        if len(repos) >= limit:
            break

    if not repos:
        logger.warning(
            "GitHub Trending page returned 200 but no repos parsed; "
            "selectors may be broken"
        )

    logger.info("Fetched %d repositories from GitHub Trending", len(repos))
    return repos


def save_daily_trending_repos(repos: list[TrendingRepo], date_str: str) -> Path:
    """Save daily GitHub Trending repository snapshots."""
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")

    year, month, day = parts
    dir_path = DATA_DIR / "github_trending" / year / month
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"{day}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([asdict(repo) for repo in repos], f, indent=2, ensure_ascii=False)

    logger.info("Saved %d GitHub Trending repos to %s", len(repos), file_path)
    return file_path
