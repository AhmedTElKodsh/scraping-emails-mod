"""Unit tests for db.py - SQLite connection and schema."""

import sqlite3
from pathlib import Path

import pytest


def test_init_creates_all_tables(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = {row[0] for row in rows}
    assert "categories" in tables
    assert "locations" in tables
    assert "brands" in tables
    assert "keywords" in tables
    assert "businesses" in tables
    assert "business_facets" in tables
    assert "scrape_jobs" in tables
    conn.close()


def test_init_adds_new_taxonomy_and_facet_columns(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)

    location_cols = {row[1] for row in conn.execute("PRAGMA table_info(locations)").fetchall()}
    job_cols = {row[1] for row in conn.execute("PRAGMA table_info(scrape_jobs)").fetchall()}

    assert {"external_id", "result_count", "parent_slug"}.issubset(location_cols)
    assert {"target_type", "target_slug", "city_slug", "status"}.issubset(job_cols)
    conn.close()


def test_business_facets_are_unique_per_business_type_and_slug(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.execute(
        "INSERT INTO business_facets (source_url, facet_type, slug, name) VALUES (?, ?, ?, ?)",
        ("https://example.com/1", "category", "air-conditioning", "Air Conditioning"),
    )
    conn.execute(
        """INSERT OR IGNORE INTO business_facets
        (source_url, facet_type, slug, name)
        VALUES (?, ?, ?, ?)""",
        ("https://example.com/1", "category", "air-conditioning", "Air Conditioning"),
    )
    count = conn.execute("SELECT COUNT(*) FROM business_facets").fetchone()[0]
    assert count == 1
    conn.close()


def test_init_is_idempotent(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    init_db(conn)  # second call should not raise
    conn.close()


def test_init_migrates_legacy_scrape_jobs_before_indexing(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    conn.executescript(
        """
        CREATE TABLE scrape_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_slug TEXT NOT NULL,
            city_slug TEXT DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed')),
            pages_scraped INTEGER DEFAULT 0,
            rows_written INTEGER DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            error TEXT DEFAULT '',
            UNIQUE(category_slug, city_slug)
        );

        INSERT INTO scrape_jobs (category_slug, city_slug, status)
        VALUES ('air-conditioning', 'cairo', 'done');
        """
    )

    init_db(conn)

    row = conn.execute(
        """SELECT target_type, target_slug, category_slug, city_slug, status
        FROM scrape_jobs"""
    ).fetchone()
    assert dict(row) == {
        "target_type": "category",
        "target_slug": "air-conditioning",
        "category_slug": "air-conditioning",
        "city_slug": "cairo",
        "status": "done",
    }
    indexes = {
        row[1] for row in conn.execute("PRAGMA index_list(scrape_jobs)").fetchall()
    }
    assert "idx_scrape_jobs_target_city" in indexes
    conn.close()


def test_init_backfills_facets_for_single_legacy_productive_job(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO businesses (source_url, business_name)
        VALUES
            ('https://example.com/1', 'One'),
            ('https://example.com/2', 'Two');

        INSERT INTO scrape_jobs
            (target_type, target_slug, category_slug, city_slug, status, rows_written)
        VALUES
            ('category', 'restaurants', 'restaurants', 'cairo', 'done', 2);
        """
    )

    init_db(conn)

    facets = conn.execute(
        """SELECT facet_type, slug, COUNT(*) AS count
        FROM business_facets
        GROUP BY facet_type, slug
        ORDER BY facet_type, slug"""
    ).fetchall()
    assert [tuple(row) for row in facets] == [
        ("category", "restaurants", 2),
        ("city", "cairo", 2),
    ]
    rows = conn.execute(
        "SELECT category_slug, city_slug FROM businesses ORDER BY source_url"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("restaurants", "cairo"),
        ("restaurants", "cairo"),
    ]
    conn.close()


def test_init_does_not_guess_facets_for_multiple_legacy_productive_jobs(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO businesses (source_url, business_name)
        VALUES
            ('https://example.com/1', 'One'),
            ('https://example.com/2', 'Two');

        INSERT INTO scrape_jobs
            (target_type, target_slug, category_slug, city_slug, status, rows_written)
        VALUES
            ('category', 'restaurants', 'restaurants', 'cairo', 'done', 1),
            ('category', 'hospitals', 'hospitals', 'cairo', 'done', 1);
        """
    )

    init_db(conn)

    count = conn.execute("SELECT COUNT(*) FROM business_facets").fetchone()[0]
    assert count == 0
    conn.close()


def test_init_rebuilds_location_facets_from_business_addresses(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO locations (slug, name, type, parent_slug)
        VALUES
            ('alexandria', 'Alexandria', 'city', ''),
            ('cairo', 'Cairo', 'city', ''),
            ('giza', 'Giza', 'city', ''),
            ('maadi', 'Maadi', 'area', 'cairo'),
            ('new-maadi', 'New Maadi', 'district', 'maadi');

        INSERT INTO businesses (source_url, business_name, city_slug, address)
        VALUES
            ('https://example.com/1', 'Maadi Biz', 'cairo', '12 Rd. 9, Maadi, Cairo'),
            ('https://example.com/2', 'Giza Biz', 'cairo', '45 El Matbaa St., Faisal, Giza'),
            ('https://example.com/3', 'New Maadi Biz', 'cairo',
             '8 El Gazaer St., New Maadi, Maadi, Cairo'),
            ('https://example.com/4', 'Cairo Building Biz', 'cairo',
             '3 Alexandria Bldgs., El Salam City, Cairo');

        INSERT INTO business_facets (source_url, facet_type, slug, name)
        VALUES
            ('https://example.com/1', 'city', 'cairo', 'cairo'),
            ('https://example.com/2', 'city', 'cairo', 'cairo'),
            ('https://example.com/3', 'city', 'cairo', 'cairo'),
            ('https://example.com/4', 'city', 'cairo', 'cairo');
        """
    )

    init_db(conn)

    facets = conn.execute(
        """SELECT source_url, facet_type, slug
        FROM business_facets
        ORDER BY source_url, facet_type, slug"""
    ).fetchall()
    assert [tuple(row) for row in facets] == [
        ("https://example.com/1", "area", "maadi"),
        ("https://example.com/1", "city", "cairo"),
        ("https://example.com/2", "city", "giza"),
        ("https://example.com/3", "area", "maadi"),
        ("https://example.com/3", "city", "cairo"),
        ("https://example.com/3", "district", "new-maadi"),
        ("https://example.com/4", "city", "cairo"),
    ]
    city_slugs = conn.execute(
        "SELECT source_url, city_slug FROM businesses ORDER BY source_url"
    ).fetchall()
    assert [tuple(row) for row in city_slugs] == [
        ("https://example.com/1", "cairo"),
        ("https://example.com/2", "giza"),
        ("https://example.com/3", "cairo"),
        ("https://example.com/4", "cairo"),
    ]
    conn.close()


def test_scrape_job_unique_constraint(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO scrape_jobs
        (target_type, target_slug, category_slug, city_slug, status)
        VALUES ('category', 'cat1', 'cat1', 'city1', 'pending')"""
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO scrape_jobs
            (target_type, target_slug, category_slug, city_slug, status)
            VALUES ('category', 'cat1', 'cat1', 'city1', 'pending')"""
        )
    conn.close()


def test_business_unique_on_source_url(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    conn.execute("INSERT INTO businesses (source_url) VALUES ('http://example.com/1')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO businesses (source_url) VALUES ('http://example.com/1')")
    conn.close()


def test_wal_mode_enabled(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "test.sqlite")
    init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.upper() == "WAL"
    conn.close()
