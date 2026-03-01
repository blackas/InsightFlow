# AGENTS.md — Code Review Guide for InsightFlow

> Quick-reference for reviewers. For development workflow, see [`CODE.md`](./CODE.md). For project context, see [`AGENT.md`](./AGENT.md).

---

## 1. Project Summary

InsightFlow is a **serverless AI tech news tracker** that runs daily via GitHub Actions (08:00 KST). It scrapes articles from 3 sources, summarizes them with Gemini AI, tracks AI model performance/pricing, and delivers results to Telegram + Notion.

- **Language**: Python 3.11+ (typed, `from __future__ import annotations`)
- **Package Manager**: `uv` (lockfile: `uv.lock`)
- **Runtime**: GitHub Actions cron (no persistent server)
- **Entry Point**: `src/main.py` → `main(dry_run: bool)`

---

## 2. Architecture Overview

```
src/
├── main.py                    # Orchestrator — 8-step sequential pipeline
├── config.py                  # Module-level constants + env vars (no classes)
├── scraper.py                 # Article dataclass + 3 fetchers (GeekNews/HN/TLDR)
├── storage.py                 # JSON persistence + dedup (seen_ids.json) + GitHub Issues
├── ai_handler.py              # Gemini batch summarization + keyword filter
├── model_tracker.py           # Artificial Analysis API + SQLite snapshots + change detection
├── notifier.py                # Telegram MarkdownV2 formatting + chunking + sending
├── blog_builder.py            # Static HTML blog from GitHub Issues (for GitHub Pages)
├── notion_common.py           # Shared Notion client factory + data_source_id resolver
├── notion_handler.py          # Articles → weekly Notion DB
├── notion_model_handler.py    # Model changes → Notion change-log DB
└── notion_model_dashboard.py  # All models → Notion living dashboard DB (upsert)

worker/
├── index.js                   # Cloudflare Worker — closes GitHub Issue on "읽음" click
└── wrangler.toml              # Worker config

tests/
├── conftest.py                # Shared fixtures (sample articles, mock config, etc.)
├── test_smoke.py              # Import smoke test
├── test_main.py               # Pipeline orchestration tests
├── test_scraper.py            # Scraper config + asyncio usage
├── test_scraper_behavior.py   # Scraper behavioral tests
├── test_ai_handler.py         # Batch separation by source
├── test_storage.py            # Storage operations
├── test_notifier.py           # Telegram formatting + escape edge cases
├── test_model_tracker_detection.py  # Change detection logic
├── test_model_tracker_wrapper.py    # get_latest_models() wrapper
├── test_normalize_model.py          # API response normalization
├── test_notion_common.py            # Shared Notion utilities
├── test_notion_model_dashboard.py   # Dashboard upsert + schema + None handling
├── test_blog_builder.py             # Blog generation
└── test_main.py                     # Full pipeline mock tests
```

### Pipeline Flow (main.py)

```
1. scrape_all()                    → Collect articles (3 sources, concurrent)
2. filter_new_articles()           → Dedup via seen_ids.json (SIDE EFFECT: mutates seen_ids set)
3. filter_and_summarize()          → Keyword filter + Gemini AI batch summarization
4. save_daily_articles() + save_seen_ids()  → JSON persistence
5. create_github_issues()          → [skipped in dry_run]
6. send_to_notion()                → [skipped in dry_run]
7. Model tracker pipeline          → fetch → SQLite snapshot → change detection
   7.5 send_model_updates_to_notion()  → [skipped in dry_run]
   7.6 sync_models_to_dashboard()      → [skipped in dry_run]
8. send_digest()                   → Telegram [skipped in dry_run]
```

---

## 3. Key Data Types

### Article (dataclass — `scraper.py`)

```python
@dataclass
class Article:
    source: str          # "geeknews" | "hackernews" | "tldrai"
    source_id: str       # Unique per source
    title: str
    url: str             # Original article URL
    discussion_url: str  # Community thread URL
    summary: str         # Raw summary from source
    score: int           # HN score (0 for others)
    published_at: str    # ISO 8601
    ai_summary: str = ""
    relevance_score: float = 0.0
    notable: bool = False
    tags: list[str] = field(default_factory=list)
```

### Dedup Key Format
`"{source}:{source_id}"` — e.g., `"geeknews:12345"`, `"tldrai:https://example.com/article"`

### Model Updates Dict
```python
{
    "new_models": [{"model_id", "name", "creator", "intelligence_index"}],
    "rank_changes": [{"name", "old_rank", "new_rank", "intelligence_index"}],
    "price_changes": [{"name", "old_price", "new_price", "change_percent"}],
}
```

---

## 4. External Integrations

| Service | Module | API/Protocol | Key Constraints |
|---------|--------|--------------|-----------------|
| **Google Gemini** | `ai_handler.py` | `google-genai` SDK, JSON response mode | 1,500 req/day free tier; retries with 5s/15s/45s backoff |
| **Telegram** | `notifier.py` | Bot API (MarkdownV2) | 4,096 char limit (auto-chunked); 3 retries with 2s/6s/18s backoff |
| **Notion** | `notion_*.py` | `notion-client` SDK (API 2025-09-03) | 3 req/s; max 5 pages/run; uses `data_source_id` (NOT `database_id`) |
| **Artificial Analysis** | `model_tracker.py` | REST JSON API | 1,000 req/day free tier |
| **Hacker News** | `scraper.py` | Firebase REST API (async via `aiohttp`) | Top 30 stories fetched concurrently |
| **GeekNews** | `scraper.py` | Atom RSS feed via `feedparser` | 24-hour cutoff filter |
| **TLDR AI** | `scraper.py` | HTML scraping via `beautifulsoup4` | Filters by section names; strips UTM params |
| **GitHub** | `storage.py`, `blog_builder.py` | REST API (Issues), `gh` CLI | 5 issues/run max |
| **Cloudflare Worker** | `worker/index.js` | GitHub API PATCH | Closes issues on "읽음" button click |

---

## 5. Review-Critical Patterns

### 5.1 Notion API — `data_source_id` vs `database_id`

The project uses Notion API version **2025-09-03** which requires `data_source_id` instead of `database_id` for queries and page creation. All Notion modules resolve this via `notion_common.resolve_data_source_id()`.

**Review check**: Any new Notion code MUST use `data_source_id`, never raw `database_id`.

### 5.2 MarkdownV2 Escaping

Telegram requires MarkdownV2 escaping. Two escape functions exist:
- `_escape_md(text)` — Full escape for display text. Handles `None` → `""`.
- `_escape_url(url)` — Minimal escape for URLs inside `[text](url)`. Only escapes `)` and `\`.

**Review check**: All dynamic text in Telegram messages MUST use the correct escape function. URLs inside link syntax use `_escape_url()`, everything else uses `_escape_md()`.

### 5.3 Keyword Filter — Source-Specific Behavior

- **GeekNews**: Subject to keyword filtering (`config.KEYWORDS` match)
- **Hacker News & TLDR AI**: Bypass keyword filter entirely (pre-curated sources)

**Review check**: New sources must explicitly decide filter behavior in `keyword_filter()`.

### 5.4 Batch Summarization — Source Separation

`batch_summarize()` separates TLDR articles from others because TLDR articles already have summaries and need different Gemini prompts (key point extraction vs full summarization).

**Review check**: Gemini prompt changes must consider both source types.

### 5.5 Side Effect in `filter_new_articles()`

`filter_new_articles(all_articles, seen_ids)` **mutates** `seen_ids` in-place by adding new article IDs. This is documented but easy to miss.

**Review check**: Call order matters. `save_seen_ids()` must be called AFTER `filter_new_articles()` and `save_daily_articles()`.

### 5.6 Dashboard Upsert — `model_id` as Key

`_find_model_page()` queries by `model_id` (rich_text property), NOT by title. The title is a display name; `model_id` is the stable API identifier used for upsert matching.

**Review check**: Dashboard page lookups must query `model_id`, never title.

### 5.7 None Handling in Dashboard Properties

`_build_dashboard_properties()` skips fields with `None` values. Notion API rejects `null` for number properties.

**Review check**: Any new numeric field added to the dashboard must have a None-guard.

### 5.8 KST Timezone for Week Boundaries

`get_week_identifier()` uses `datetime.now(KST)` (UTC+9) because GitHub Actions runs in UTC. Using naive `datetime.now()` causes wrong week boundaries.

**Review check**: Any date/time logic that affects weekly DB naming MUST use `KST`.

### 5.9 Model Tracker — Nested API Response Normalization

`_normalize_model()` handles both flat (cached/stored) and nested (raw API) formats. The Artificial Analysis API returns nested structures (`evaluations.artificial_analysis_intelligence_index`) while SQLite stores flat fields.

**Review check**: New model fields need entries in both `_normalize_model()` mapping and SQLite schema.

### 5.10 `dry_run` — Parameter Threading, Not Global State

`dry_run` is passed as a function parameter through the pipeline. It does NOT mutate `config.DRY_RUN` at runtime. The config value is only read at startup in `__main__`.

**Review check**: New pipeline steps must accept `dry_run` parameter or check the flag correctly.

---

## 6. Error Handling Conventions

| Pattern | Used In | Behavior |
|---------|---------|----------|
| **Graceful degradation** | `ai_handler.py`, `model_tracker.py` | On failure, returns input unchanged or empty results |
| **Non-fatal exception** | `main.py` steps 7, 7.5, 7.6 | Caught and logged; pipeline continues |
| **Fatal exception** | `main.py` outer try/except | Sends Telegram failure notification, then re-raises |
| **Retry with backoff** | `ai_handler.py` (Gemini), `notifier.py` (Telegram) | Exponential backoff: Gemini 5/15/45s, Telegram 2/6/18s |
| **Rate limit detection** | `ai_handler.py` | Checks for "429" or "quota" in error string |

---

## 7. Configuration

All configuration lives in `config.py` as **module-level constants** (no config class).

### Required Environment Variables
| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google AI Studio |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API |
| `TELEGRAM_CHAT_ID` | Telegram recipient |
| `NOTION_API_KEY` | Notion integration |
| `NOTION_PARENT_PAGE_ID` | Parent page for auto-created DBs |

### Optional Environment Variables
| Variable | Default Behavior |
|----------|-----------------|
| `NOTION_DATABASE_ID` | Auto-creates weekly DB if unset |
| `NOTION_MODEL_TRACKER_DB_ID` | Auto-creates "AI Model Tracker" DB if unset |
| `NOTION_MODEL_TRACKER_PAGE_ID` | Falls back to `NOTION_PARENT_PAGE_ID` |
| `NOTION_MODEL_DASHBOARD_DB_ID` | Auto-creates "AI 모델 현황" DB if unset |
| `ARTIFICIAL_ANALYSIS_API_KEY` | Model tracking disabled if unset |
| `DRY_RUN` | `false` — skips external write operations when `true` |

### Key Constants
| Constant | Value | Purpose |
|----------|-------|---------|
| `BATCH_SIZE` | 8 | Gemini API batch size |
| `HN_TOP_N` | 30 | Hacker News articles to fetch |
| `RELEVANCE_THRESHOLD` | 0.6 | Minimum score to include in digest |
| `ISSUE_THRESHOLD` | 0.8 | Minimum score for GitHub Issues + Notion |
| `MAX_ISSUES_PER_RUN` | 5 | GitHub Issues creation cap |
| `MAX_NOTION_PER_RUN` | 5 | Notion page creation cap |
| `GEMINI_MODEL` | `gemini-2.5-flash` | AI model for summarization |

---

## 8. Testing Conventions

- **Framework**: pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- **Test Location**: `tests/` directory, mirroring `src/` modules
- **Naming**: `test_{module}.py` → `test_{behavior}()` or `test_{function_name}_{scenario}()`
- **Methodology**: TDD (Red-Green-Refactor) as mandated by `CODE.md`

### Test Patterns

1. **Code-verification tests**: Assert source patterns exist (e.g., verify `asyncio.to_thread` usage in scraper)
2. **Mock-based integration tests**: Patch external APIs, verify pipeline behavior
3. **Shared fixtures in `conftest.py`**: `sample_article`, `sample_articles`, `sample_model_updates`, `mock_config`, `tmp_data_dir`

### Mock Requirements for `main.py`

Tests for `main.py` must mock ALL of these (or they make real API calls):
- `scrape_all`, `filter_new_articles`, `load_seen_ids`, `save_seen_ids`, `save_daily_articles`
- `filter_and_summarize`, `create_github_issues`, `send_to_notion`
- `fetch_model_data`, `save_model_snapshots`, `get_model_updates`
- `get_latest_models`, `sync_models_to_dashboard`
- `send_model_updates_to_notion`, `send_digest`, `send_failure_notification`

### Running Tests

```bash
uv run pytest tests/ -v          # Full suite
uv run pytest tests/test_foo.py  # Single file
```

---

## 9. CI/CD Pipelines

### `daily-digest.yml` — Main Pipeline
- **Trigger**: Cron `0 23 * * *` UTC (= 08:00 KST) + manual dispatch
- **Steps**: Checkout → Install uv → Python 3.11 → `uv sync` → Run pipeline → Git commit data/ → Failure notification
- **Permissions**: `contents: write`, `issues: write`
- **Concurrency**: `daily-digest` group, never cancels in-progress

### `codeguardian.yml` — PR Review
- **Trigger**: PR opened/synchronized, `/review` comment, manual dispatch
- **Action**: Calls `blackas/CodeGuardian` reusable workflow for AI-powered code review
- **Secret**: `OPENAI_API_KEY`

### `blog-deploy.yml` — Static Blog
- **Trigger**: Issue opened/closed/labeled + manual dispatch
- **Steps**: Build HTML from open issues via `blog_builder.py` → Deploy to GitHub Pages
- **Permissions**: `contents: read`, `pages: write`, `id-token: write`

---

## 10. Dependencies

### Runtime
| Package | Version | Purpose |
|---------|---------|---------|
| `feedparser` | >=6.0.0 | GeekNews Atom feed parsing |
| `aiohttp` | >=3.9.0 | Async HTTP for HN API |
| `google-genai` | >=1.0.0 | Gemini AI SDK |
| `python-dotenv` | >=1.0.0 | `.env` file loading |
| `requests` | >=2.31.0 | Sync HTTP (Telegram, GitHub, Artificial Analysis) |
| `notion-client` | >=2.7.0,<3.0.0 | Notion API SDK |
| `beautifulsoup4` | >=4.12.0 | TLDR AI HTML parsing |

### Dev
| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=8.0.0 | Test framework |
| `pytest-asyncio` | >=0.23.0 | Async test support |

---

## 11. Data Storage

| Path | Format | Purpose |
|------|--------|---------|
| `data/seen_ids.json` | JSON array (sorted strings) | Deduplication tracking |
| `data/YYYY/MM/DD.json` | JSON array of article dicts | Daily article archive |
| `data/models.db` | SQLite | Model tracker snapshots (PK: `model_id + fetched_at`) |

---

## 12. Review Checklist

When reviewing PRs for this project, verify:

- [ ] No `as any`, `@ts-ignore`, or type suppression equivalents
- [ ] New Notion code uses `data_source_id`, not `database_id`
- [ ] Telegram text uses correct escape function (`_escape_md` vs `_escape_url`)
- [ ] New pipeline steps respect `dry_run` parameter
- [ ] Date/time logic uses `KST` timezone where week boundaries matter
- [ ] New model fields are handled in `_normalize_model()` + SQLite schema
- [ ] Dashboard numeric fields have None-guards
- [ ] `filter_new_articles()` call order is preserved (before save)
- [ ] Tests mock all external API calls in `main.py` tests
- [ ] No hardcoded secrets or credentials
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] Follows TDD workflow defined in `CODE.md`
