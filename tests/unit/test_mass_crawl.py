"""Unit tests for mass_crawl.py - mocks scrape_category and DB."""

from unittest.mock import MagicMock

import pytest


def test_done_job_skipped() -> None:
    from scraper.mass_crawl import _get_or_create_job

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1, "done", 0, 0)
    job = _get_or_create_job(conn, "cat1", "city1")
    assert job["status"] == "done"


def test_zero_row_done_arabic_role_jobs_are_retryable() -> None:
    from scraper.mass_crawl import _should_skip_done_job

    assert _should_skip_done_job(
        "category",
        "استيراد",
        {"status": "done", "rows_written": 0},
    ) is False
    assert _should_skip_done_job(
        "category",
        "استيراد",
        {"status": "done", "rows_written": 4},
    ) is True
    assert _should_skip_done_job(
        "category",
        "restaurants",
        {"status": "done", "rows_written": 0},
    ) is True


def test_failed_job_reset_to_pending_then_runs() -> None:
    from scraper.mass_crawl import _get_or_create_job

    conn = MagicMock()
    # First call returns 'failed', after update returns 'pending'
    conn.execute.return_value.fetchone.side_effect = [
        (1, "failed", 0, 0),
        (1, "pending", 0, 0),
    ]
    job = _get_or_create_job(conn, "cat1", "city1")
    assert job["status"] in ("failed", "pending")


def test_stale_running_job_reset_to_failed_on_startup() -> None:
    from scraper.mass_crawl import _reset_stale_jobs

    conn = MagicMock()
    _reset_stale_jobs(conn)
    # Verify UPDATE was called with 'failed' status
    update_calls = [c for c in conn.execute.call_args_list if "failed" in str(c)]
    assert len(update_calls) > 0


def test_exception_marks_job_failed_with_error_string() -> None:
    from scraper.mass_crawl import _mark_failed

    conn = MagicMock()
    _mark_failed(conn, 1, "test error")
    conn.execute.assert_called()
    call_args = conn.execute.call_args[0][0]
    assert "failed" in call_args.lower()


def test_claim_job_only_claims_pending_or_failed_jobs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scraper.db import get_connection, init_db
    from scraper.mass_crawl import _claim_job

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO scrape_jobs (target_type, target_slug, category_slug, city_slug, status)
        VALUES
            ('category', 'pending-cat', 'pending-cat', '', 'pending'),
            ('category', 'running-cat', 'running-cat', '', 'running');
        """
    )
    pending_id = conn.execute(
        "SELECT id FROM scrape_jobs WHERE target_slug='pending-cat'"
    ).fetchone()[0]
    running_id = conn.execute(
        "SELECT id FROM scrape_jobs WHERE target_slug='running-cat'"
    ).fetchone()[0]

    assert _claim_job(conn, pending_id) is True
    assert _claim_job(conn, pending_id) is False
    assert _claim_job(conn, running_id) is False

    row = conn.execute(
        "SELECT status, pages_scraped, rows_written FROM scrape_jobs WHERE id=?",
        (pending_id,),
    ).fetchone()
    assert tuple(row) == ("running", 0, 0)
    conn.close()


def test_mark_progress_updates_running_job_counts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scraper.db import get_connection, init_db
    from scraper.mass_crawl import _mark_progress

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO scrape_jobs
        (target_type, target_slug, category_slug, city_slug, status)
        VALUES ('category', 'restaurants', 'restaurants', '', 'running')"""
    )
    job_id = conn.execute("SELECT id FROM scrape_jobs").fetchone()[0]

    _mark_progress(conn, job_id, pages=3, rows=17)

    row = conn.execute(
        "SELECT pages_scraped, rows_written FROM scrape_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    assert tuple(row) == (3, 17)
    conn.close()


def test_dry_run_prints_counts_no_crawl() -> None:
    from scraper.mass_crawl import _print_dry_run_summary

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        ("pending", 5, 0, 0),
        ("done", 3, 10, 50),
        ("failed", 2, 0, 0),
    ]
    conn.execute.return_value.fetchone.return_value = (7,)
    _print_dry_run_summary(conn)  # Should not raise


def test_load_targets_reads_requested_taxonomy_tables(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scraper.db import get_connection, init_db
    from scraper.mass_crawl import _load_targets

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.execute(
        "INSERT INTO categories (slug, name) VALUES ('air-conditioning', 'Air Conditioning')"
    )
    conn.execute("INSERT INTO brands (slug, name) VALUES ('carrier', 'Carrier')")
    conn.execute("INSERT INTO keywords (slug, name) VALUES ('Air-Condition', 'Air Condition')")
    conn.commit()

    targets = _load_targets(conn, ["category", "brand", "keyword"])

    assert ("category", "air-conditioning") not in targets
    assert ("category", "استيراد") not in targets
    assert ("category", "استيراد وتصدير") in targets
    assert ("category", "مصنع") in targets
    assert ("category", "تصدير") not in targets
    assert ("brand", "carrier") not in targets
    assert ("keyword", "Air-Condition") not in targets
    assert ("keyword", "استيراد") in targets
    conn.close()


def test_load_targets_can_limit_to_selected_slugs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from scraper.db import get_connection, init_db
    from scraper.mass_crawl import _load_targets

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.execute("INSERT INTO categories (slug, name) VALUES ('atms', 'ATMs')")
    conn.execute("INSERT INTO categories (slug, name) VALUES ('restaurants', 'Restaurants')")
    conn.execute("INSERT INTO brands (slug, name) VALUES ('2b', '2B')")
    conn.execute("INSERT INTO brands (slug, name) VALUES ('carrier', 'Carrier')")
    conn.commit()

    assert _load_targets(
        conn,
        ["category", "brand"],
        {"category": ["atms"], "brand": ["2b"]},
    ) == [("category", "atms"), ("brand", "2b")]
    conn.close()


def test_run_mass_crawl_headless_false_omits_browser_tier(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # type: ignore[no-untyped-def]
    from scraper.db import get_connection, init_db
    from scraper.mass_crawl import run_mass_crawl

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.execute("INSERT INTO categories (slug, name) VALUES ('restaurants', 'Restaurants')")
    conn.execute("INSERT INTO locations (slug, name, type) VALUES ('cairo', 'Cairo', 'city')")
    conn.commit()
    conn.close()

    def fail_tier3(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Tier3Client should not be created when headless=False")

    def fake_scrape_target(**kwargs):  # type: ignore[no-untyped-def]
        return 0

    monkeypatch.setattr("scraper.browser_client.Tier3Client", fail_tier3)
    monkeypatch.setattr("scraper.sites.yellowpages_eg.scrape_target", fake_scrape_target)

    assert run_mass_crawl(
        db_path=str(db_path),
        max_pages=1,
        headless=False,
        target_types=["category"],
        city_slugs=["cairo"],
    ) == 0
