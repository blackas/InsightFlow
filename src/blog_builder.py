"""Static blog builder from GitHub Issues.

Fetches OPEN issues, parses structured bodies, and generates
static HTML pages deployable to GitHub Pages.
"""

from __future__ import annotations

import html
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SOURCE_COLORS: dict[str, str] = {
    "geeknews": "#e67e22",
    "hackernews": "#ff6600",
    "tldrai": "#6c5ce7",
    "unknown": "#95a5a6",
}


def parse_issue_body(body: str) -> dict[str, Any]:
    """Parse structured GitHub Issue body into a flat dict.

    Expected format from storage.py create_github_issues():
        ## 기사 정보
        - **원본 URL**: https://...
        - **토론**: https://...
        - **소스**: geeknews
        - **관련성 점수**: 0.85

        ## AI 요약
        Summary text here...
    """
    data: dict[str, Any] = {
        "url": "",
        "discussion_url": "",
        "source": "",
        "relevance_score": 0.0,
        "ai_summary": "",
    }

    url_match = re.search(r"\*\*원본 URL\*\*:\s*(\S+)", body)
    if url_match:
        data["url"] = url_match.group(1)

    discussion_match = re.search(r"\*\*토론\*\*:\s*(\S+)", body)
    if discussion_match:
        data["discussion_url"] = discussion_match.group(1)

    source_match = re.search(r"\*\*소스\*\*:\s*(\w+)", body)
    if source_match:
        data["source"] = source_match.group(1)

    score_match = re.search(r"\*\*관련성 점수\*\*:\s*([\d.]+)", body)
    if score_match:
        data["relevance_score"] = float(score_match.group(1))

    summary_match = re.search(r"## AI 요약\n(.*?)(?:\n##|$)", body, re.DOTALL)
    if summary_match:
        summary_text = summary_match.group(1).strip()
        data["ai_summary"] = "\n".join(
            line.strip() for line in summary_text.split("\n") if line.strip()
        )

    return data


def extract_title_and_source(issue_title: str) -> tuple[str, str]:
    """Extract article title and source from '[source] Title' format."""
    match = re.match(r"\[(\w+)\]\s+(.*)", issue_title)
    if match:
        return match.group(2), match.group(1)
    return issue_title, "unknown"


def fetch_open_issues() -> list[dict[str, Any]]:
    """Fetch all OPEN issues via gh CLI."""
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--state",
                "open",
                "--label",
                "auto-collected",
                "--json",
                "number,title,body,labels,state,createdAt",
                "--limit",
                "500",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        logger.exception("Failed to fetch GitHub issues")
        raise RuntimeError("Failed to fetch GitHub issues") from None
    except json.JSONDecodeError:
        logger.exception("Failed to parse GitHub issues JSON")
        raise RuntimeError("Failed to parse GitHub issues JSON") from None


def render_article_html(issue: dict[str, Any], worker_url: str) -> str:
    """Render a single article page as HTML."""
    title, source = extract_title_and_source(issue["title"])
    parsed = parse_issue_body(issue.get("body", ""))
    number = issue["number"]
    created = issue.get("createdAt", "")[:10]
    color = _SOURCE_COLORS.get(source, _SOURCE_COLORS["unknown"])

    summary_html = ""
    if parsed["ai_summary"]:
        paragraphs = parsed["ai_summary"].split("\n")
        summary_html = "".join(f"<p>{_esc(line)}</p>" for line in paragraphs)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} — InsightFlow</title>
<style>{_css()}</style>
</head>
<body>
<nav><a href="index.html">← 목록으로</a></nav>
<main>
  <article>
    <header>
      <span class="badge" style="background:{color}">{_esc(source)}</span>
      <time>{_esc(created)}</time>
      <span class="score">관련성 {parsed["relevance_score"]:.0%}</span>
    </header>
    <h1>{_esc(title)}</h1>
    <div class="summary">{summary_html}</div>
    <div class="links">
      <a href="{_safe_url(parsed["url"])}" target="_blank" rel="noopener">원문 보기 ↗</a>
      <a href="{_safe_url(parsed["discussion_url"])}" target="_blank" rel="noopener">토론 보기 ↗</a>
    </div>
    {_read_button_html(worker_url, number)}
  </article>
</main>
</body>
</html>"""


def render_index_html(issues: list[dict[str, Any]], worker_url: str) -> str:
    """Render index page listing all articles, sorted newest-first."""
    sorted_issues = sorted(
        issues,
        key=lambda i: i.get("createdAt", ""),
        reverse=True,
    )

    cards = ""
    for issue in sorted_issues:
        title, source = extract_title_and_source(issue["title"])
        number = issue["number"]
        created = issue.get("createdAt", "")[:10]
        color = _SOURCE_COLORS.get(source, _SOURCE_COLORS["unknown"])
        parsed = parse_issue_body(issue.get("body", ""))
        preview = (parsed["ai_summary"] or "")[:120]
        if len(parsed.get("ai_summary", "")) > 120:
            preview += "…"

        cards += f"""
  <a class="card" href="{number}.html">
    <div class="card-header">
      <span class="badge" style="background:{color}">{_esc(source)}</span>
      <time>{_esc(created)}</time>
    </div>
    <h2>{_esc(title)}</h2>
    <p class="preview">{_esc(preview)}</p>
  </a>"""

    count = len(sorted_issues)
    empty_msg = '<p class="empty">수집된 기사가 없습니다.</p>' if count == 0 else ""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>InsightFlow — AI 기술 뉴스</title>
<style>{_css()}</style>
</head>
<body>
<header class="site-header">
  <h1>InsightFlow</h1>
  <p>AI 기술 뉴스 트래커 · {count}건</p>
</header>
<main>
  <div class="cards">{cards}
  </div>
  {empty_msg}
</main>
</body>
</html>"""


def build_blog(output_dir: str, worker_url: str) -> None:
    """Fetch open issues, generate HTML, write to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    issues = fetch_open_issues()
    logger.info("Building blog from %d open issues", len(issues))

    index_html = render_index_html(issues, worker_url)
    (out / "index.html").write_text(index_html, encoding="utf-8")

    for issue in issues:
        article_html = render_article_html(issue, worker_url)
        (out / f"{issue['number']}.html").write_text(article_html, encoding="utf-8")

    logger.info("Blog built: %d article pages + index → %s", len(issues), out)


def _esc(text: str) -> str:
    """HTML escaping using stdlib."""
    return html.escape(text)


def _safe_url(url: str) -> str:
    """Escape URL for use in href, allowing only http(s) schemes."""
    if url and not url.startswith(("http://", "https://")):
        return ""
    return _esc(url)


def _read_button_html(worker_url: str, number: int) -> str:
    """Issue-closing is disabled on the public blog until an auth model exists."""
    _ = worker_url, number
    return ""


def _css() -> str:
    return """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  line-height:1.6;color:#1a1a2e;background:#f8f9fa;max-width:800px;margin:0 auto;padding:1rem}
nav{margin-bottom:1.5rem}
nav a{color:#6c5ce7;text-decoration:none;font-weight:500}
.site-header{text-align:center;padding:2rem 0 1rem}
.site-header h1{font-size:1.8rem;color:#1a1a2e}
.site-header p{color:#636e72;margin-top:.25rem}
h1{font-size:1.5rem;margin:.75rem 0}
h2{font-size:1.1rem;margin:.5rem 0;color:#2d3436}
header{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.badge{color:#fff;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}
time{font-size:.8rem;color:#636e72}
.score{font-size:.8rem;color:#636e72}
.summary p{margin:.5rem 0;color:#2d3436}
.links{display:flex;gap:1rem;margin:1rem 0}
.links a{color:#6c5ce7;text-decoration:none;font-weight:500}
.actions{margin-top:1.5rem}
.btn-read{display:inline-block;padding:.5rem 1.5rem;background:#00b894;color:#fff;
  border-radius:6px;text-decoration:none;font-weight:600}
.btn-read:hover{background:#00a381}
.cards{display:flex;flex-direction:column;gap:.75rem}
.card{display:block;padding:1rem;background:#fff;border-radius:8px;
  text-decoration:none;color:inherit;border:1px solid #dfe6e9;transition:box-shadow .15s}
.card:hover{box-shadow:0 2px 8px rgba(0,0,0,.08)}
.card-header{display:flex;align-items:center;gap:.5rem}
.preview{font-size:.9rem;color:#636e72;margin-top:.25rem}
.empty{text-align:center;color:#b2bec3;padding:3rem 0}
"""
