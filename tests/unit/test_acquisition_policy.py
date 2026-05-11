from pathlib import Path

import pytest


def _init_test_db(tmp_path: Path) -> Path:
    from scraper.acquisition_db import get_connection, init_acquisition_db

    db_path = tmp_path / "acquisition.sqlite"
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    conn.close()
    return db_path


def test_init_acquisition_db_seeds_default_sources_in_separate_database(tmp_path: Path) -> None:
    from scraper.acquisition_db import get_connection

    db_path = _init_test_db(tmp_path)
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT source_name, source_type, can_collect_people, can_collect_contacts, "
        "can_enrich, is_paid, enabled "
        "FROM sources ORDER BY source_name"
    ).fetchall()
    conn.close()

    sources = {row["source_name"]: dict(row) for row in rows}
    assert {"yellowpages", "csv_import", "apollo_people_search", "reoon"} <= set(sources)
    assert sources["apollo_people_search"]["can_collect_people"] == 1
    assert sources["apollo_people_search"]["can_collect_contacts"] == 0
    assert sources["reoon"]["can_collect_contacts"] == 0
    assert sources["reoon"]["can_enrich"] == 1


def test_disabled_source_cannot_run(tmp_path: Path) -> None:
    from scraper.acquisition_db import get_connection
    from scraper.acquisition_policy import PolicyBlockedError, require_source_allowed

    db_path = _init_test_db(tmp_path)
    conn = get_connection(db_path)
    conn.execute("UPDATE sources SET enabled=0 WHERE source_name='apollo_people_search'")
    conn.commit()
    conn.close()

    with pytest.raises(PolicyBlockedError, match="disabled"):
        require_source_allowed(db_path, "apollo_people_search")


def test_unknown_terms_block_execution(tmp_path: Path) -> None:
    from scraper.acquisition_db import get_connection
    from scraper.acquisition_policy import PolicyBlockedError, require_source_allowed

    db_path = _init_test_db(tmp_path)
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE sources SET allowed_use_note='', terms_url='' WHERE source_name='csv_import'"
    )
    conn.commit()
    conn.close()

    with pytest.raises(PolicyBlockedError, match="terms"):
        require_source_allowed(db_path, "csv_import")


def test_paid_source_requires_explicit_budget(tmp_path: Path) -> None:
    from scraper.acquisition_policy import PolicyBlockedError, require_source_allowed

    db_path = _init_test_db(tmp_path)

    with pytest.raises(PolicyBlockedError, match="budget"):
        require_source_allowed(db_path, "apollo_enrichment")

    source = require_source_allowed(db_path, "apollo_enrichment", credit_budget=5)
    assert source.source_name == "apollo_enrichment"
    assert source.is_paid is True


def test_scraper_db_does_not_create_acquisition_sources_table(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db

    conn = get_connection(tmp_path / "scraper.sqlite")
    init_db(conn)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sources'"
    ).fetchone()
    conn.close()

    assert row is None


def test_acquisition_businesses_include_yellowpages_merge_keys_plus_confidence(
    tmp_path: Path,
) -> None:
    from scraper.acquisition_db import get_connection as get_acquisition_connection
    from scraper.acquisition_db import init_acquisition_db
    from scraper.db import get_connection as get_scraper_connection
    from scraper.db import init_db

    scraper_conn = get_scraper_connection(tmp_path / "scraper.sqlite")
    init_db(scraper_conn)
    acquisition_conn = get_acquisition_connection(tmp_path / "acquisition.sqlite")
    init_acquisition_db(acquisition_conn)

    scraper_columns = {
        row[1] for row in scraper_conn.execute("PRAGMA table_info(businesses)").fetchall()
    }
    acquisition_columns = {
        row[1] for row in acquisition_conn.execute("PRAGMA table_info(businesses)").fetchall()
    }
    scraper_conn.close()
    acquisition_conn.close()

    assert (scraper_columns | {"confidence"}).issubset(acquisition_columns)


def test_acquisition_db_backfills_merge_keys_for_existing_rows(tmp_path: Path) -> None:
    from scraper.acquisition_db import get_connection, init_acquisition_db

    conn = get_connection(tmp_path / "acquisition.sqlite")
    init_acquisition_db(conn)
    conn.execute(
        """INSERT INTO businesses
        (
            business_name, website, city, source_name, source_record_id,
            source_url, confidence, acquired_at
        )
        VALUES (
            'Acme', 'https://acme.example', 'Cairo', 'csv_import',
            'record-1', 'https://acme.example', 0.8, '2026-05-11'
        )"""
    )
    conn.commit()

    init_acquisition_db(conn)

    row = conn.execute(
        """SELECT city_slug, raw_html_hash, source_tier, scraped_at
        FROM businesses WHERE source_record_id='record-1'"""
    ).fetchone()
    conn.close()

    assert dict(row) == {
        "city_slug": "Cairo",
        "raw_html_hash": "record-1",
        "source_tier": "csv_import",
        "scraped_at": "2026-05-11",
    }
