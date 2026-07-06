# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

TrendRadar is a hot-news aggregation and analysis tool. It crawls trending topics from multiple Chinese platforms (Zhihu, Weibo, Baidu, etc.) and RSS feeds, matches titles against user-defined keywords, generates HTML reports, and pushes notifications to 9+ channels (Feishu, DingTalk, WeCom, Telegram, Email, Slack, Bark, ntfy, generic webhook).

## Commands

```bash
# Install dependencies (requires Python >= 3.12)
pip install -e .

# Run the main pipeline (crawl → analyze → report → notify)
python -m trendradar

# Diagnostic / utility commands
python -m trendradar --doctor              # Environment & config health check
python -m trendradar --test-notification   # Send test notification to configured channels
python -m trendradar --show-schedule       # Display current schedule status

# Start the MCP server (for AI client integration)
python -m mcp_server.server                # stdio mode (default)
python -m mcp_server.server --http 8080     # HTTP mode

# Docker management (inside container)
python docker/manage.py run                # Manual crawl once
python docker/manage.py status             # Show container status
python docker/manage.py start_webserver    # Serve output/ on port 8080
```

## Architecture

### Data flow

```
config.yaml ──► load_config() ──► AppContext ──► NewsAnalyzer.run()
                                                     │
                    ┌────────────────────────────────┼──────────────────────────────────┐
                    ▼                                ▼                                  ▼
           DataFetcher.crawl_websites()    RSSFetcher.fetch_all()           StorageManager.save_news_data()
           (newsnow API → hotlists)        (feedparser → RSS items)        (SQLite + optional TXT snapshot)
                    │                                │
                    └────────────┬───────────────────┘
                                 ▼
                    count_word_frequency()  OR  AIFilterPipeline.run()
                    (keyword matching)           (AI tag-based filtering)
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
           generate_html()   dispatch_all()   translate_content()
           (HTML report)     (9 channels)     (AI translation)
```

### Key classes and their roles

| Class | File | Role |
|-------|------|------|
| `NewsAnalyzer` | `trendradar/__main__.py` | Main orchestrator (~1600 lines): crawling, analysis pipeline, report generation, notification dispatch |
| `AppContext` | `trendradar/context.py` | Config wrapper + dependency injection hub. All operations route through this, eliminating global state |
| `StorageManager` | `trendradar/storage/manager.py` | Unified backend: auto-selects local SQLite or S3 remote. Module-level singleton via `get_storage_manager()` |
| `Scheduler` | `trendradar/core/scheduler.py` | Timeline-based scheduler: periods + day_plans + week_map model. Controls collect/analyze/push windows + once-per-period dedup |
| `AIClient` | `trendradar/ai/client.py` | LiteLLM wrapper, supports 100+ providers. Model format: `provider/model_name` |
| `AIAnalyzer` | `trendradar/ai/analyzer.py` | Calls AI for deep analysis (5-section report: trends, sentiment, signals, RSS insights, outlook) |
| `AIFilterPipeline` | `trendradar/ai/filter_pipeline.py` | AI-based smart filtering: extracts tags from interests file, classifies news, replaces keyword matching |
| `NotificationDispatcher` | `trendradar/notification/dispatcher.py` | Multi-account, multi-channel dispatch with translation support |
| `DataFetcher` | `trendradar/crawler/fetcher.py` | Fetches hotlists from newsnow API with retry + proxy support |
| `RSSFetcher` | `trendradar/crawler/rss/fetcher.py` | RSS feed fetcher with freshness filtering (max_age_days) |

### Three report modes

- **`incremental`** — Only newly appeared titles since last crawl. No push if nothing new.
- **`current`** — Current hotlist + new titles section. Pushes on schedule.
- **`daily`** — All titles from the entire day (cumulative). Pushes on schedule.

The mode is set in `config.yaml` (`REPORT_MODE`) and can be overridden per time period by the scheduler.

### Two filter methods

- **`keyword`** (default) — Match titles against `config/frequency_words.txt` word groups + filter words.
- **`ai`** — Use AI to extract interest tags from `config/ai_interests.txt`, then classify news by tag. Controlled by `filter.method` in config.

### Display modes

- **`keyword`** — Group results by matched keyword (shows `[source]` tag per title).
- **`platform`** — Group results by platform (shows `[keyword]` tag per title). Uses `convert_keyword_stats_to_platform_stats()`.

## Configuration

### Required files

| File | Purpose |
|------|---------|
| `config/config.yaml` | Main config: platforms, notification webhooks, AI keys, storage, schedule |
| `config/frequency_words.txt` | Keyword groups for matching (blank-line separated groups, one keyword per line) |
| `config/timeline.yaml` | Optional: time-period schedule overrides (periods + day_plans + week_map) |
| `config/ai_interests.txt` | Optional: AI filter interests (used when `filter.method: "ai"`) |

### Environment variable overrides

Most config values can be overridden via env vars. Key ones:
- `FEISHU_WEBHOOK_URL`, `DINGTALK_WEBHOOK_URL`, `WEWORK_WEBHOOK_URL`, etc. — notification webhooks (support `;` separator for multi-account)
- `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL` — AI provider settings
- `MAX_NEWS_PER_KEYWORD`, `MAX_ACCOUNTS_PER_CHANNEL` — limits (⚠️ setting to `0` via env var is silently ignored due to `or` chain bug in loader.py lines 93, 112)
- `LOCAL_RETENTION_DAYS`, `REMOTE_RETENTION_DAYS` — data cleanup (⚠️ same `0` bug at lines 384, 392)
- `CRON_SCHEDULE`, `RUN_MODE` — Docker container settings

## Storage

- SQLite databases stored in `output/news/` (hotlists) and `output/rss/` (RSS).
- Each day gets one `.db` file. Each crawl creates a timestamped record within the day's DB.
- Optional TXT snapshots in `output/txt/{date}/`.
- HTML reports in `output/html/{date}/` + `output/html/latest/{mode}.html`.
- Remote sync to S3-compatible storage (R2, COS, OSS) configured via `STORAGE.REMOTE.*`.

## MCP server

A separate read-only query layer (`mcp_server/`) provides MCP protocol tools for AI clients. It reads SQLite files directly (bypasses StorageManager). Provides tools for: data query, analytics, search, config management, notification testing, storage sync, article reading. Uses FastMCP 2.0, supports stdio and HTTP transports.

## Key conventions

- **Time handling**: All times in configured timezone (default `Asia/Shanghai`). Use `AppContext.get_time()` / `.format_date()` / `.format_time()` instead of `datetime.now()`.
- **CamelCase vs snake_case**: Storage layer uses camelCase keys (`mobileUrl`, `sourceName`). Processed/report data uses snake_case (`mobile_url`, `source_name`). Be careful when crossing the boundary — `prepare_report_data()` in `generator.py` translates between them, but AI filter pipeline (`filter_pipeline.py:564`) produces snake_case directly, causing a mismatch.
- **Encoding**: Config/frequency files are read with `utf-8`. Using `utf-8-sig` would prevent BOM corruption from Windows Notepad (see `frequency.py:136`).
- **Batch mode**: Storage backends support `begin_batch()` / `end_batch()` for atomic multi-write. Always ensure `end_batch()` is called in a `finally` block.
- **Notification format dispatch**: Uses `if format_type == "feishu": ... elif "dingtalk": ...` chains in splitter, renderer, formatter, and senders. Adding a new platform requires touching all 4 files in ~20 locations each.
