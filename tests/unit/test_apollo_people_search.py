from pathlib import Path
from typing import Any

import pytest


def test_people_search_payload_uses_official_limits() -> None:
    from scraper.apollo_people_search import build_people_search_payload

    payload = build_people_search_payload(
        person_titles=["Owner", "Founder"],
        person_locations=["Cairo", "Egypt"],
        q_keywords="restaurants",
        page=501,
        per_page=250,
        include_similar_titles=False,
    )

    assert payload == {
        "person_titles[]": ["Owner", "Founder"],
        "person_locations[]": ["Cairo", "Egypt"],
        "include_similar_titles": False,
        "q_keywords": "restaurants",
        "page": 500,
        "per_page": 100,
    }


def test_people_search_requires_title_and_location() -> None:
    from scraper.apollo_people_search import build_people_search_payload

    with pytest.raises(ValueError, match="person title"):
        build_people_search_payload(person_titles=[], person_locations=["Egypt"])

    with pytest.raises(ValueError, match="person location"):
        build_people_search_payload(person_titles=["Owner"], person_locations=[])


def test_run_people_search_writes_candidates_without_email_or_phone_contacts(
    tmp_path: Path,
) -> None:
    from scraper.acquisition_db import get_connection, init_acquisition_db
    from scraper.apollo_people_search import run_people_search

    db_path = tmp_path / "acquisition.sqlite"

    def fake_transport(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        assert url == "https://api.apollo.io/api/v1/mixed_people/api_search"
        assert headers["x-api-key"] == "test-key"
        assert payload["person_titles[]"] == ["Owner"]
        assert timeout == 30
        return {
            "people": [
                {
                    "id": "person-1",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "name": "Jane Doe",
                    "title": "Owner",
                    "seniority": "owner",
                    "linkedin_url": "https://linkedin.example/in/jane",
                    "email": "should-not-store@example.com",
                    "phone": "+2010000000",
                    "organization": {
                        "id": "org-1",
                        "name": "Nile Foods",
                        "website_url": "https://nile.example",
                        "city": "Cairo",
                        "country": "Egypt",
                    },
                }
            ],
            "pagination": {"total_entries": 1},
        }

    result = run_people_search(
        db_path=db_path,
        api_key="test-key",
        person_titles=["Owner"],
        person_locations=["Cairo"],
        dry_run=False,
        transport=fake_transport,
    )

    conn = get_connection(db_path)
    init_acquisition_db(conn)
    business = conn.execute("SELECT * FROM businesses").fetchone()
    person = conn.execute("SELECT * FROM people").fetchone()
    contacts = conn.execute("SELECT contact_type, contact_value FROM contacts").fetchall()
    run = conn.execute("SELECT * FROM acquisition_runs").fetchone()
    task = conn.execute("SELECT * FROM acquisition_tasks").fetchone()
    conn.close()

    assert result.people_written == 1
    assert result.businesses_written == 1
    assert result.contacts_written == 1
    assert business["business_name"] == "Nile Foods"
    assert business["source_tier"] == "apollo_people_search"
    assert business["source_url"] == "apollo://people/person-1"
    assert business["email"] == ""
    assert business["phone"] == ""
    assert business["website"] == "https://nile.example"
    assert business["confidence"] == 0.65
    assert person["full_name"] == "Jane Doe"
    assert [(row["contact_type"], row["contact_value"]) for row in contacts] == [
        ("website", "https://nile.example")
    ]
    assert run["status"] == "succeeded"
    assert task["status"] == "succeeded"


def test_run_people_search_dry_run_creates_no_candidates(tmp_path: Path) -> None:
    from scraper.acquisition_db import get_connection, init_acquisition_db
    from scraper.apollo_people_search import run_people_search

    db_path = tmp_path / "acquisition.sqlite"

    def blocked_transport(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        raise AssertionError("dry run must not call Apollo")

    result = run_people_search(
        db_path=db_path,
        api_key="",
        person_titles=["Owner"],
        person_locations=["Egypt"],
        dry_run=True,
        transport=blocked_transport,
    )

    conn = get_connection(db_path)
    init_acquisition_db(conn)
    counts = {
        "runs": conn.execute("SELECT COUNT(*) FROM acquisition_runs").fetchone()[0],
        "tasks": conn.execute("SELECT COUNT(*) FROM acquisition_tasks").fetchone()[0],
        "people": conn.execute("SELECT COUNT(*) FROM people").fetchone()[0],
    }
    run = conn.execute("SELECT * FROM acquisition_runs").fetchone()
    task = conn.execute("SELECT * FROM acquisition_tasks").fetchone()
    conn.close()

    assert result.dry_run is True
    assert result.people_seen == 0
    assert counts == {"runs": 1, "tasks": 1, "people": 0}
    assert run["status"] == "draft"
    assert task["status"] == "skipped_policy"


def test_run_people_search_live_requires_api_key(tmp_path: Path) -> None:
    from scraper.apollo_people_search import ApolloPeopleSearchError, run_people_search

    with pytest.raises(ApolloPeopleSearchError, match="APOLLO_API_KEY"):
        run_people_search(
            db_path=tmp_path / "acquisition.sqlite",
            api_key="",
            person_titles=["Owner"],
            person_locations=["Egypt"],
            dry_run=False,
        )
