from pathlib import Path


def test_load_acquisition_overview_reads_separate_database(tmp_path: Path) -> None:
    from app.acquisition_data_access import load_acquisition_overview
    from scraper.acquisition_db import get_connection, init_acquisition_db

    db_path = tmp_path / "acquisition.sqlite"
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    conn.execute(
        """INSERT INTO businesses
        (business_name, website, source_name, source_record_id, source_url, acquired_at)
        VALUES (
            'Acme', 'https://acme.example', 'csv_import', 'biz-1',
            'local://biz-1', '2026-05-11'
        )"""
    )
    conn.execute(
        """INSERT INTO people
        (full_name, title, business_id, source_name, source_record_id, acquired_at)
        VALUES ('Jane Doe', 'Owner', 1, 'apollo_people_search', 'person-1', '2026-05-11')"""
    )
    conn.execute(
        """INSERT INTO contacts
        (
            contact_type, contact_value, business_id, person_id, source_name,
            verification_status, confidence, acquired_at
        )
        VALUES (
            'email', 'jane@acme.example', 1, 1, 'csv_import',
            'unverified', 0.75, '2026-05-11'
        )"""
    )
    conn.commit()
    conn.close()

    overview = load_acquisition_overview(db_path)

    assert overview["business_count"] == 1
    assert overview["people_count"] == 1
    assert overview["contact_count"] == 1
    assert overview["enabled_sources"] >= 1


def test_load_sources_returns_policy_fields(tmp_path: Path) -> None:
    from app.acquisition_data_access import load_sources
    from scraper.acquisition_db import get_connection, init_acquisition_db

    db_path = tmp_path / "acquisition.sqlite"
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    conn.close()

    sources = {row["source_name"]: row for row in load_sources(db_path)}

    assert sources["apollo_people_search"]["can_collect_people"] == 1
    assert sources["apollo_people_search"]["can_collect_contacts"] == 0
    assert sources["reoon"]["source_type"] == "email_verifier"
