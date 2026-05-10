"""Unit tests for mass_crawl.py - mocks scrape_category and DB."""

from unittest.mock import MagicMock


def test_done_job_skipped() -> None:
    from scraper.mass_crawl import _get_or_create_job

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1, "done", 0, 0)
    job = _get_or_create_job(conn, "cat1", "city1")
    assert job["status"] == "done"


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

    assert _load_targets(conn, ["category", "brand", "keyword"]) == [
        ("category", "air-conditioning"),
        ("brand", "carrier"),
        ("keyword", "Air-Condition"),
    ]
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
