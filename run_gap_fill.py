#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gap-fill scraper: Runs targeted scraping for all URLs identified in the gap report.

Targets (from yp_data_gap_report.md):
- /en/search/import          (2,595 est.)
- /en/search/export          (2,107 est.)
- /en/category/import-&-export (1,172 est.)
- /ar/category/import-&-export (~1,172 est.)
- /en/search/factory         (1,018 est.)
- /ar/search/factory         (~1,018 est.)
- /ar/search/distribution    (641 est.)
- /en/category/factory-equipment-and-supplies (unknown)
- /ar/search/import          (~2,595 est.)
- /ar/search/export          (~2,107 est.)
"""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import structlog
from scraper.config import Settings
from scraper.storage import open_connection, storage_target
from scraper.postgres_db import get_connection, init_db
from scraper.postgres_writer import PostgresWriter
from scraper.http_client import Tier1Client, Tier2Client
from scraper.pipeline import Pipeline
from scraper.rate_limiter import RateLimiter
from scraper.proxy_pool import ProxyPool
from scraper.sites.yellowpages_eg import scrape_target

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

DATABASE_URL = (
    "postgresql://postgres.brmljayacipdhfgppuzk:"
    "scrapping-database%40123@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"
)

# ALL gap targets: (target_type, slug, language)
# The scraper's build_target_url uses SEARCH_ALIASES for these:
#   factory/import/export/distribution  -> /en/search/<slug>
#   مصنع/استيراد/تصدير/توزيع           -> /en/search/<arabic> (Arabic role search)
# For import-&-export category we use target_type="category"

GAP_TARGETS = [
    # English keyword search pages (HIGH priority)
    ("keyword", "import"),
    ("keyword", "export"),
    ("keyword", "factory"),
    ("keyword", "distribution"),
    # Arabic keyword search pages (HIGH priority)
    ("keyword", "استيراد"),
    ("keyword", "تصدير"),
    ("keyword", "مصنع"),
    ("keyword", "توزيع"),
    # Category pages (HIGH priority)
    ("category", "import-&-export"),
    ("category", "factory"),
    ("category", "factory-equipment-and-supplies"),
    ("category", "distribution"),
    # Arabic category equivalents
    ("category", "استيراد وتصدير"),
    ("category", "مصنع"),
    ("category", "توزيع"),
]

MAX_PAGES = 120  # Each YP page has ~20 listings; 120 pages = ~2,400 per target
CONSECUTIVE_EMPTY_HALT = 5


def reset_stale_jobs(conn):
    """Reset any stale running jobs back to pending so they get re-run."""
    cursor = conn.execute(
        """UPDATE scrape_jobs SET status='pending', error='reset: stale gap-fill restart'
        WHERE status='running'
        AND started_at < now() - interval '30 minutes'"""
    )
    conn.commit()
    if cursor.rowcount:
        print(f"Reset {cursor.rowcount} stale running jobs to pending")


def ensure_targets_in_db(conn):
    """Make sure all gap target slugs exist in categories/keywords tables."""
    category_targets = [
        ("import-&-export", "Import & Export", "/en/category/import-&-export"),
        ("factory", "Factory", "/en/search/factory"),
        ("factory-equipment-and-supplies", "Factory Equipment & Supplies", "/en/category/factory-equipment-and-supplies"),
        ("distribution", "Distribution", "/en/search/distribution"),
        ("استيراد وتصدير", "استيراد وتصدير", "/en/category/import-&-export"),
        ("مصنع", "مصنع", "/en/search/factory"),
        ("توزيع", "توزيع", "/ar/search/distribution"),
    ]
    keyword_targets = [
        ("import", "Import", "/en/search/import"),
        ("export", "Export", "/en/search/export"),
        ("factory", "Factory", "/en/search/factory"),
        ("distribution", "Distribution", "/ar/search/distribution"),
        ("استيراد", "استيراد", "/en/search/import"),
        ("تصدير", "تصدير", "/en/search/export"),
        ("مصنع", "مصنع", "/en/search/factory"),
        ("توزيع", "توزيع", "/ar/search/distribution"),
    ]
    for slug, name, href in category_targets:
        conn.execute(
            """INSERT INTO categories (slug, name, parent_slug, result_count, href, scraped_at)
            VALUES (%s, %s, '', 0, %s, '')
            ON CONFLICT (slug) DO UPDATE SET href=EXCLUDED.href""",
            (slug, name, href),
        )
    for slug, name, href in keyword_targets:
        conn.execute(
            """INSERT INTO keywords (slug, name, href, scraped_at)
            VALUES (%s, %s, %s, '')
            ON CONFLICT (slug) DO UPDATE SET href=EXCLUDED.href""",
            (slug, name, href),
        )
    conn.commit()
    print(f"Ensured {len(category_targets)} categories and {len(keyword_targets)} keywords exist in DB")


def get_or_create_job(conn, target_type, target_slug, city_slug=""):
    """Get existing job or create new pending one."""
    conn.execute(
        """INSERT INTO scrape_jobs
        (target_type, target_slug, category_slug, city_slug, status)
        VALUES (%s, %s, %s, %s, 'pending')
        ON CONFLICT (target_type, target_slug, city_slug) DO NOTHING""",
        (target_type, target_slug, target_slug, city_slug),
    )
    conn.commit()
    row = conn.execute(
        """SELECT id, status, rows_written FROM scrape_jobs
        WHERE target_type=%s AND target_slug=%s AND city_slug=%s""",
        (target_type, target_slug, city_slug),
    ).fetchone()
    return row


def claim_job(conn, job_id):
    """Atomically claim a pending/failed job."""
    cursor = conn.execute(
        """UPDATE scrape_jobs
        SET status='running', started_at=now(), finished_at=NULL, error='', pages_scraped=0, rows_written=0
        WHERE id=%s AND status IN ('pending', 'failed')""",
        (job_id,),
    )
    conn.commit()
    return cursor.rowcount == 1


def mark_done(conn, job_id, pages, rows):
    conn.execute(
        """UPDATE scrape_jobs
        SET status='done', finished_at=now(), pages_scraped=%s, rows_written=%s
        WHERE id=%s""",
        (pages, rows, job_id),
    )
    conn.commit()


def mark_failed(conn, job_id, error):
    conn.execute(
        """UPDATE scrape_jobs
        SET status='failed', finished_at=now(), error=%s
        WHERE id=%s""",
        (error, job_id),
    )
    conn.commit()


def mark_progress(conn, job_id, pages, rows):
    conn.execute(
        """UPDATE scrape_jobs SET pages_scraped=%s, rows_written=%s
        WHERE id=%s AND status='running'""",
        (pages, rows, job_id),
    )
    conn.commit()


def main():
    cfg = Settings()

    print("Connecting to Supabase Postgres...")
    conn = get_connection(DATABASE_URL)
    init_db(conn)

    reset_stale_jobs(conn)
    ensure_targets_in_db(conn)

    # Build pipeline
    tiers = [Tier1Client(), Tier2Client()]
    pipeline = Pipeline(tiers=tiers)
    rate_limiter = RateLimiter(
        min_delay=cfg.rate_limit_min_delay,
        max_delay=cfg.rate_limit_max_delay,
    )
    proxy_pool = ProxyPool([], checker=lambda _: True)
    writer = PostgresWriter(DATABASE_URL)

    total_written = 0
    for target_type, target_slug in GAP_TARGETS:
        print(f"\n{'='*60}")
        print(f"TARGET: [{target_type}] {target_slug}")
        print(f"{'='*60}")

        job = get_or_create_job(conn, target_type, target_slug, city_slug="")
        if job is None:
            print(f"  ERROR: Could not get/create job for {target_slug}")
            continue

        job_id = job["id"]
        status = job["status"]

        if status == "done" and (job.get("rows_written") or 0) > 0:
            print(f"  SKIP: Already done with {job['rows_written']} rows")
            continue

        if status == "running":
            print(f"  SKIP: Already running")
            continue

        if not claim_job(conn, job_id):
            print(f"  SKIP: Could not claim job (status={status})")
            continue

        pages_scraped = 0
        rows_written = 0

        def progress_cb(pages, rows):
            nonlocal pages_scraped, rows_written
            pages_scraped = pages
            rows_written = rows
            mark_progress(conn, job_id, pages, rows)
            if pages % 5 == 0:
                print(f"  Progress: page {pages}, rows written so far: {rows}")

        try:
            print(f"  Scraping {target_type} '{target_slug}' (max {MAX_PAGES} pages)...")
            rows_written = scrape_target(
                target_type=target_type,
                slug=target_slug,
                city_slug=None,
                pipeline=pipeline,
                csv_writer=writer,
                rate_limiter=rate_limiter,
                proxy_pool=proxy_pool,
                max_pages=MAX_PAGES,
                consecutive_empty_halt=CONSECUTIVE_EMPTY_HALT,
                progress_callback=progress_cb,
            )
            mark_done(conn, job_id, pages_scraped, rows_written)
            total_written += rows_written
            print(f"  DONE: {rows_written} new rows written, {pages_scraped} pages scraped")
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            mark_failed(conn, job_id, error)
            print(f"  FAILED: {error}")
            log.error("job_failed", target=target_slug, error=error)

    # Final stats
    conn_check = get_connection(DATABASE_URL)
    row = conn_check.execute("SELECT COUNT(*) AS cnt FROM businesses").fetchone()
    print(f"\n{'='*60}")
    print(f"GAP-FILL COMPLETE")
    print(f"New rows written this run: {total_written}")
    print(f"Total businesses in Supabase: {row['cnt']}")
    conn_check.close()
    conn.close()


if __name__ == "__main__":
    main()
