"""SQLite connection factory and schema initialization."""

import re
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "data/scraper.sqlite"
ARABIC_ROLE_TERMS = ("مصنع", "مستورد", "موزع")

def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection with WAL mode enabled."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


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


def _backfill_legacy_business_facets(conn: sqlite3.Connection) -> None:
    business_count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    facet_count = conn.execute("SELECT COUNT(*) FROM business_facets").fetchone()[0]
    if business_count == 0 or facet_count > 0:
        return

    productive_jobs = conn.execute(
        """SELECT target_type, target_slug, city_slug, rows_written
        FROM scrape_jobs
        WHERE status='done' AND rows_written > 0
        ORDER BY id"""
    ).fetchall()
    if len(productive_jobs) != 1:
        return

    job = productive_jobs[0]
    if job["rows_written"] != business_count:
        return

    target_type = job["target_type"]
    target_slug = job["target_slug"]
    city_slug = job["city_slug"]
    conn.execute(
        """INSERT OR IGNORE INTO business_facets (source_url, facet_type, slug, name)
        SELECT source_url, ?, ?, ?
        FROM businesses""",
        (target_type, target_slug, target_slug),
    )
    if city_slug:
        conn.execute(
            """INSERT OR IGNORE INTO business_facets (source_url, facet_type, slug, name)
            SELECT source_url, 'city', ?, ?
            FROM businesses""",
            (city_slug, city_slug),
        )
    if target_type == "category":
        conn.execute(
            """UPDATE businesses
            SET category_slug=?
            WHERE category_slug IS NULL OR category_slug=''""",
            (target_slug,),
        )
    if city_slug:
        conn.execute(
            """UPDATE businesses
            SET city_slug=?
            WHERE city_slug IS NULL OR city_slug=''""",
            (city_slug,),
        )


_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


def _normalized_words(value: str) -> str:
    return f" {_NON_WORD_RE.sub(' ', value.lower()).strip()} "


def _location_matches(address_text: str, name: str, slug: str) -> bool:
    candidates = {_normalized_words(name), _normalized_words(slug.replace("-", " "))}
    return any(candidate.strip() and candidate in address_text for candidate in candidates)


def _city_matches(raw_address: str, name: str, slug: str) -> bool:
    candidates = {name.lower(), slug.replace("-", " ").lower()}
    for candidate in candidates:
        if not candidate:
            continue
        pattern = rf"(?:^|,)\s*{re.escape(candidate)}(?:\s|,|$)"
        if re.search(pattern, raw_address.lower()):
            return True
    return False


def _sync_location_facets_from_addresses(conn: sqlite3.Connection) -> None:
    signature = conn.execute(
        """SELECT
            (SELECT COUNT(*) FROM businesses),
            (SELECT COALESCE(MAX(id), 0) FROM businesses),
            (SELECT COALESCE(MAX(scraped_at), '') FROM businesses),
            (SELECT COUNT(*) FROM locations),
            (SELECT COALESCE(MAX(
                slug || ':' || name || ':' || type || ':' || COALESCE(parent_slug, '')
            ), '')
             FROM locations)
        """
    ).fetchone()
    signature_value = "|".join(str(part) for part in signature)
    previous_signature = conn.execute(
        "SELECT value FROM schema_meta WHERE key='location_facet_sync_signature'"
    ).fetchone()
    has_location_facets = conn.execute(
        "SELECT 1 FROM business_facets WHERE facet_type IN ('city','area','district') LIMIT 1"
    ).fetchone()
    if (
        previous_signature is not None
        and previous_signature["value"] == signature_value
        and has_location_facets is not None
    ):
        return

    locations = conn.execute(
        """SELECT slug, name, type
        FROM locations
        WHERE type IN ('city','area','district')
        ORDER BY CASE type WHEN 'district' THEN 0 WHEN 'area' THEN 1 ELSE 2 END,
                 length(name) DESC"""
    ).fetchall()
    businesses = conn.execute(
        "SELECT source_url, address FROM businesses WHERE address IS NOT NULL AND address<>''"
    ).fetchall()
    if not locations or not businesses:
        conn.execute(
            """INSERT OR REPLACE INTO schema_meta (key, value)
            VALUES ('location_facet_sync_signature', ?)""",
            (signature_value,),
        )
        return

    matches: list[tuple[str, str, str, str]] = []
    city_by_url: dict[str, str] = {}
    for business in businesses:
        raw_address = business["address"]
        address_text = _normalized_words(business["address"])
        for location in locations:
            if location["type"] == "city":
                is_match = _city_matches(raw_address, location["name"], location["slug"])
            else:
                is_match = _location_matches(address_text, location["name"], location["slug"])
            if not is_match:
                continue
            matches.append(
                (
                    business["source_url"],
                    location["type"],
                    location["slug"],
                    location["name"],
                )
            )
            if location["type"] == "city" and business["source_url"] not in city_by_url:
                city_by_url[business["source_url"]] = location["slug"]

    if not matches:
        conn.execute(
            """INSERT OR REPLACE INTO schema_meta (key, value)
            VALUES ('location_facet_sync_signature', ?)""",
            (signature_value,),
        )
        return

    conn.execute("DELETE FROM business_facets WHERE facet_type IN ('city','area','district')")
    conn.executemany(
        """INSERT OR IGNORE INTO business_facets (source_url, facet_type, slug, name)
        VALUES (?, ?, ?, ?)""",
        matches,
    )
    conn.execute("UPDATE businesses SET city_slug=''")
    conn.executemany(
        "UPDATE businesses SET city_slug=? WHERE source_url=?",
        [(slug, source_url) for source_url, slug in city_by_url.items()],
    )
    conn.execute(
        """INSERT OR REPLACE INTO schema_meta (key, value)
        VALUES ('location_facet_sync_signature', ?)""",
        (signature_value,),
    )


def _seed_arabic_role_terms(conn: sqlite3.Connection) -> None:
    for term in ARABIC_ROLE_TERMS:
        conn.execute(
            """INSERT OR IGNORE INTO categories
            (slug, name, parent_slug, result_count, href, scraped_at)
            VALUES (?, ?, '', 0, ?, '')""",
            (term, term, f"/ar/keyword/{term}"),
        )
        conn.execute(
            """INSERT OR IGNORE INTO keywords (slug, name, href, scraped_at)
            VALUES (?, ?, ?, '')""",
            (term, term, f"/ar/keyword/{term}"),
        )


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if not present. Idempotent."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_slug TEXT,
            result_count INTEGER DEFAULT 0,
            href TEXT DEFAULT '',
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS brands (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            href TEXT DEFAULT '',
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS keywords (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            href TEXT DEFAULT '',
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS locations (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('city','area','district')),
            external_id TEXT DEFAULT '',
            parent_slug TEXT,
            result_count INTEGER DEFAULT 0,
            scraped_at TEXT,
            FOREIGN KEY (parent_slug) REFERENCES locations(slug)
        );

        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT UNIQUE NOT NULL,
            business_name TEXT DEFAULT '',
            business_name_ar TEXT DEFAULT '',
            category_slug TEXT,
            category_ar TEXT DEFAULT '',
            city_slug TEXT,
            governorate_ar TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            website TEXT DEFAULT '',
            facebook_url TEXT DEFAULT '',
            address TEXT DEFAULT '',
            address_ar TEXT DEFAULT '',
            raw_html_hash TEXT DEFAULT '',
            source_tier INTEGER DEFAULT 0,
            scraped_at TEXT,
            FOREIGN KEY (category_slug) REFERENCES categories(slug),
            FOREIGN KEY (city_slug) REFERENCES locations(slug)
        );

        CREATE INDEX IF NOT EXISTS idx_businesses_category
            ON businesses(category_slug, city_slug);

        CREATE TABLE IF NOT EXISTS business_facets (
            source_url TEXT NOT NULL,
            facet_type TEXT NOT NULL CHECK(
                facet_type IN ('category','brand','keyword','city','area','district')
            ),
            slug TEXT NOT NULL,
            name TEXT DEFAULT '',
            PRIMARY KEY (source_url, facet_type, slug),
            FOREIGN KEY (source_url) REFERENCES businesses(source_url)
        );

        CREATE INDEX IF NOT EXISTS idx_business_facets_type_slug
            ON business_facets(facet_type, slug);

        CREATE TABLE IF NOT EXISTS scrape_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL DEFAULT 'category'
                CHECK(target_type IN ('category','brand','keyword')),
            target_slug TEXT NOT NULL DEFAULT '',
            category_slug TEXT NOT NULL,
            city_slug TEXT DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed')),
            pages_scraped INTEGER DEFAULT 0,
            rows_written INTEGER DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            error TEXT DEFAULT '',
            UNIQUE(target_type, target_slug, city_slug)
        );

        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

    """)
    _add_column_if_missing(conn, "categories", "result_count", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "categories", "href", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "locations", "external_id", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "locations", "result_count", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "businesses", "business_name_ar", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "category_ar", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "governorate_ar", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "businesses", "address_ar", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "scrape_jobs", "target_type", "TEXT NOT NULL DEFAULT 'category'")
    _add_column_if_missing(conn, "scrape_jobs", "target_slug", "TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """UPDATE scrape_jobs
        SET target_slug = category_slug
        WHERE target_slug = '' AND category_slug IS NOT NULL"""
    )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_scrape_jobs_target_city
        ON scrape_jobs(target_type, target_slug, city_slug)"""
    )
    _backfill_legacy_business_facets(conn)
    _sync_location_facets_from_addresses(conn)
    _seed_arabic_role_terms(conn)
    conn.commit()
