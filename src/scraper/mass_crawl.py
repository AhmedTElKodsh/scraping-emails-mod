"""Mass crawl driver: loops (category, city) combos, writes to SQLite via ResultWriter."""

from typing import Any

import structlog

from scraper.config import Settings
from scraper.db import get_connection, init_db
from scraper.sqlite_writer import SQLiteWriter

log = structlog.get_logger()

# 30 minutes stale threshold
_STALE_MINUTES = 30
_TARGET_TABLES = {
    "category": "categories",
    "brand": "brands",
    "keyword": "keywords",
}


def _reset_stale_jobs(conn: Any) -> None:
    """Reset stale 'running' jobs to 'failed' on startup."""
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
) -> dict[str, Any]:
    """Get existing job or create new pending job. Returns job dict."""
    conn.execute(
        """INSERT OR IGNORE INTO scrape_jobs
        (target_type, target_slug, category_slug, city_slug, status)
        VALUES (?, ?, ?, ?, 'pending')""",
        (target_type, target_slug, target_slug, city_slug),
    )
    row = conn.execute(
        """SELECT id, status, pages_scraped, rows_written
        FROM scrape_jobs
        WHERE target_type=? AND target_slug=? AND city_slug=?""",
        (target_type, target_slug, city_slug),
    ).fetchone()
    return {"id": row[0], "status": row[1], "pages_scraped": row[2], "rows_written": row[3]}


def _mark_running(conn: Any, job_id: int) -> None:
    conn.execute(
        """UPDATE scrape_jobs
        SET status='running', started_at=datetime('now', 'localtime'), error=''
        WHERE id=?""",
        (job_id,),
    )
    conn.commit()


def _mark_done(conn: Any, job_id: int, pages: int, rows: int) -> None:
    conn.execute(
        """UPDATE scrape_jobs
        SET status='done',
            finished_at=datetime('now', 'localtime'),
            pages_scraped=?,
            rows_written=?
        WHERE id=?""",
        (pages, rows, job_id),
    )
    conn.commit()


def _mark_failed(conn: Any, job_id: int, error: str) -> None:
    conn.execute(
        """UPDATE scrape_jobs
        SET status='failed', finished_at=datetime('now', 'localtime'), error=?
        WHERE id=?""",
        (error, job_id),
    )
    conn.commit()


def _load_targets(
    conn: Any,
    target_types: list[str],
    target_slugs_by_type: dict[str, list[str]] | None = None,
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    target_slugs_by_type = target_slugs_by_type or {}
    for target_type in target_types:
        table = _TARGET_TABLES[target_type]
        selected_slugs = target_slugs_by_type.get(target_type) or []
        if selected_slugs:
            placeholders = ",".join("?" for _ in selected_slugs)
            rows = conn.execute(
                f"SELECT slug FROM {table} WHERE slug IN ({placeholders}) ORDER BY name",
                selected_slugs,
            ).fetchall()
        else:
            rows = conn.execute(f"SELECT slug FROM {table} ORDER BY name").fetchall()
        targets.extend((target_type, row[0]) for row in rows)
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
    return [row[0] for row in rows] or [""]


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

    conn = get_connection(db_path or cfg.db_path)
    init_db(conn)

    _reset_stale_jobs(conn)

    if target_types is None:
        target_types = ["category"]

    targets = _load_targets(conn, target_types, target_slugs_by_type)
    city_slugs = city_slugs if city_slugs is not None else _load_cities(conn, cities)
    if not city_slugs:
        city_slugs = [""]

    if not targets:
        log.warning("no_taxonomy", msg="No crawl targets in DB. Run 'taxonomy' first.")
        conn.close()
        return 0

    # Pre-populate scrape_jobs for all target/city combos
    for target_type, target_slug in targets:
        for city in city_slugs:
            conn.execute(
                """INSERT OR IGNORE INTO scrape_jobs
                (target_type, target_slug, category_slug, city_slug, status)
                VALUES (?, ?, ?, ?, 'pending')""",
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
    if not headless:
        from scraper.browser_client import Tier3Client
        tiers.append(Tier3Client(headless=headless))
    pipeline = Pipeline(tiers=tiers)
    rate_limiter = RateLimiter(
        min_delay=cfg.rate_limit_min_delay,
        max_delay=cfg.rate_limit_max_delay,
    )
    proxy_pool = ProxyPool([], checker=lambda _: True)

    writer = SQLiteWriter(db_path or cfg.db_path)

    total_rows = 0
    for target_type, target_slug in targets:
        for city in city_slugs:
            job = _get_or_create_job(conn, target_slug, city, target_type)
            if job["status"] == "done":
                log.info("job_skip_done", target_type=target_type, target=target_slug, city=city)
                continue
            if job["status"] == "failed":
                conn.execute("UPDATE scrape_jobs SET status='pending' WHERE id=?", (job["id"],))
                conn.commit()

            _mark_running(conn, job["id"])
            try:
                from scraper.sites.yellowpages_eg import scrape_target
                pages_written = scrape_target(
                    target_type=target_type,
                    slug=target_slug,
                    city_slug=city or None,
                    pipeline=pipeline,
                    csv_writer=writer,
                    rate_limiter=rate_limiter,
                    proxy_pool=proxy_pool,
                    max_pages=max_pages,
                    consecutive_empty_halt=cfg.consecutive_empty_halt,
                )
                _mark_done(conn, job["id"], max_pages, pages_written)
                total_rows += pages_written
            except Exception as e:
                _mark_failed(conn, job["id"], str(e))
                log.error(
                    "job_failed",
                    target_type=target_type,
                    target=target_slug,
                    city=city,
                    error=str(e),
                )

    conn.close()
    log.info("mass_crawl_done", total_rows=total_rows)
    return total_rows


def _print_dry_run_summary(conn: Any) -> None:
    """Print job counts for dry-run mode."""
    rows = conn.execute(
        """SELECT status, COUNT(*), SUM(pages_scraped), SUM(rows_written)
        FROM scrape_jobs GROUP BY status"""
    ).fetchall()
    print("=== Dry Run: Job Summary ===")
    for row in rows:
        print(f"  {row[0]}: {row[1]} jobs, {row[2] or 0} pages, {row[3] or 0} rows")
    pending = conn.execute("SELECT COUNT(*) FROM scrape_jobs WHERE status='pending'").fetchone()[0]
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
