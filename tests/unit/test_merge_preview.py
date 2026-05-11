from pathlib import Path


def test_load_unified_business_preview_combines_yellowpages_and_acquisition(
    tmp_path: Path,
) -> None:
    from app.merge_preview import load_unified_business_preview
    from scraper.acquisition_db import get_connection as get_acquisition_connection
    from scraper.acquisition_db import init_acquisition_db
    from scraper.db import get_connection as get_scraper_connection
    from scraper.db import init_db

    yp_path = tmp_path / "scraper.sqlite"
    yp_conn = get_scraper_connection(yp_path)
    init_db(yp_conn)
    yp_conn.execute(
        """INSERT INTO businesses
        (
            source_url, business_name, category_slug, city_slug, phone, email,
            website, facebook_url, address, raw_html_hash, source_tier, scraped_at
        )
        VALUES (
            'https://yp.example/acme', 'YP Acme', 'restaurants', 'cairo',
            '+20100', 'info@yp.example', 'https://yp.example', '',
            'Cairo', 'hash-1', 1, '2026-05-10'
        )"""
    )
    yp_conn.commit()
    yp_conn.close()

    acquisition_path = tmp_path / "acquisition.sqlite"
    acq_conn = get_acquisition_connection(acquisition_path)
    init_acquisition_db(acq_conn)
    acq_conn.execute(
        """INSERT INTO businesses
        (
            source_url, business_name, category_slug, city_slug, phone, email,
            website, facebook_url, address, raw_html_hash, source_tier, scraped_at,
            city, source_name, source_record_id, confidence, acquired_at
        )
        VALUES (
            'https://apollo.example/person', 'Apollo Acme', '', 'Cairo',
            '+20200', 'owner@apollo.example', 'https://apollo.example', '',
            'Cairo', 'record-1', 'csv_import', '2026-05-11',
            'Cairo', 'csv_import', 'record-1', 0.82, '2026-05-11'
        )"""
    )
    acq_conn.commit()
    acq_conn.close()

    rows = load_unified_business_preview(yp_path, acquisition_path)

    assert [row["origin"] for row in rows] == ["acquisition", "yellowpages"]
    assert rows[0]["business_name"] == "Apollo Acme"
    assert rows[0]["confidence"] == 0.82
    assert rows[1]["business_name"] == "YP Acme"
    assert rows[1]["confidence"] == "yellowpages"


def test_load_unified_business_preview_uses_common_keys(tmp_path: Path) -> None:
    from app.merge_preview import MERGE_BUSINESS_KEYS, load_unified_business_preview
    from scraper.acquisition_db import get_connection, init_acquisition_db

    acquisition_path = tmp_path / "acquisition.sqlite"
    conn = get_connection(acquisition_path)
    init_acquisition_db(conn)
    conn.execute(
        """INSERT INTO businesses
        (
            source_url, business_name, source_name, source_record_id,
            confidence, acquired_at
        )
        VALUES ('https://example.com', 'Only Acq', 'csv_import', 'r1', 0.5, '2026')"""
    )
    conn.commit()
    conn.close()

    rows = load_unified_business_preview(tmp_path / "missing.sqlite", acquisition_path)

    assert set(MERGE_BUSINESS_KEYS).issubset(rows[0])


def test_yellowpages_preview_does_not_migrate_live_database(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    import app.merge_preview as merge_preview
    from scraper.db import get_connection, init_db

    yp_path = tmp_path / "scraper.sqlite"
    conn = get_connection(yp_path)
    init_db(conn)
    conn.execute("INSERT INTO businesses (source_url, business_name) VALUES ('x', 'Y')")
    conn.commit()
    conn.close()

    def fail_init_db(_conn):  # type: ignore[no-untyped-def]
        raise AssertionError("merge preview must not run scraper DB migrations")

    monkeypatch.setattr(merge_preview, "init_db", fail_init_db, raising=False)

    rows = merge_preview.load_unified_business_preview(
        yp_path,
        tmp_path / "acquisition.sqlite",
    )

    assert rows[-1]["origin"] == "yellowpages"
