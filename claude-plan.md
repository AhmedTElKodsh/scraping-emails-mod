# Plan: Streamlit UI + SQLite-backed Mass Crawl

## Context

User wants a UI where they choose **Category** and **Location** (City / Area / District) and view scraped business contacts. Decision: full upfront mass crawl (capped at **20 pages per category×city combo** for v1) populates a **SQLite DB**; **Streamlit** app reads from DB and offers filter + export. Brands/Keywords deferred to v2.

Today the scraper only runs one `category/governorate` from CLI and writes to per-run CSVs. We need: taxonomy discovery (categories + cities + areas + districts from YP), a SQLite store, a mass-crawl driver, and the Streamlit front end.

## Scope (v1)

- Filters: Category, City, Area, District — all **cascading dropdowns populated from DB** (YP-sourced taxonomy only, no free-text location entry).
- Mass crawl: every `(category, city)` combo, 20 pages each. Area/district are **not crawl parameters** (YP `?city=` only); they are stored in the `locations` table with parent relationships and used to filter the **viewing layer** via `businesses.city_slug` + area/district dropdown selection against the taxonomy hierarchy.
- DB-backed write path replacing CSV for crawl results. CSV export (deduped across categories) available from UI.
- Crawl resumability via `scrape_jobs` status rows. Stale `running` jobs reset to `failed` on `mass_crawl.py` startup.
- Freshness: `scraped_at` visible in UI and in exported CSV.
- Empty results: UI distinguishes "never crawled" vs "crawled, zero results" vs "filter matched nothing."

## Architecture

```
[YP taxonomy pages] --crawl--> taxonomy.py --> SQLite (categories, locations hierarchy)
[YP listing pages]  --crawl--> mass_crawl.py + scrape_category --> SQLite (businesses, scrape_jobs)
                                                                    ^
                                                                    |
                                              Streamlit app reads + filters (taxonomy dropdowns) + exports
```

**Crawl launch from UI**: `threading.Thread` (not `subprocess.Popen`) spawned from Streamlit, guarded by `st.session_state['crawl_running']` flag to prevent double-launch. Log output written to a rotating log file; Streamlit reads via `st.code(open(logfile).read())` + manual refresh button (no blocking readline loop). Thread sets `st.session_state['crawl_running'] = False` on completion/exception.

**SQLite concurrency**: WAL mode enabled at connection init (`PRAGMA journal_mode=WAL`). `mass_crawl.py` / `taxonomy.py` are the only writers. Streamlit is read-only. Connection-per-thread, `check_same_thread=False`.

## Files

### New

- **`src/scraper/db.py`** — SQLite connection factory (`get_connection(db_path)`), schema init (`init_db(conn)`), WAL mode enable. Schema only — no writer class here.
  - `init_db` calls `CREATE TABLE IF NOT EXISTS` for all tables. Called explicitly by CLI subcommands (`taxonomy`, `crawl-all`) and by `SQLiteWriter.__init__`. Never at import time.
  - Schema:
    - `categories(slug PK, name, parent_slug, scraped_at)`
    - `locations(slug PK, name, type CHECK IN ('city','area','district'), parent_slug, scraped_at)` — `parent_slug` FK to `locations.slug` for city→area→district hierarchy.
    - `businesses(id PK, source_url UNIQUE, business_name, category_slug FK, city_slug FK, phone, email, website, facebook_url, address, raw_html_hash, source_tier, scraped_at)` — index on `(category_slug, city_slug)`.
    - `scrape_jobs(id PK, category_slug, city_slug, status TEXT CHECK IN ('pending','running','done','failed'), pages_scraped, rows_written, started_at, finished_at, error)` — UNIQUE on `(category_slug, city_slug)`.

- **`src/scraper/sqlite_writer.py`** — `SQLiteWriter` implementing `ResultWriter` Protocol. Uses `INSERT OR IGNORE INTO businesses` (conflict on `source_url` silently skipped — persistent cross-run dedup via DB constraint). `write(result) -> int` returns 1 if inserted, 0 if duplicate. No in-memory seen-sets; DB constraint is the authority.

- **`src/scraper/taxonomy.py`** — fetch YP categories and locations pages, parse with `selectolax`, populate `categories` and `locations` tables. Idempotent (`INSERT OR REPLACE`).
  - **Primary source**: hardcoded seed JSON (`data/taxonomy_seed.json`) with known categories, cities, areas, districts. Taxonomy crawl *refreshes* from live YP pages but is not required for app startup.
  - Seed JSON must be verified manually before first run (spot-check 5 categories × 3 cities against real YP URLs — see Verification #0 below).
  - Pagination on YP taxonomy pages: detect and follow if present; log a warning if page count exceeds expected threshold.
  - Areas and districts discovered and stored with `parent_slug` linking to their parent city/area.

- **`src/scraper/mass_crawl.py`** — main loop:
  ```python
  # On startup: reset stale running jobs
  conn.execute(
      "UPDATE scrape_jobs SET status='failed', error='stale: process died' "
      "WHERE status='running' AND started_at < datetime('now', '-30 minutes')"
  )

  for cat in categories:
      for city in cities:
          job = get_or_create_job(conn, cat, city)  # INSERT OR IGNORE, then SELECT
          if job.status == 'done':
              continue
          if job.status == 'failed':
              conn.execute("UPDATE scrape_jobs SET status='pending' WHERE id=?", (job.id,))
          mark_running(conn, job)
          try:
              rows = scrape_category(cat, city, ..., max_pages=max_pages, writer=SQLiteWriter(conn))
              mark_done(conn, job, rows)
          except Exception as e:
              mark_failed(conn, job, str(e))
  ```
  - `--dry-run` flag: prints job count (pending/done/failed breakdown) and exits without crawling.
  - Honors `consecutive_empty_halt` from `Settings`. Reuses existing `Pipeline`, `RateLimiter`, `proxy_pool`.
  - Runs with `PYTHONUNBUFFERED=1` (set in `cli.py` before spawning or documented for direct invocation).

- **`app/streamlit_app.py`** — Streamlit app:
  - Sidebar: Category select → City select (filtered by availability in `scrape_jobs`) → Area select (filtered by City from `locations` hierarchy) → District select (filtered by Area). All dropdowns from DB taxonomy — no free-text location input.
  - Main: dataframe of `businesses` with active filters, row count, `scraped_at` column visible, "Export CSV" button (`st.download_button` with in-memory `df.to_csv()` — no disk write).
  - Cross-category dedup on export: if same `source_url` appears in multiple category crawls, CSV contains it once (deduplicated by `source_url`).
  - Empty results: show explicit reason — "This combination has not been crawled yet" (no `scrape_jobs` row or status=pending) vs "Crawled but no results found" (status=done, zero rows) vs "Results exist but area/district filter matched none."
  - "Crawl status" expander: counts of pending/running/done/failed jobs, last crawl timestamp. "Run mass crawl" button: disabled if `st.session_state['crawl_running']` is True; spawns `threading.Thread(target=run_mass_crawl, daemon=True)`; logs to `data/crawl.log`; Streamlit reads log via `st.code` + "Refresh log" button.

- **`app/__init__.py`** — empty, marks `app/` as package.

- **`data/taxonomy_seed.json`** — hardcoded seed of known YP categories, cities, areas, districts. Source of truth for app startup. Updated by `taxonomy` crawl but not required to be fresh.

- **`tests/unit/test_db.py`** — uses `tmp_path` / `:memory:` SQLite, never touches `data/scraper.sqlite`. ACs:
  - `test_init_creates_all_tables`
  - `test_init_is_idempotent` (double-call does not raise)
  - `test_scrape_job_unique_constraint`
  - `test_business_unique_on_source_url`
  - `test_wal_mode_enabled`

- **`tests/unit/test_sqlite_writer.py`** — ACs:
  - `test_write_returns_1_on_insert`
  - `test_duplicate_source_url_returns_0_not_raises`
  - `test_dedup_persists_across_writer_instances` (two `SQLiteWriter` instances, same DB, same URL — second returns 0)
  - `test_null_email_handled`

- **`tests/unit/test_mass_crawl.py`** — mocks `scrape_category` and DB. ACs:
  - `test_done_job_skipped`
  - `test_failed_job_reset_to_pending_then_runs`
  - `test_stale_running_job_reset_to_failed_on_startup`
  - `test_exception_marks_job_failed_with_error_string`
  - `test_dry_run_prints_counts_no_crawl`

- **`tests/unit/test_taxonomy.py`** — unit tests against HTML fixtures (no live HTTP). ACs:
  - `test_parse_categories_from_fixture`
  - `test_parse_locations_hierarchy_from_fixture` (city → area → district)
  - `test_empty_page_returns_empty_list_not_raises`
  - `test_pagination_followed`

- **`tests/integration/test_taxonomy_live.py`** — hits real YP URLs, skipped in CI (`@pytest.mark.integration`). Verifies 3 known slugs. Not in default `pytest -q` run.

### Modified

- **`src/scraper/cli.py`** — add subcommands:
  - `scraper taxonomy [--db PATH] [--seed-only]` → `--seed-only` loads from `taxonomy_seed.json` without HTTP crawl; default refreshes from live pages.
  - `scraper crawl-all [--max-pages 20] [--db PATH] [--use-proxies] [--no-browser] [--dry-run]`
  - `scraper ui` → `subprocess.run([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py"])`.
  Existing `scrape` command preserved.

- **`src/scraper/config.py`** — add:
  - `db_path: str = "data/scraper.sqlite"`
  - `mass_crawl_max_pages: int = Field(20, ge=1)`
  - `taxonomy_seed_path: str = "data/taxonomy_seed.json"`

- **`src/scraper/csv_writer.py`** — extract `ResultWriter` Protocol (typing.Protocol):
  ```python
  class ResultWriter(Protocol):
      def write(self, result: ScrapeResult) -> int:
          """Write result. Return 1 if written, 0 if duplicate. Implementors MUST be idempotent on source_url."""
  ```
  `CSVWriter` implements this Protocol. Dedup contract on `CSVWriter` remains best-effort (in-process only) — documented in docstring. `SQLiteWriter` provides persistent cross-run dedup via DB constraint.

- **`pyproject.toml`** — add `streamlit`, `pandas` to deps.

### Untouched

- `sites/yellowpages_eg.py` parsing logic, `pipeline.py`, `http_client.py`, `browser_client.py`, `proxy_pool.py`, `rate_limiter.py`, `email_extract.py`, `models.py`.

## Reused existing utilities

- `scraper.sites.yellowpages_eg.scrape_category` (drives the crawl, writes via injected `ResultWriter`)
- `scraper.sites.yellowpages_eg.build_category_url` (same `?city=` URL shape)
- `scraper.pipeline.Pipeline` + tier escalation
- `scraper.rate_limiter.RateLimiter`
- `scraper.proxy_pool.ProxyPool`
- `scraper.models.ScrapeResult`

## URL/data assumptions (verify before coding)

1. **Manual pre-coding spot-check (Verification #0)**: Browse YP manually, confirm 5 category slugs + 3 city slugs produce valid listing URLs. Capture real area/district names for 2 cities into `taxonomy_seed.json`. This is a prerequisite — do not write code until seed JSON is populated.
2. YP categories listing page — check `https://yellowpages.com.eg/en/categories`. If JS-rendered, use existing `Tier3Client` (Playwright). Capture response as HTML fixture for unit tests.
3. YP locations page — check `https://yellowpages.com.eg/en/locations` for cities/areas/districts hierarchy. Capture as fixture.
4. `?city=` slug format — already known (`cairo`, `giza`, `el-dakahleya`). Confirm area/district slugs follow same pattern.
5. Area/district are taxonomy values from YP dropdowns, not free-text. Stored in `locations` table with `parent_slug`. Cascading dropdowns in UI constrained to DB values only.

## Verification

0. **Pre-coding**: Manual spot-check — 5 categories × 3 cities valid on YP. `taxonomy_seed.json` populated with real values.
1. `python -m scraper taxonomy --seed-only --db data/test.sqlite` → `categories` + `locations` tables non-empty from seed; spot-check 3 known slugs.
2. `python -m scraper crawl-all --db data/test.sqlite --max-pages 1 --no-browser --dry-run` → prints job count, exits clean, zero DB writes.
3. `python -m scraper crawl-all --db data/test.sqlite --max-pages 1 --no-browser` → `scrape_jobs` rows → `done`; `businesses` has rows; URLs unique.
4. Re-run #3 → all jobs skip (`status='done'`); zero new rows (idempotency).
5. Simulate stale job: manually `UPDATE scrape_jobs SET status='running', started_at=datetime('now','-60 minutes')` for one row; re-run #3 → that job resets to `failed` then re-runs.
6. `streamlit run app/streamlit_app.py` → all dropdowns populated from DB; selecting `restaurants`+`cairo` shows rows with `scraped_at`; selecting an area/district narrows results; empty combo shows explicit reason; "Export CSV" downloads deduped file.
7. Tests: `pytest -q` (no `integration` mark) — existing 97 + new unit tests all pass.
8. Sanity slice: `crawl-all --max-pages 20` for ~5 cat×city combos; verify row counts reasonable.

## Decisions resolved (from review)

| Decision | Resolution |
|---|---|
| Crawl launch mechanism | `threading.Thread` + `st.session_state` guard. No `subprocess.Popen`. |
| Taxonomy source | Seed JSON primary; live crawl optional refresh via `--seed-only` flag inverse |
| Area/district filter | Taxonomy dropdowns (YP-sourced values). No free-text. No substring match. |
| SQLite WAL mode | Explicit `PRAGMA journal_mode=WAL` in `get_connection()` |
| Writer ownership | `mass_crawl.py` / `taxonomy.py` write. Streamlit read-only. |
| `scrape_jobs` resume | `failed` → reset to `pending` on next run. `running` → reset to `failed` on startup if >30min old. |
| `ResultWriter` dedup contract | Protocol documents: implementors MUST be idempotent on `source_url`. `CSVWriter` = best-effort in-process. `SQLiteWriter` = persistent via `INSERT OR IGNORE`. |
| `SQLiteWriter` location | `src/scraper/sqlite_writer.py` (separate from `db.py`) |
| DB init caller | CLI subcommands and `SQLiteWriter.__init__`. Never at import time. |
| Subprocess Python path | `sys.executable` used everywhere — no bare `python` |
| Empty results UX | UI distinguishes: not crawled / crawled+empty / filter matched nothing |
| Freshness | `scraped_at` shown in UI dataframe and exported CSV |
| Cross-category dedup on export | Dedup by `source_url` in `df.to_csv()` path |

## Out of scope (v2+)

- Brands, Keywords, Letter filters (URL shape unknown).
- Live progress bar in Streamlit (log file + refresh button is v1).
- Multi-user / auth.
- Postgres migration.
- Auto-refresh of crawl log (manual refresh button is v1).
