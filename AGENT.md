# AGENT.md — InsightFlow Project Guide

## Project Overview

InsightFlow is a serverless AI tech news tracker powered by GitHub Actions. It runs daily at 08:00 KST, collecting articles from GeekNews, Hacker News, and TLDR AI, summarizing them with Gemini AI, tracking AI model performance/pricing changes, and delivering results via Telegram and Notion.

## Tech Stack

- **Runtime**: Python 3.13+ with `uv` package manager
- **AI**: Google Gemini 2.5 Flash (batch summarization)
- **Notifications**: Telegram Bot API (MarkdownV2)
- **Database**: Notion API (weekly Articles DB + Model Tracker DB)
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
├── notion_common.py    → Shared Notion utilities (get_client, resolve_data_source_id)
├── notion_handler.py   → Articles → Notion weekly DB
├── notion_model_handler.py → Model changes → Notion Model Tracker DB
├── notifier.py         → Telegram digest formatting + chunking + sending
└── config.py           → All configuration, env vars, constants
```

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
- Weekly databases are auto-created under `NOTION_PARENT_PAGE_ID`
- Uses Notion API 2025-09-03 which requires `data_source_id` instead of `database_id`
- `notion_common.py` holds shared `get_client()` and `resolve_data_source_id()`
- Max 5 pages created per run (rate limiting)

### Telegram
- Messages use MarkdownV2 (requires escaping special chars via `_escape_md()`)
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
- **Fixtures**: Shared in `tests/conftest.py` (sample_articles, sample_model_updates, etc.)
- **Approach**: Mostly code-verification tests (checking source for patterns) + mock-based integration tests

### Test Files
| File | Tests | Covers |
|------|-------|--------|
| `test_smoke.py` | 1 | All module imports |
| `test_notifier.py` | 4 | Telegram message formatting (model updates) |
| `test_main.py` | 5 | Pipeline ordering, dry_run behavior, error logging |
| `test_scraper.py` | 2 | Config usage, modern asyncio API |
| `test_ai_handler.py` | 3 | Batch separation by source |
| `test_notion_common.py` | 3 | Shared Notion utilities, duplication removal |

## Important Constraints

- **Never modify** `.github/workflows/daily-digest.yml`
- **Never change** `seen_ids.json` or daily JSON file formats
- **Never modify** Gemini prompt text content (only routing logic)
- `config.DRY_RUN` env var reading must stay in `config.py` (for GitHub Actions)
- `TLDR_SECTIONS` is a `frozenset` in config (membership test optimization)

## Common Pitfalls

1. **MarkdownV2 escaping**: All dynamic text in Telegram messages must go through `_escape_md()`
2. **model_tracker output keys**: Uses `"name"` (not `"model_name"`), `"intelligence_index"` (not `"intelligence_score"`)
3. **Notion API**: `data_source_id` ≠ `database_id` — always resolve via `resolve_data_source_id()`
4. **Mixed batches**: TLDR articles need different Gemini prompts than HN/GeekNews — `batch_summarize()` handles separation
5. **asyncio**: Use `asyncio.to_thread()` (not deprecated `get_event_loop().run_in_executor()`)
