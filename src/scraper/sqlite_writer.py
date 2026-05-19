"""SQLiteWriter implementing ResultWriter Protocol.

Persistent cross-run dedup via DB constraint (INSERT OR IGNORE on source_url).
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scraper.db import get_connection
from scraper.models import Facet, ScrapeResult


class SQLiteWriter:
    """Writes results to SQLite. Implements ResultWriter Protocol.
    Persistent dedup via INSERT OR IGNORE on source_url."""

    refresh_existing = True

    def __init__(
        self,
        db_path: str | Path | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._owns_connection = conn is None
        self._conn = conn or get_connection(db_path)
        from scraper.db import init_db

        init_db(self._conn)

    def _first_facet_value(self, result: ScrapeResult, facet_type: str, field: str) -> str:
        for facet in result.facets:
            if facet.type == facet_type:
                value = getattr(facet, field)
                if value:
                    return value
        return ""

    def write(self, result: ScrapeResult) -> int:
        """Write result. Returns 1 if inserted, 0 if duplicate (source_url conflict)."""
        try:
            now = (result.scraped_at or datetime.now(UTC).isoformat())
            category_slug = result.category or self._first_facet_value(result, "category", "slug")
            category_ar = result.category_ar or self._first_facet_value(
                result,
                "category",
                "name_ar",
            )
            city_slug = result.governorate or self._first_facet_value(result, "city", "slug")
            cursor = self._conn.execute(
                """INSERT INTO businesses
                (source_url, business_name, business_name_ar,
                 category_slug, category_ar, city_slug, governorate_ar,
                 phone, email, website, facebook_url, address,
                 address_ar, raw_html_hash, source_tier, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    business_name=COALESCE(NULLIF(excluded.business_name, ''), businesses.business_name),
                    business_name_ar=COALESCE(NULLIF(excluded.business_name_ar, ''), businesses.business_name_ar),
                    category_slug=COALESCE(NULLIF(excluded.category_slug, ''), businesses.category_slug),
                    category_ar=COALESCE(NULLIF(excluded.category_ar, ''), businesses.category_ar),
                    city_slug=COALESCE(NULLIF(excluded.city_slug, ''), businesses.city_slug),
                    governorate_ar=COALESCE(NULLIF(excluded.governorate_ar, ''), businesses.governorate_ar),
                    phone=COALESCE(NULLIF(excluded.phone, ''), businesses.phone),
                    email=COALESCE(NULLIF(excluded.email, ''), businesses.email),
                    website=COALESCE(NULLIF(excluded.website, ''), businesses.website),
                    facebook_url=COALESCE(NULLIF(excluded.facebook_url, ''), businesses.facebook_url),
                    address=COALESCE(NULLIF(excluded.address, ''), businesses.address),
                    address_ar=COALESCE(NULLIF(excluded.address_ar, ''), businesses.address_ar),
                    raw_html_hash=COALESCE(NULLIF(excluded.raw_html_hash, ''), businesses.raw_html_hash),
                    source_tier=CASE
                        WHEN excluded.source_tier != 0 THEN excluded.source_tier
                        ELSE businesses.source_tier
                    END,
                    scraped_at=excluded.scraped_at""",
                (
                    result.url,
                    result.business_name,
                    result.business_name_ar,
                    category_slug,
                    category_ar,
                    city_slug,
                    result.governorate_ar,
                    result.phone,
                    ",".join(result.emails) if result.emails else "",
                    result.website,
                    result.facebook_url,
                    result.address,
                    result.address_ar,
                    result.raw_html_hash,
                    result.source_tier,
                    now,
                ),
            )
            saved_rows = cursor.rowcount
            for facet in result.facets:
                if not facet.type or not facet.slug:
                    continue
                facet_cursor = self._conn.execute(
                    """INSERT INTO business_facets
                    (source_url, facet_type, slug, name, name_ar)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_url, facet_type, slug) DO UPDATE SET
                        name=COALESCE(NULLIF(excluded.name, ''), business_facets.name),
                        name_ar=COALESCE(NULLIF(excluded.name_ar, ''), business_facets.name_ar)""",
                    (result.url, facet.type, facet.slug, facet.name, facet.name_ar),
                )
                saved_rows += facet_cursor.rowcount
            self._conn.commit()
            return 1 if saved_rows > 0 else 0
        except Exception:
            self._conn.rollback()
            return 0

    def has_url(self, source_url: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM businesses WHERE source_url=? LIMIT 1",
            (source_url,),
        ).fetchone()
        return row is not None

    def has_arabic_fields(self, source_url: str) -> bool:
        row = self._conn.execute(
            """SELECT business_name_ar, address_ar
            FROM businesses WHERE source_url=? LIMIT 1""",
            (source_url,),
        ).fetchone()
        if row is None:
            return False
        return bool(row["business_name_ar"] or row["address_ar"])

    def update_arabic_fields(self, source_url: str, arabic: ScrapeResult) -> int:
        if not source_url:
            return 0
        try:
            cursor = self._conn.execute(
                """UPDATE businesses
                SET business_name_ar=COALESCE(NULLIF(?, ''), business_name_ar),
                    category_ar=COALESCE(NULLIF(?, ''), category_ar),
                    city_slug=COALESCE(NULLIF(?, ''), city_slug),
                    governorate_ar=COALESCE(NULLIF(?, ''), governorate_ar),
                    address_ar=COALESCE(NULLIF(?, ''), address_ar)
                WHERE source_url=?""",
                (
                    arabic.business_name,
                    arabic.category,
                    arabic.governorate,
                    arabic.governorate_ar or arabic.governorate,
                    arabic.address,
                    source_url,
                ),
            )
            self._conn.commit()
            return cursor.rowcount
        except Exception:
            self._conn.rollback()
            return 0

    def write_facets(self, source_url: str, facets: list[Facet]) -> int:
        """Attach newly discovered facets to an existing business without refetching details."""
        if not source_url or not facets:
            return 0
        try:
            saved_rows = 0
            for facet in facets:
                if not facet.type or not facet.slug:
                    continue
                cursor = self._conn.execute(
                    """INSERT INTO business_facets
                    (source_url, facet_type, slug, name, name_ar)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_url, facet_type, slug) DO UPDATE SET
                        name=COALESCE(NULLIF(excluded.name, ''), business_facets.name),
                        name_ar=COALESCE(NULLIF(excluded.name_ar, ''), business_facets.name_ar)""",
                    (source_url, facet.type, facet.slug, facet.name, facet.name_ar),
                )
                saved_rows += cursor.rowcount
            self._conn.commit()
            return saved_rows
        except Exception:
            self._conn.rollback()
            return 0

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()
