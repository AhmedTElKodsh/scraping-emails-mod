"""Official Apollo People API Search acquisition adapter."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scraper.acquisition_db import get_connection, init_acquisition_db
from scraper.acquisition_policy import require_source_allowed

SOURCE_NAME = "apollo_people_search"
DEFAULT_BASE_URL = "https://api.apollo.io/api/v1"
PEOPLE_SEARCH_PATH = "/mixed_people/api_search"
DEFAULT_CONFIDENCE = 0.65

ApolloTransport = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


class ApolloPeopleSearchError(RuntimeError):
    """Raised when Apollo People Search cannot be executed safely."""


@dataclass(frozen=True)
class ApolloPeopleSearchResult:
    dry_run: bool
    run_id: int
    people_seen: int
    raw_records_written: int
    businesses_written: int
    people_written: int
    contacts_written: int


def _clean_list(values: Sequence[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def build_people_search_payload(
    *,
    person_titles: Sequence[str],
    person_locations: Sequence[str],
    q_keywords: str = "",
    person_seniorities: Sequence[str] = (),
    include_similar_titles: bool = True,
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    """Build the documented Apollo People Search query payload."""
    titles = _clean_list(person_titles)
    locations = _clean_list(person_locations)
    seniorities = _clean_list(person_seniorities)
    if not titles:
        raise ValueError("At least one person title is required for Apollo People Search.")
    if not locations:
        raise ValueError("At least one person location is required for Apollo People Search.")

    payload: dict[str, Any] = {
        "person_titles[]": titles,
        "person_locations[]": locations,
        "include_similar_titles": include_similar_titles,
        "page": min(max(page, 1), 500),
        "per_page": min(max(per_page, 1), 100),
    }
    if q_keywords.strip():
        payload["q_keywords"] = q_keywords.strip()
    if seniorities:
        payload["person_seniorities[]"] = seniorities
    return payload


def _default_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    import requests

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.status_code >= 400:
        raise ApolloPeopleSearchError(f"Apollo People Search failed: HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise ApolloPeopleSearchError("Apollo People Search returned a non-object response.")
    return data


def _domain(value: str) -> str:
    if not value:
        return ""
    candidate = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate)
    return (parsed.netloc or parsed.path).removeprefix("www.").strip("/").lower()


def _organization(person: dict[str, Any]) -> dict[str, Any]:
    org = person.get("organization") or person.get("company") or {}
    return org if isinstance(org, dict) else {}


def _str_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _person_record_id(person: dict[str, Any]) -> str:
    value = _str_value(person, "id", "person_id")
    if value:
        return value
    return str(abs(hash(json.dumps(person, sort_keys=True, ensure_ascii=False))))


def _insert_run(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    dry_run: bool,
    record_budget: int,
    status: str,
    now: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO acquisition_runs
        (source_name, query_json, status, dry_run, record_budget, credit_budget, started_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)""",
        (
            SOURCE_NAME,
            json.dumps(payload, sort_keys=True),
            status,
            int(dry_run),
            record_budget,
            now,
        ),
    )
    if cursor.lastrowid is None:
        raise ApolloPeopleSearchError("Could not create Apollo acquisition run.")
    return cursor.lastrowid


def _insert_task(
    conn: sqlite3.Connection,
    run_id: int,
    page: int,
    status: str,
    error: str = "",
) -> int:
    cursor = conn.execute(
        """INSERT INTO acquisition_tasks
        (run_id, task_type, page, status, estimated_credits, actual_credits, error)
        VALUES (?, 'people_search', ?, ?, 0, 0, ?)""",
        (run_id, page, status, error),
    )
    if cursor.lastrowid is None:
        raise ApolloPeopleSearchError("Could not create Apollo acquisition task.")
    return cursor.lastrowid


def _finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    now: str,
    error: str = "",
) -> None:
    conn.execute(
        "UPDATE acquisition_runs SET status=?, finished_at=?, error=? WHERE id=?",
        (status, now, error, run_id),
    )


def _insert_raw_record(
    conn: sqlite3.Connection,
    person: dict[str, Any],
    record_id: str,
    now: str,
) -> int:
    cursor = conn.execute(
        """INSERT OR IGNORE INTO raw_records
        (source_name, source_record_id, payload_json, acquired_at, provenance_note)
        VALUES (?, ?, ?, ?, ?)""",
        (
            SOURCE_NAME,
            record_id,
            json.dumps(person, ensure_ascii=False, sort_keys=True),
            now,
            "Official Apollo People API Search candidate discovery; no email/phone stored.",
        ),
    )
    return int(cursor.rowcount)


def _insert_business(
    conn: sqlite3.Connection,
    person: dict[str, Any],
    record_id: str,
    now: str,
) -> int:
    org = _organization(person)
    company = _str_value(org, "name", "company_name", "organization_name")
    website = _str_value(org, "website_url", "website", "domain")
    city = _str_value(org, "city") or _str_value(person, "city")
    country = _str_value(org, "country") or _str_value(person, "country")
    cursor = conn.execute(
        """INSERT OR IGNORE INTO businesses
        (
            source_url, business_name, category_slug, city_slug, phone, email,
            normalized_business_name, website, facebook_url, domain, address,
            raw_html_hash, source_tier, scraped_at, city, country, source_name,
            source_record_id, confidence, acquired_at
        )
        VALUES (?, ?, '', ?, '', '', ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _str_value(person, "profile_url") or f"apollo://people/{record_id}",
            company,
            city,
            company.lower(),
            website,
            _domain(website),
            _str_value(org, "street_address", "address"),
            record_id,
            SOURCE_NAME,
            now,
            city,
            country,
            SOURCE_NAME,
            record_id,
            DEFAULT_CONFIDENCE,
            now,
        ),
    )
    return int(cursor.rowcount)


def _business_id(conn: sqlite3.Connection, record_id: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM businesses WHERE source_name=? AND source_record_id=?",
        (SOURCE_NAME, record_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_person(
    conn: sqlite3.Connection,
    person: dict[str, Any],
    record_id: str,
    business_id: int | None,
    now: str,
) -> int:
    full_name = _str_value(person, "name", "full_name")
    first_name = _str_value(person, "first_name")
    last_name = _str_value(person, "last_name")
    if not full_name:
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    if not full_name:
        return 0
    cursor = conn.execute(
        """INSERT OR IGNORE INTO people
        (
            full_name, first_name, last_name, title, seniority, linkedin_url, business_id,
            source_name, source_record_id, confidence, acquired_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            full_name,
            first_name,
            last_name,
            _str_value(person, "title", "job_title", "headline"),
            _str_value(person, "seniority"),
            _str_value(person, "linkedin_url", "linkedin"),
            business_id,
            SOURCE_NAME,
            record_id,
            DEFAULT_CONFIDENCE,
            now,
        ),
    )
    return int(cursor.rowcount)


def _person_id(conn: sqlite3.Connection, record_id: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM people WHERE source_name=? AND source_record_id=?",
        (SOURCE_NAME, record_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_website_contact(
    conn: sqlite3.Connection,
    person: dict[str, Any],
    business_id: int | None,
    person_id: int | None,
    now: str,
) -> int:
    website = _str_value(_organization(person), "website_url", "website")
    if not website:
        return 0
    cursor = conn.execute(
        """INSERT OR IGNORE INTO contacts
        (
            contact_type, contact_value, business_id, person_id, source_name,
            verification_status, confidence, acquired_at
        )
        VALUES ('website', ?, ?, ?, ?, 'unverified', ?, ?)""",
        (website, business_id, person_id, SOURCE_NAME, DEFAULT_CONFIDENCE, now),
    )
    return int(cursor.rowcount)


def _people_from_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_people = data.get("people") or []
    if not isinstance(raw_people, list):
        raise ApolloPeopleSearchError("Apollo People Search response missing people list.")
    return [person for person in raw_people if isinstance(person, dict)]


def run_people_search(
    *,
    db_path: str | Path,
    api_key: str,
    person_titles: Sequence[str],
    person_locations: Sequence[str],
    q_keywords: str = "",
    person_seniorities: Sequence[str] = (),
    include_similar_titles: bool = True,
    page: int = 1,
    per_page: int = 25,
    dry_run: bool = True,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 30,
    transport: ApolloTransport | None = None,
) -> ApolloPeopleSearchResult:
    require_source_allowed(db_path, SOURCE_NAME)
    payload = build_people_search_payload(
        person_titles=person_titles,
        person_locations=person_locations,
        q_keywords=q_keywords,
        person_seniorities=person_seniorities,
        include_similar_titles=include_similar_titles,
        page=page,
        per_page=per_page,
    )
    now = datetime.now(UTC).isoformat()
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    run_id = _insert_run(conn, payload, dry_run, int(payload["per_page"]), "draft", now)

    if dry_run:
        _insert_task(conn, run_id, int(payload["page"]), "skipped_policy", "dry run")
        conn.commit()
        conn.close()
        return ApolloPeopleSearchResult(
            dry_run=True,
            run_id=run_id,
            people_seen=0,
            raw_records_written=0,
            businesses_written=0,
            people_written=0,
            contacts_written=0,
        )

    if not api_key.strip():
        conn.rollback()
        conn.close()
        raise ApolloPeopleSearchError("Set APOLLO_API_KEY or pass --api-key for live search.")

    transport = transport or _default_transport
    task_id = _insert_task(conn, run_id, int(payload["page"]), "leased")
    conn.execute("UPDATE acquisition_runs SET status='running' WHERE id=?", (run_id,))
    conn.commit()
    raw_written = 0
    businesses_written = 0
    people_written = 0
    contacts_written = 0
    try:
        response = transport(
            f"{base_url.rstrip('/')}{PEOPLE_SEARCH_PATH}",
            {"x-api-key": api_key.strip(), "Content-Type": "application/json"},
            payload,
            timeout,
        )
        people = _people_from_response(response)
        for person in people:
            record_id = _person_record_id(person)
            raw_written += _insert_raw_record(conn, person, record_id, now)
            businesses_written += _insert_business(conn, person, record_id, now)
            business_id = _business_id(conn, record_id)
            people_written += _insert_person(conn, person, record_id, business_id, now)
            person_id = _person_id(conn, record_id)
            contacts_written += _insert_website_contact(conn, person, business_id, person_id, now)
        conn.execute(
            "UPDATE acquisition_tasks SET status='succeeded', attempts=1 WHERE id=?",
            (task_id,),
        )
        _finish_run(conn, run_id, "succeeded", datetime.now(UTC).isoformat())
        conn.commit()
    except Exception as exc:
        conn.rollback()
        conn = get_connection(db_path)
        conn.execute(
            "UPDATE acquisition_tasks SET status='failed', error=? WHERE id=?",
            (str(exc), task_id),
        )
        _finish_run(conn, run_id, "failed", datetime.now(UTC).isoformat(), str(exc))
        conn.commit()
        raise
    finally:
        conn.close()

    return ApolloPeopleSearchResult(
        dry_run=False,
        run_id=run_id,
        people_seen=len(people),
        raw_records_written=raw_written,
        businesses_written=businesses_written,
        people_written=people_written,
        contacts_written=contacts_written,
    )
