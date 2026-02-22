# AGENT.md — InsightFlow Project Guide

> **Before writing any code, read [`CODE.md`](./CODE.md)** for the mandatory development workflow (branching, TDD, review, PR).

## Project Overview

InsightFlow is a serverless AI tech news tracker powered by GitHub Actions. It runs daily at 08:00 KST, collecting articles from GeekNews, Hacker News, and TLDR AI, summarizing them with Gemini AI, tracking AI model performance/pricing changes, and delivering results via Telegram and Notion.

## Tech Stack

- **Runtime**: Python 3.13+ with `uv` package manager
- **AI**: Google Gemini 2.5 Flash (batch summarization)
- **Notifications**: Telegram Bot API (MarkdownV2)
- **Database**: Notion API (Articles weekly DB + Model Tracker change-log DB + Model Dashboard living DB)
- **Model Tracking**: Artificial Analysis API + SQLite snapshots
- **CI/CD**: GitHub Actions (daily cron + manual dispatch)
- **Testing**: pytest + pytest-asyncio

## Architecture

```
main.py (orchestrator)
├── scraper.py          → Collects articles from 3 sources
│   ├── fetch_geeknews()      (Atom feed)
│   ├── fetch_hackernews()     (HN API, async)
│   └── fetch_tldr_ai()        (HTML scraping)
├── storage.py          → Deduplication (seen_ids.json) + JSON persistence + GitHub Issues
├── ai_handler.py       → Keyword filter + Gemini batch summarization
│   ├── keyword_filter()       (GeekNews only; HN/TLDR bypass)
│   ├── batch_summarize()      (separates TLDR vs other sources for correct prompts)
│   └── filter_and_summarize() (pipeline: filter → summarize → threshold → notable flag)
├── model_tracker.py    → AI model data from Artificial Analysis API
│   ├── fetch_model_data()     (API call → raw model list)
│   ├── save_model_snapshots() (SQLite insert)
│   ├── get_model_updates()    (compare today vs previous → new/rank/price changes)
│   └── get_latest_models()    (wrapper: returns today's snapshot for dashboard)
├── notion_common.py    → Shared Notion utilities (get_client, resolve_data_source_id)
├── notion_handler.py   → Articles → Notion weekly DB
├── notion_model_handler.py → Model changes → Notion Model Tracker DB (change log)
├── notion_model_dashboard.py → All models → Notion AI 모델 현황 DB (living dashboard, upsert)
│   ├── ensure_model_dashboard_db()  (auto-create DB under tracker page)
│   ├── _find_model_page()           (lookup by model_id rich_text property)
│   ├── _build_dashboard_properties() (map model dict → Notion properties, skip None)
│   ├── _upsert_model()              (create or update page)
│   └── sync_models_to_dashboard()   (public entry point, sorted by intelligence_index desc)
├── notifier.py         → Telegram digest formatting + chunking + sending
└── config.py           → All configuration, env vars, constants, KST timezone
```

## Pipeline Steps

| Step | Description | Dry-run behavior |
|------|-------------|------------------|
| 1 | `scrape_all()` — collect articles | Runs normally |
| 2 | `filter_new_articles()` — deduplicate via `seen_ids.json` | Runs normally |
| 3 | `filter_and_summarize()` — keyword filter + Gemini | Runs normally |
| 4 | `save_daily_articles()` + `save_seen_ids()` | Runs normally |
| 5 | `create_github_issues()` | **Skipped** |
| 6 | `send_to_notion()` — articles → weekly Notion DB | **Skipped** |
| 7 | Model tracker: `fetch_model_data()` → `save_model_snapshots()` → `get_model_updates()` | Runs normally |
| 7.5 | `send_model_updates_to_notion()` — changes → Model Tracker DB | **Skipped** |
| 7.6 | `sync_models_to_dashboard()` — all models → Living Dashboard DB | **Skipped** |
| 8 | `send_digest()` — Telegram | **Skipped** |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Yes | Telegram chat ID |
| `NOTION_API_KEY` | Yes | Notion Integration API key |
| `NOTION_PARENT_PAGE_ID` | Yes | Parent page for weekly Articles DBs |
| `NOTION_DATABASE_ID` | No | Existing Articles DB (skips auto-create) |
| `NOTION_MODEL_TRACKER_DB_ID` | No | Existing Model Tracker DB (auto-created if unset) |
| `NOTION_MODEL_TRACKER_PAGE_ID` | No | Separate page for Model Tracker/Dashboard DBs (falls back to `NOTION_PARENT_PAGE_ID`) |
| `NOTION_MODEL_DASHBOARD_DB_ID` | No | Existing Dashboard DB (auto-created if unset) |
| `ARTIFICIAL_ANALYSIS_API_KEY` | No | Artificial Analysis API key (model tracking disabled if unset) |

## Key Design Decisions

### Data Flow
1. Scrape all sources concurrently (`asyncio.to_thread` for sync functions)
2. Deduplicate via `seen_ids.json` (key format: `"{source}:{source_id}"`)
3. `filter_new_articles()` has a **side effect**: adds new IDs to `seen_ids` set in-place
4. Save `seen_ids` immediately after `save_daily_articles()`, **before** any notifications
5. Keyword filter only applies to GeekNews; HN and TLDR are pre-curated
6. Batch summarization separates TLDR articles from others for source-appropriate prompts
7. `dry_run` mode is controlled via parameter threading (no global state mutation)

### Notion Integration
- **3 databases**: Articles (weekly, auto-created), Model Tracker (change log), Model Dashboard (living snapshot)
- Weekly Articles DBs are auto-created under `NOTION_PARENT_PAGE_ID` with name format `"YYYY-WNN Articles"`
- Uses Notion API 2025-09-03 which requires `data_source_id` instead of `database_id`
- `notion_common.py` holds shared `get_client()` and `resolve_data_source_id()`
- Max 5 pages created per run (rate limiting)
- Model Dashboard uses **upsert** keyed on `model_id` rich_text property — one row per model, updated daily
- `_build_dashboard_properties()` skips any field that is `None` (avoids Notion API errors)

### Model Tracker
- SQLite database at `data/models.db` stores daily snapshots
- Each row: model name, provider, intelligence/coding/math/speed indexes, pricing, throughput, TTFT, rank, date
- `get_model_updates()` compares today vs previous snapshot → detects new models, rank changes (top 10), price changes (≥10%)
- `get_latest_models()` is a thin wrapper returning today's snapshot as a list of dicts for the dashboard

### Telegram
- Messages use MarkdownV2 (requires escaping special chars via `_escape_md()`)
- `_escape_md(value)` handles `None` gracefully (returns empty string)
- Auto-chunking at 4096 chars with 1s delay between chunks
- 3 retries with exponential backoff (2s → 6s → 18s)

## Running the Project

```bash
# Install dependencies
uv sync

# Run in dry-run mode (no external API calls for notifications)
uv run python -m src.main --dry-run

# Run tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_notifier.py -v
```

## Testing Strategy

- **Framework**: pytest with pytest-asyncio
- **Pattern**: TDD (Red-Green-Refactor)
- **Fixtures**: Shared in `tests/conftest.py` (sample_articles, sample_model_updates, sample_models, etc.)
- **Approach**: Mostly code-verification tests (checking source for patterns) + mock-based integration tests
- **Mock requirements**: `main.py` tests must mock `get_latest_models` and `sync_models_to_dashboard` in addition to all other pipeline functions

### Test Files (43 total)
| File | Tests | Covers |
|------|-------|--------|
| `test_smoke.py` | 1 | All module imports |
| `test_notifier.py` | 6 | Telegram message formatting, `_escape_md(None)`, model updates |
| `test_main.py` | 6 | Pipeline ordering, dry_run behavior, error logging, dashboard integration |
| `test_scraper.py` | 2 | Config usage, modern asyncio API |
| `test_ai_handler.py` | 3 | Batch separation by source |
| `test_notion_common.py` | 3 | Shared Notion utilities, duplication removal |
| `test_model_tracker_wrapper.py` | 4 | `get_latest_models()` wrapper (empty DB, no table, normal, date param) |
| `test_notion_model_dashboard.py` | 18 | Dashboard DB schema, properties, upsert, sync, None handling, dry-run, sorting |

## Common Pitfalls

1. **MarkdownV2 escaping**: All dynamic text in Telegram messages must go through `_escape_md()`. `_escape_md(None)` must return `""`, not crash.
2. **model_tracker output keys**: Uses `"name"` (not `"model_name"`), `"intelligence_index"` (not `"intelligence_score"`)
3. **Notion API**: `data_source_id` ≠ `database_id` — always resolve via `resolve_data_source_id()`
4. **Mixed batches**: TLDR articles need different Gemini prompts than HN/GeekNews — `batch_summarize()` handles separation
5. **asyncio**: Use `asyncio.to_thread()` (not deprecated `get_event_loop().run_in_executor()`)
6. **Dashboard None values**: `_build_dashboard_properties()` must skip `None` fields — Notion API rejects null number properties
7. **Dashboard upsert key**: `_find_model_page()` queries by `model_id` rich_text, not by title — title is display name, model_id is the stable API identifier
8. **KST timezone**: `get_week_identifier()` uses `datetime.now(KST)` — using naive `datetime.now()` causes wrong week boundaries when running in UTC (GitHub Actions)
9. **Test mocks for main.py**: Must patch `get_latest_models` and `sync_models_to_dashboard` alongside existing pipeline mocks, or tests will attempt real API calls
