from pathlib import Path


def test_import_csv_creates_normalized_business_people_contacts(tmp_path: Path) -> None:
    from scraper.acquisition_csv import import_csv
    from scraper.acquisition_db import get_connection, init_acquisition_db

    csv_path = tmp_path / "apollo_export.csv"
    csv_path.write_text(
        "\n".join(
            [
                "First Name,Last Name,Title,Company,Website,Email,Phone,LinkedIn URL,City,Country",
                "Jane,Doe,Owner,Acme Co,https://acme.example,jane@acme.example,+20100,https://linkedin.example/jane,Cairo,Egypt",
                "Jane,Doe,Owner,Acme Co,https://acme.example,jane@acme.example,+20100,https://linkedin.example/jane,Cairo,Egypt",
            ]
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "acquisition.sqlite"

    result = import_csv(
        csv_path,
        db_path=db_path,
        source_name="csv_import",
        provenance_note="user supplied test export",
    )

    conn = get_connection(db_path)
    init_acquisition_db(conn)
    counts = {
        "businesses": conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0],
        "people": conn.execute("SELECT COUNT(*) FROM people").fetchone()[0],
        "contacts": conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
        "raw_records": conn.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0],
    }
    business = conn.execute("SELECT * FROM businesses").fetchone()
    person = conn.execute("SELECT * FROM people").fetchone()
    contacts = conn.execute(
        "SELECT contact_type, contact_value FROM contacts ORDER BY contact_type"
    ).fetchall()
    conn.close()

    assert result.rows_seen == 2
    assert result.businesses_written == 1
    assert result.people_written == 1
    assert result.contacts_written == 3
    assert counts == {"businesses": 1, "people": 1, "contacts": 3, "raw_records": 1}
    assert business["business_name"] == "Acme Co"
    assert business["domain"] == "acme.example"
    assert business["category_slug"] == ""
    assert business["city_slug"] == "Cairo"
    assert business["facebook_url"] == ""
    assert business["raw_html_hash"] == business["source_record_id"]
    assert business["source_tier"] == "csv_import"
    assert business["scraped_at"] == business["acquired_at"]
    assert business["confidence"] == 0.8
    assert person["full_name"] == "Jane Doe"
    assert [(row["contact_type"], row["contact_value"]) for row in contacts] == [
        ("email", "jane@acme.example"),
        ("phone", "+20100"),
        ("website", "https://acme.example"),
    ]


def test_import_csv_requires_allowed_source(tmp_path: Path) -> None:
    import pytest

    from scraper.acquisition_csv import import_csv
    from scraper.acquisition_db import get_connection, init_acquisition_db
    from scraper.acquisition_policy import PolicyBlockedError

    csv_path = tmp_path / "leads.csv"
    csv_path.write_text("Company,Email\nAcme,jane@acme.example\n", encoding="utf-8")
    db_path = tmp_path / "acquisition.sqlite"
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    conn.execute("UPDATE sources SET enabled=0 WHERE source_name='csv_import'")
    conn.commit()
    conn.close()

    with pytest.raises(PolicyBlockedError, match="disabled"):
        import_csv(csv_path, db_path=db_path, source_name="csv_import")
