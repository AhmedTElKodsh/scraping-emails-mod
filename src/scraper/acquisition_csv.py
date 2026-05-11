"""CSV import for the separate compliant acquisition database."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from scraper.acquisition_db import get_connection, init_acquisition_db
from scraper.acquisition_policy import require_source_allowed


@dataclass(frozen=True)
class CsvImportResult:
    rows_seen: int
    raw_records_written: int
    businesses_written: int
    people_written: int
    contacts_written: int


FIELD_ALIASES = {
    "first_name": ("first name", "firstname", "first_name"),
    "last_name": ("last name", "lastname", "last_name"),
    "full_name": ("name", "full name", "full_name", "person name"),
    "title": ("title", "job title", "position"),
    "company": ("company", "company name", "organization", "business name"),
    "website": ("website", "company website", "domain", "company domain"),
    "email": ("email", "email address", "work email"),
    "phone": ("phone", "phone number", "mobile", "telephone"),
    "linkedin_url": ("linkedin url", "linkedin", "person linkedin url"),
    "city": ("city", "location city"),
    "country": ("country", "location country"),
    "source_url": ("source url", "profile url", "apollo url"),
}


def _norm_key(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _value(row: dict[str, str], field: str) -> str:
    normalized = {_norm_key(key): value.strip() for key, value in row.items() if value is not None}
    for alias in FIELD_ALIASES[field]:
        if alias in normalized and normalized[alias]:
            return normalized[alias]
    return ""


def _domain(value: str) -> str:
    if not value:
        return ""
    candidate = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate)
    domain = parsed.netloc or parsed.path
    return domain.removeprefix("www.").strip("/").lower()


def _source_record_id(row: dict[str, str]) -> str:
    stable = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _full_name(first_name: str, last_name: str, full_name: str) -> str:
    return full_name or " ".join(part for part in [first_name, last_name] if part).strip()


def _insert_raw_record(
    conn: sqlite3.Connection,
    source_name: str,
    source_record_id: str,
    row: dict[str, str],
    acquired_at: str,
    provenance_note: str,
) -> int:
    cursor = conn.execute(
        """INSERT OR IGNORE INTO raw_records
        (source_name, source_record_id, payload_json, acquired_at, provenance_note)
        VALUES (?, ?, ?, ?, ?)""",
        (
            source_name,
            source_record_id,
            json.dumps(row, ensure_ascii=False, sort_keys=True),
            acquired_at,
            provenance_note,
        ),
    )
    return int(cursor.rowcount)


def _insert_business(
    conn: sqlite3.Connection,
    row: dict[str, str],
    source_name: str,
    record_id: str,
    now: str,
) -> int:
    company = _value(row, "company")
    website = _value(row, "website")
    email = _value(row, "email")
    phone = _value(row, "phone")
    cursor = conn.execute(
        """INSERT OR IGNORE INTO businesses
        (
            business_name, normalized_business_name, website, domain, phone, email,
            city, country, source_name, source_record_id, source_url, confidence, acquired_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            company,
            company.lower(),
            website,
            _domain(website),
            phone,
            email,
            _value(row, "city"),
            _value(row, "country"),
            source_name,
            record_id,
            _value(row, "source_url") or website,
            0.8,
            now,
        ),
    )
    return int(cursor.rowcount)


def _business_id(conn: sqlite3.Connection, source_name: str, record_id: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM businesses WHERE source_name=? AND source_record_id=?",
        (source_name, record_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_person(
    conn: sqlite3.Connection,
    row: dict[str, str],
    source_name: str,
    record_id: str,
    business_id: int | None,
    now: str,
) -> int:
    first_name = _value(row, "first_name")
    last_name = _value(row, "last_name")
    full_name = _full_name(first_name, last_name, _value(row, "full_name"))
    if not full_name:
        return 0
    cursor = conn.execute(
        """INSERT OR IGNORE INTO people
        (
            full_name, first_name, last_name, title, linkedin_url, business_id,
            source_name, source_record_id, confidence, acquired_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            full_name,
            first_name,
            last_name,
            _value(row, "title"),
            _value(row, "linkedin_url"),
            business_id,
            source_name,
            record_id,
            0.8,
            now,
        ),
    )
    return int(cursor.rowcount)


def _person_id(conn: sqlite3.Connection, source_name: str, record_id: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM people WHERE source_name=? AND source_record_id=?",
        (source_name, record_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_contact(
    conn: sqlite3.Connection,
    contact_type: str,
    contact_value: str,
    source_name: str,
    business_id: int | None,
    person_id: int | None,
    now: str,
) -> int:
    if not contact_value:
        return 0
    cursor = conn.execute(
        """INSERT OR IGNORE INTO contacts
        (
            contact_type, contact_value, business_id, person_id, source_name,
            verification_status, confidence, acquired_at
        )
        VALUES (?, ?, ?, ?, ?, 'unverified', ?, ?)""",
        (contact_type, contact_value, business_id, person_id, source_name, 0.75, now),
    )
    return int(cursor.rowcount)


def import_csv(
    csv_path: str | Path,
    *,
    db_path: str | Path,
    source_name: str = "csv_import",
    provenance_note: str = "",
) -> CsvImportResult:
    require_source_allowed(db_path, source_name)

    conn = get_connection(db_path)
    init_acquisition_db(conn)
    rows_seen = 0
    raw_written = 0
    businesses_written = 0
    people_written = 0
    contacts_written = 0
    now = datetime.now(UTC).isoformat()
    try:
        with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows_seen += 1
                record_id = _source_record_id(row)
                raw_written += _insert_raw_record(
                    conn,
                    source_name,
                    record_id,
                    row,
                    now,
                    provenance_note,
                )
                businesses_written += _insert_business(conn, row, source_name, record_id, now)
                business_id = _business_id(conn, source_name, record_id)
                people_written += _insert_person(
                    conn,
                    row,
                    source_name,
                    record_id,
                    business_id,
                    now,
                )
                person_id = _person_id(conn, source_name, record_id)
                contacts_written += _insert_contact(
                    conn,
                    "email",
                    _value(row, "email"),
                    source_name,
                    business_id,
                    person_id,
                    now,
                )
                contacts_written += _insert_contact(
                    conn,
                    "phone",
                    _value(row, "phone"),
                    source_name,
                    business_id,
                    person_id,
                    now,
                )
                contacts_written += _insert_contact(
                    conn,
                    "website",
                    _value(row, "website"),
                    source_name,
                    business_id,
                    person_id,
                    now,
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return CsvImportResult(
        rows_seen=rows_seen,
        raw_records_written=raw_written,
        businesses_written=businesses_written,
        people_written=people_written,
        contacts_written=contacts_written,
    )
