from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from src import config
from src.scraper import Article

logger = logging.getLogger(__name__)


def _escape_md(text: str | None) -> str:
    if text is None:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def format_digest(
    articles: list[Article],
    model_updates: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Format articles into a Telegram MarkdownV2 daily digest, grouped by source."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y\\-%m\\-%d")
    lines: list[str] = [f"📰 *InsightFlow Daily Digest \\- {date_str}*\n"]

    geeknews = [a for a in articles if a.source == "geeknews"]
    hackernews = [a for a in articles if a.source == "hackernews"]
    tldrai = [a for a in articles if a.source == "tldrai"]

    if geeknews:
        lines.append("🇰🇷 *GeekNews*\n")
        for i, article in enumerate(geeknews, 1):
            title = _escape_md(article.title)
            summary = _escape_md(article.ai_summary or article.summary)
            url = _escape_md(article.url)
            discussion_url = _escape_md(article.discussion_url)
            relevance = _escape_md(str(article.relevance_score))

            lines.append(
                f"{i}\\. *{title}*\n{summary}\n🔗 [원문]({url}) \\| [토론]({discussion_url})\n⭐ 관련성: {relevance}\n"
            )

    if hackernews:
        lines.append("🌍 *Hacker News*\n")
        for i, article in enumerate(hackernews, 1):
            title = _escape_md(article.title)
            score = _escape_md(str(article.score))
            summary = _escape_md(article.ai_summary)
            url = _escape_md(article.url)
            discussion_url = _escape_md(article.discussion_url)

            lines.append(
                f"{i}\\. *{title}* \\(⬆{score}\\)\n{summary}\n🔗 [원문]({url}) \\| [토론]({discussion_url})\n"
            )

    if tldrai:
        lines.append("🤖 *TLDR AI*\n")
        for i, article in enumerate(tldrai, 1):
            title = _escape_md(article.title)
            summary = _escape_md(article.ai_summary or article.summary)
            url = _escape_md(article.url)
            discussion_url = _escape_md(article.discussion_url)
            relevance = _escape_md(str(article.relevance_score))

            lines.append(
                f"{i}\\. *{title}*\n{summary}\n🔗 [원문]({url}) \\| [토론]({discussion_url})\n⭐ 관련성: {relevance}\n"
            )

    if model_updates:
        new_models = model_updates.get("new_models", [])
        rank_changes = model_updates.get("rank_changes", [])
        price_changes = model_updates.get("price_changes", [])

        if new_models or rank_changes or price_changes:
            lines.append("📊 *AI Model Updates*\n")

            if new_models:
                for model in new_models:
                    model_name = _escape_md(model["name"])
                    creator = _escape_md(model["creator"])
                    score = _escape_md(str(model["intelligence_index"]))
                    lines.append(
                        f"🆕 {model_name} by {creator} \\(intelligence: {score}\\)\n"
                    )

            if rank_changes:
                for change in rank_changes:
                    model_name = _escape_md(change["name"])
                    old_rank = _escape_md(str(change["old_rank"]))
                    new_rank = _escape_md(str(change["new_rank"]))
                    lines.append(f"📈 {model_name}: \\#{old_rank} → \\#{new_rank}\n")

            if price_changes:
                for change in price_changes:
                    model_name = _escape_md(change["name"])
                    old_price = _escape_md(str(change["old_price"]))
                    new_price = _escape_md(str(change["new_price"]))
                    change_pct = _escape_md(str(change["change_percent"]))
                    lines.append(
                        f"💰 {model_name}: \\${old_price} → \\${new_price} \\({change_pct}%\\)\n"
                    )

    return "\n".join(lines)


def chunk_message(text: str, max_length: int = 4096) -> list[str]:
    """Split text into chunks at article boundaries, each within max_length chars."""
    if len(text) <= max_length:
        return [text]

    blocks = re.split(r"\n\n", text)

    chunks: list[str] = []
    current_chunk = ""

    for block in blocks:
        candidate = f"{current_chunk}\n\n{block}" if current_chunk else block
        if len(candidate) > max_length - 10:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = block
        else:
            current_chunk = candidate

    if current_chunk:
        chunks.append(current_chunk)

    total = len(chunks)
    if total > 1:
        chunks = [f"{chunk}\n\n\\({i}/{total}\\)" for i, chunk in enumerate(chunks, 1)]

    return chunks


def send_telegram(text: str) -> bool:
    """Send MarkdownV2 message via Telegram Bot API with 3 retries (exponential backoff)."""
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would send Telegram message (%d chars)", len(text))
        logger.debug("[DRY RUN] Message content:\n%s", text)
        return True

    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
    }

    max_retries = 3
    backoff = 2

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=30)

            if resp.status_code == 200:
                logger.info("Telegram message sent successfully")
                return True

            logger.warning(
                "Telegram API error (attempt %d/%d): HTTP %d - %s",
                attempt,
                max_retries,
                resp.status_code,
                resp.text,
            )

        except requests.RequestException as e:
            logger.warning(
                "Telegram request failed (attempt %d/%d): %s",
                attempt,
                max_retries,
                e,
            )

        if attempt < max_retries:
            logger.info("Retrying in %ds...", backoff)
            time.sleep(backoff)
            backoff *= 3  # exponential: 2s → 6s → 18s

    logger.error("Failed to send Telegram message after %d attempts", max_retries)
    return False


def send_digest(
    articles: list[Article],
    model_updates: dict[str, list[dict[str, Any]]] | None = None,
) -> bool:
    """Format articles into digest, chunk, and send via Telegram (1s between chunks)."""
    if not articles:
        logger.info("No articles to send in digest")
        return True

    text = format_digest(articles, model_updates)
    chunks = chunk_message(text)

    logger.info(
        "Sending digest: %d article(s) in %d chunk(s)", len(articles), len(chunks)
    )

    for i, chunk in enumerate(chunks, 1):
        if not send_telegram(chunk):
            logger.error("Failed to send chunk %d/%d", i, len(chunks))
            return False
        if i < len(chunks):
            time.sleep(1)

    logger.info("Digest sent successfully")
    return True


def send_failure_notification(error_message: str) -> bool:
    """Send a MarkdownV2-escaped failure notification with timestamp via Telegram."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    escaped_error = _escape_md(error_message)
    escaped_timestamp = _escape_md(timestamp)

    text = f"⚠️ *InsightFlow 실행 실패*\n\n{escaped_error}\n\n{escaped_timestamp}"

    logger.warning("Sending failure notification: %s", error_message)
    return send_telegram(text)
