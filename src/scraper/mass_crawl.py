"""Mass crawl driver: loops target/city combos, writes to configured storage."""

from typing import Any

import structlog

from scraper.config import Settings
from scraper.sqlite_writer import SQLiteWriter
from scraper.storage import Backend, open_connection, placeholder, storage_target

log = structlog.get_logger()

# 30 minutes stale threshold
_STALE_MINUTES = 30
_TARGET_TABLES = {
    "category": "categories",
    "brand": "brands",
    "keyword": "keywords",
}
ARABIC_ROLE_SEARCH_TERMS = {
    "مصنع",
    "استيراد",
    "تصدير",
    "استيراد وتصدير",
    "توزيع",
}
RELATED_CATEGORY_TARGETS = {
    "import-&-export",
    "import-export",
    "import export",
    "factory",
    "factories",
    "استيراد وتصدير",
    "مصنع",
    "distribution",
    "توزيع",
}
RELATED_KEYWORD_TARGETS = {
    "import",
    "export",
    "factory",
    "استيراد",
    "تصدير",
    "مصنع",
    "distribution",
    "توزيع",
}


def _row_value(row: Any, key: str, index: int) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]


def _reset_stale_jobs(conn: Any, backend: Backend = "sqlite") -> None:
    """Reset stale 'running' jobs to 'failed' on startup."""
    if backend == "postgres":
        conn.execute(
            f"""UPDATE scrape_jobs SET status='failed', error='stale: process died'
            WHERE status='running'
            AND started_at < now() - interval '{_STALE_MINUTES} minutes'"""
        )
    else:
        conn.execute(
            f"""UPDATE scrape_jobs SET status='failed', error='stale: process died'
            WHERE status='running'
            AND started_at < datetime('now', '-{_STALE_MINUTES} minutes', 'localtime')"""
        )
    conn.commit()


def _get_or_create_job(
    conn: Any,
    target_slug: str,
    city_slug: str = "",
    target_type: str = "category",
    backend: Backend = "sqlite",
) -> dict[str, Any]:
    """Get existing job or create new pending job. Returns job dict."""
    ph = placeholder(backend)
    conflict = "ON CONFLICT DO NOTHING" if backend == "postgres" else "OR IGNORE"
    conn.execute(
        f"""INSERT {conflict if backend == "sqlite" else ""} INTO scrape_jobs
        (target_type, target_slug, category_slug, city_slug, status)
        VALUES ({ph}, {ph}, {ph}, {ph}, 'pending')
        {conflict if backend == "postgres" else ""}""",
        (target_type, target_slug, target_slug, city_slug),
    )
    row = conn.execute(
        f"""SELECT id, status, pages_scraped, rows_written
        FROM scrape_jobs
        WHERE target_type={ph} AND target_slug={ph} AND city_slug={ph}""",
        (target_type, target_slug, city_slug),
    ).fetchone()
    return {
        "id": _row_value(row, "id", 0),
        "status": _row_value(row, "status", 1),
        "pages_scraped": _row_value(row, "pages_scraped", 2),
        "rows_written": _row_value(row, "rows_written", 3),
    }


def _mark_running(conn: Any, job_id: int, backend: Backend = "sqlite") -> None:
    ph = placeholder(backend)
    now_expr = "now()" if backend == "postgres" else "datetime('now', 'localtime')"
    conn.execute(
        f"""UPDATE scrape_jobs
        SET status='running', started_at={now_expr}, error=''
        WHERE id={ph}""",
        (job_id,),
    )
    conn.commit()


def _claim_job(conn: Any, job_id: int, backend: Backend = "sqlite") -> bool:
    """Atomically claim a pending/failed job for this process."""
    ph = placeholder(backend)
    now_expr = "now()" if backend == "postgres" else "datetime('now', 'localtime')"
    cursor = conn.execute(
        f"""UPDATE scrape_jobs
        SET status='running',
            started_at={now_expr},
            finished_at=NULL,
            error='',
            pages_scraped=0,
            rows_written=0
        WHERE id={ph} AND status IN ('pending', 'failed')""",
        (job_id,),
    )
    conn.commit()
    return bool(cursor.rowcount == 1)


def _mark_progress(
    conn: Any,
    job_id: int,
    pages: int,
    rows: int,
    backend: Backend = "sqlite",
) -> None:
    ph = placeholder(backend)
    conn.execute(
        f"""UPDATE scrape_jobs
        SET pages_scraped={ph}, rows_written={ph}
        WHERE id={ph} AND status='running'""",
        (pages, rows, job_id),
    )
    conn.commit()


def _mark_done(
    conn: Any,
    job_id: int,
    pages: int,
    rows: int,
    backend: Backend = "sqlite",
) -> None:
    ph = placeholder(backend)
    now_expr = "now()" if backend == "postgres" else "datetime('now', 'localtime')"
    conn.execute(
        f"""UPDATE scrape_jobs
        SET status='done',
            finished_at={now_expr},
            pages_scraped={ph},
            rows_written={ph}
        WHERE id={ph}""",
        (pages, rows, job_id),
    )
    conn.commit()


def _should_skip_done_job(target_type: str, target_slug: str, job: dict[str, Any]) -> bool:
    if job["status"] != "done":
        return False
    if target_type in {"category", "keyword"} and target_slug in ARABIC_ROLE_SEARCH_TERMS:
        return (job.get("rows_written") or 0) > 0
    return True


def _mark_failed(conn: Any, job_id: int, error: str, backend: Backend = "sqlite") -> None:
    ph = placeholder(backend)
    now_expr = "now()" if backend == "postgres" else "datetime('now', 'localtime')"
    conn.execute(
        f"""UPDATE scrape_jobs
        SET status='failed', finished_at={now_expr}, error={ph}
        WHERE id={ph}""",
        (error, job_id),
    )
    conn.commit()


def _load_targets(
    conn: Any,
    target_types: list[str],
    target_slugs_by_type: dict[str, list[str]] | None = None,
    backend: Backend = "sqlite",
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    target_slugs_by_type = target_slugs_by_type or {}
    for target_type in target_types:
        if target_type == "brand" and target_type not in target_slugs_by_type:
            continue
        table = _TARGET_TABLES[target_type]
        selected_slugs = target_slugs_by_type.get(target_type) or []
        if selected_slugs:
            placeholders = ",".join(placeholder(backend) for _ in selected_slugs)
            rows = conn.execute(
                f"SELECT slug FROM {table} WHERE slug IN ({placeholders}) ORDER BY name",
                selected_slugs,
            ).fetchall()
        else:
            allowed_terms = (
                RELATED_CATEGORY_TARGETS
                if target_type == "category"
                else RELATED_KEYWORD_TARGETS
                if target_type == "keyword"
                else set()
            )
            ph = placeholder(backend)
            target_search_clause = (
                f"LOWER(slug) LIKE LOWER({ph}) "
                f"OR LOWER(name) LIKE LOWER({ph}) "
                f"OR LOWER(href) LIKE LOWER({ph})"
            )
            search_clause = " OR ".join(
                target_search_clause
                for _ in allowed_terms
            )
            params = [
                f"%{term}%"
                for term in allowed_terms
                for _ in range(3)
            ]
            rows = conn.execute(
                f"SELECT slug FROM {table} WHERE {search_clause} ORDER BY name",
                params,
            ).fetchall()
        targets.extend((target_type, _row_value(row, "slug", 0)) for row in rows)
    return targets


def _load_cities(conn: Any, mode: str) -> list[str]:
    if mode == "none":
        return [""]
    limit = " LIMIT 10" if mode == "top" else ""
    rows = conn.execute(
        f"""SELECT slug FROM locations
        WHERE type='city'
        ORDER BY result_count DESC, name{limit}"""
    ).fetchall()
    return [_row_value(row, "slug", 0) for row in rows] or [""]


def run_mass_crawl(
    db_path: str | None = None,
    max_pages: int | None = None,
    use_proxies: bool = False,
    headless: bool = True,
    dry_run: bool = False,
    target_types: list[str] | None = None,
    target_slugs_by_type: dict[str, list[str]] | None = None,
    cities: str = "all",
    city_slugs: list[str] | None = None,
) -> int:
    """Main mass crawl loop. Returns total rows written."""
    cfg = Settings()
    if max_pages is None:
        max_pages = cfg.mass_crawl_max_pages

    active_target = storage_target(db_path, cfg)
    conn, backend = open_connection(active_target)

    _reset_stale_jobs(conn, backend)

    if target_types is None:
        target_types = ["category"]

    targets = _load_targets(conn, target_types, target_slugs_by_type, backend)
    city_slugs = city_slugs if city_slugs is not None else _load_cities(conn, cities)
    if not city_slugs:
        city_slugs = [""]

    if not targets:
        log.warning("no_taxonomy", msg="No crawl targets in DB. Run 'taxonomy' first.")
        conn.close()
        return 0

    # Pre-populate scrape_jobs for all target/city combos
    ph = placeholder(backend)
    insert_ignore = "OR IGNORE " if backend == "sqlite" else ""
    on_conflict = " ON CONFLICT DO NOTHING" if backend == "postgres" else ""
    for target_type, target_slug in targets:
        for city in city_slugs:
            conn.execute(
                f"""INSERT {insert_ignore}INTO scrape_jobs
                (target_type, target_slug, category_slug, city_slug, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, 'pending'){on_conflict}""",
                (target_type, target_slug, target_slug, city),
            )
    conn.commit()
    log.info("jobs_populated", targets=len(targets), cities=len(city_slugs))

    if dry_run:
        _print_dry_run_summary(conn)
        conn.close()
        return 0

    # Build pipeline
    from scraper.http_client import Tier1Client, Tier2Client
    from scraper.pipeline import Pipeline
    from scraper.proxy_pool import ProxyPool
    from scraper.rate_limiter import RateLimiter

    tiers = [Tier1Client(), Tier2Client()]
    if headless:
        from scraper.browser_client import Tier3Client
        tiers.append(Tier3Client(headless=headless))
    pipeline = Pipeline(tiers=tiers)
    rate_limiter = RateLimiter(
        min_delay=cfg.rate_limit_min_delay,
        max_delay=cfg.rate_limit_max_delay,
    )
    proxy_pool = ProxyPool([], checker=lambda _: True)

    if backend == "postgres":
        from scraper.postgres_writer import PostgresWriter

        writer: Any = PostgresWriter(str(active_target))
    else:
        writer = SQLiteWriter(active_target, conn=conn)

    total_rows = 0
    for target_type, target_slug in targets:
        for city in city_slugs:
            job = _get_or_create_job(conn, target_slug, city, target_type, backend)
            if _should_skip_done_job(target_type, target_slug, job):
                log.info("job_skip_done", target_type=target_type, target=target_slug, city=city)
                continue
            if job["status"] == "done":
                _mark_failed(
                    conn,
                    job["id"],
                    "retrying zero-row Arabic role search job",
                    backend,
                )
                job["status"] = "failed"
            if job["status"] == "running":
                log.info(
                    "job_skip_running",
                    target_type=target_type,
                    target=target_slug,
                    city=city,
                )
                continue
            if not _claim_job(conn, job["id"], backend):
                log.info(
                    "job_claim_missed",
                    target_type=target_type,
                    target=target_slug,
                    city=city,
                )
                continue

            pages_scraped = 0
            rows_written = 0
            try:
                from scraper.sites.yellowpages_eg import scrape_target

                def progress_callback(pages: int, rows: int) -> None:
                    nonlocal pages_scraped, rows_written
                    pages_scraped = pages
                    rows_written = rows
                    _mark_progress(conn, job["id"], pages_scraped, rows_written, backend)

                rows_written = scrape_target(
                    target_type=target_type,
                    slug=target_slug,
                    city_slug=city or None,
                    pipeline=pipeline,
                    csv_writer=writer,
                    rate_limiter=rate_limiter,
                    proxy_pool=proxy_pool,
                    max_pages=max_pages,
                    consecutive_empty_halt=cfg.consecutive_empty_halt,
                    progress_callback=progress_callback,
                )
                _mark_done(conn, job["id"], pages_scraped, rows_written, backend)
                total_rows += rows_written
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
                _mark_failed(conn, job["id"], error, backend)
                log.error(
                    "job_failed",
                    target_type=target_type,
                    target=target_slug,
                    city=city,
                    error=error,
                )

    conn.close()
    log.info("mass_crawl_done", total_rows=total_rows)
    return total_rows


def _print_dry_run_summary(conn: Any) -> None:
    """Print job counts for dry-run mode."""
    rows = conn.execute(
        """SELECT status, COUNT(*) AS jobs,
        SUM(pages_scraped) AS pages, SUM(rows_written) AS rows
        FROM scrape_jobs GROUP BY status"""
    ).fetchall()
    print("=== Dry Run: Job Summary ===")
    for row in rows:
        print(
            f"  {_row_value(row, 'status', 0)}: {_row_value(row, 'jobs', 1)} jobs, "
            f"{_row_value(row, 'pages', 2) or 0} pages, "
            f"{_row_value(row, 'rows', 3) or 0} rows"
        )
    row = conn.execute("SELECT COUNT(*) AS count FROM scrape_jobs WHERE status='pending'").fetchone()
    pending = _row_value(row, 'count', 0)
    print(f"  Total pending jobs: {pending}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--use-proxies", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target-types", default="category")
    parser.add_argument("--cities", default="all")
    args = parser.parse_args()
    run_mass_crawl(
        db_path=args.db_path,
        max_pages=args.max_pages,
        use_proxies=args.use_proxies,
        headless=not args.no_browser,
        dry_run=args.dry_run,
        target_types=[p.strip() for p in args.target_types.split(",") if p.strip()],
        cities=args.cities,
    )
