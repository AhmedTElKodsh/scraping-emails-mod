"""Separate SQLite database for compliant acquisition experiments."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_ACQUISITION_DB_PATH = "data/acquisition.sqlite"

DEFAULT_SOURCES = [
    {
        "source_name": "yellowpages",
        "source_type": "public_directory",
        "allowed_use_note": (
            "Permitted public-directory business discovery with conservative crawling "
            "and provenance."
        ),
        "terms_url": "https://yellowpages.com.eg",
        "requires_api_key": 0,
        "can_collect_people": 0,
        "can_collect_contacts": 1,
        "can_enrich": 0,
        "is_paid": 0,
        "enabled": 1,
    },
    {
        "source_name": "csv_import",
        "source_type": "user_owned_import",
        "allowed_use_note": "User-owned CSV import; caller must provide source/license provenance.",
        "terms_url": "local:user-owned-import",
        "requires_api_key": 0,
        "can_collect_people": 1,
        "can_collect_contacts": 1,
        "can_enrich": 0,
        "is_paid": 0,
        "enabled": 1,
    },
    {
        "source_name": "apollo_csv_export",
        "source_type": "user_export",
        "allowed_use_note": "User-exported Apollo CSV only; no UI automation.",
        "terms_url": "https://knowledge.apollo.io/hc/en-us/articles/4409237712141-Export-Contacts-to-a-CSV",
        "requires_api_key": 0,
        "can_collect_people": 1,
        "can_collect_contacts": 1,
        "can_enrich": 0,
        "is_paid": 0,
        "enabled": 1,
    },
    {
        "source_name": "apollo_people_search",
        "source_type": "official_api",
        "allowed_use_note": (
            "Official Apollo People API Search for candidate discovery only; "
            "no emails or phones."
        ),
        "terms_url": "https://docs.apollo.io/reference/people-api-search",
        "requires_api_key": 1,
        "can_collect_people": 1,
        "can_collect_contacts": 0,
        "can_enrich": 0,
        "is_paid": 0,
        "enabled": 1,
    },
    {
        "source_name": "apollo_enrichment",
        "source_type": "official_paid_api",
        "allowed_use_note": (
            "Official Apollo enrichment only with explicit paid budget and usage checks."
        ),
        "terms_url": "https://docs.apollo.io/reference/people-enrichment",
        "requires_api_key": 1,
        "can_collect_people": 1,
        "can_collect_contacts": 1,
        "can_enrich": 1,
        "is_paid": 1,
        "enabled": 1,
    },
    {
        "source_name": "hunter",
        "source_type": "email_finder",
        "allowed_use_note": (
            "Email finder pilot quotas only; validate vendor terms before live use."
        ),
        "terms_url": "https://hunter.io/pricing",
        "requires_api_key": 1,
        "can_collect_people": 0,
        "can_collect_contacts": 1,
        "can_enrich": 1,
        "is_paid": 1,
        "enabled": 0,
    },
    {
        "source_name": "snov",
        "source_type": "email_finder",
        "allowed_use_note": (
            "Email finder trial/paid quotas only; validate vendor terms before live use."
        ),
        "terms_url": "https://snov.io/pricing",
        "requires_api_key": 1,
        "can_collect_people": 0,
        "can_collect_contacts": 1,
        "can_enrich": 1,
        "is_paid": 1,
        "enabled": 0,
    },
    {
        "source_name": "findymail",
        "source_type": "email_finder",
        "allowed_use_note": (
            "Email finder pilot quotas only; validate vendor terms before live use."
        ),
        "terms_url": "https://www.findymail.com/api/",
        "requires_api_key": 1,
        "can_collect_people": 0,
        "can_collect_contacts": 1,
        "can_enrich": 1,
        "is_paid": 1,
        "enabled": 0,
    },
    {
        "source_name": "reoon",
        "source_type": "email_verifier",
        "allowed_use_note": "Email verification only; does not discover missing emails.",
        "terms_url": "https://www.reoon.com/email-verifier/",
        "requires_api_key": 1,
        "can_collect_people": 0,
        "can_collect_contacts": 0,
        "can_enrich": 1,
        "is_paid": 0,
        "enabled": 1,
    },
    {
        "source_name": "zerobounce",
        "source_type": "email_verifier",
        "allowed_use_note": "Email verification benchmark only; does not discover missing emails.",
        "terms_url": "https://www.zerobounce.net/email-validation-pricing",
        "requires_api_key": 1,
        "can_collect_people": 0,
        "can_collect_contacts": 0,
        "can_enrich": 1,
        "is_paid": 0,
        "enabled": 0,
    },
]


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_ACQUISITION_DB_PATH
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_default_sources(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO sources (
            source_name, source_type, allowed_use_note, terms_url, requires_api_key,
            can_collect_people, can_collect_contacts, can_enrich, is_paid, enabled
        )
        VALUES (
            :source_name, :source_type, :allowed_use_note, :terms_url, :requires_api_key,
            :can_collect_people, :can_collect_contacts, :can_enrich, :is_paid, :enabled
        )""",
        DEFAULT_SOURCES,
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _backfill_business_merge_keys(conn: sqlite3.Connection) -> None:
    conn.execute(
        """UPDATE businesses
        SET city_slug=city
        WHERE (city_slug IS NULL OR city_slug='') AND city<>''"""
    )
    conn.execute(
        """UPDATE businesses
        SET raw_html_hash=source_record_id
        WHERE (raw_html_hash IS NULL OR raw_html_hash='') AND source_record_id<>''"""
    )
    conn.execute(
        """UPDATE businesses
        SET source_tier=source_name
        WHERE (source_tier IS NULL OR source_tier='') AND source_name<>''"""
    )
    conn.execute(
        """UPDATE businesses
        SET scraped_at=acquired_at
        WHERE scraped_at IS NULL AND acquired_at<>''"""
    )


def init_acquisition_db(conn: sqlite3.Connection) -> None:
    """Create separate acquisition tables with merge-friendly normalized fields."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            source_name TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            allowed_use_note TEXT NOT NULL DEFAULT '',
            terms_url TEXT NOT NULL DEFAULT '',
            requires_api_key INTEGER NOT NULL DEFAULT 0,
            can_collect_people INTEGER NOT NULL DEFAULT 0,
            can_collect_contacts INTEGER NOT NULL DEFAULT 0,
            can_enrich INTEGER NOT NULL DEFAULT 0,
            is_paid INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS acquisition_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            query_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL CHECK(status IN (
                'draft','pending','running','succeeded','blocked','failed'
            )),
            dry_run INTEGER NOT NULL DEFAULT 1,
            record_budget INTEGER DEFAULT 0,
            credit_budget INTEGER DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            error TEXT DEFAULT '',
            FOREIGN KEY (source_name) REFERENCES sources(source_name)
        );

        CREATE TABLE IF NOT EXISTS acquisition_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            cursor TEXT DEFAULT '',
            page INTEGER DEFAULT 0,
            status TEXT NOT NULL CHECK(status IN (
                'pending','leased','succeeded','retry_wait','blocked_budget',
                'blocked_rate','skipped_duplicate','skipped_policy','failed'
            )),
            attempts INTEGER NOT NULL DEFAULT 0,
            next_run_at TEXT,
            estimated_credits INTEGER DEFAULT 0,
            actual_credits INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            FOREIGN KEY (run_id) REFERENCES acquisition_runs(id)
        );

        CREATE TABLE IF NOT EXISTS credit_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            run_id INTEGER,
            task_id INTEGER,
            credit_kind TEXT NOT NULL DEFAULT 'unknown',
            estimated INTEGER DEFAULT 0,
            actual INTEGER DEFAULT 0,
            checked_at TEXT NOT NULL,
            FOREIGN KEY (source_name) REFERENCES sources(source_name)
        );

        CREATE TABLE IF NOT EXISTS raw_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            provenance_note TEXT NOT NULL DEFAULT '',
            UNIQUE(source_name, source_record_id)
        );

        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT NOT NULL DEFAULT '',
            business_name TEXT NOT NULL DEFAULT '',
            category_slug TEXT DEFAULT '',
            city_slug TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            normalized_business_name TEXT NOT NULL DEFAULT '',
            website TEXT NOT NULL DEFAULT '',
            facebook_url TEXT DEFAULT '',
            domain TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            raw_html_hash TEXT DEFAULT '',
            source_tier TEXT DEFAULT '',
            scraped_at TEXT,
            city TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            source_name TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            acquired_at TEXT NOT NULL,
            UNIQUE(source_name, source_record_id)
        );

        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT '',
            first_name TEXT NOT NULL DEFAULT '',
            last_name TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            seniority TEXT NOT NULL DEFAULT '',
            linkedin_url TEXT NOT NULL DEFAULT '',
            business_id INTEGER,
            source_name TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            acquired_at TEXT NOT NULL,
            UNIQUE(source_name, source_record_id),
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_type TEXT NOT NULL CHECK(contact_type IN ('email','phone','website')),
            contact_value TEXT NOT NULL,
            business_id INTEGER,
            person_id INTEGER,
            source_name TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'unknown',
            confidence REAL NOT NULL DEFAULT 0,
            acquired_at TEXT NOT NULL,
            UNIQUE(contact_type, contact_value, source_name),
            FOREIGN KEY (business_id) REFERENCES businesses(id),
            FOREIGN KEY (person_id) REFERENCES people(id)
        );

        CREATE TABLE IF NOT EXISTS source_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('business','person','contact')),
            entity_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            acquired_at TEXT NOT NULL,
            UNIQUE(entity_type, entity_id, source_name, source_record_id)
        );

        CREATE TABLE IF NOT EXISTS suppression_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suppression_type TEXT NOT NULL CHECK(
                suppression_type IN ('email','domain','phone','person','company')
            ),
            suppression_value TEXT NOT NULL,
            reason TEXT NOT NULL,
            source_name TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(suppression_type, suppression_value)
        );
    """)
    _add_column_if_missing(conn, "businesses", "category_slug", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "city_slug", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "facebook_url", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "raw_html_hash", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "source_tier", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "scraped_at", "TEXT")
    _add_column_if_missing(conn, "businesses", "confidence", "REAL NOT NULL DEFAULT 0")
    _backfill_business_merge_keys(conn)
    _seed_default_sources(conn)
    conn.commit()
