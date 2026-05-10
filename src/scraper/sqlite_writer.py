"""SQLiteWriter implementing ResultWriter Protocol.

Persistent cross-run dedup via DB constraint (INSERT OR IGNORE on source_url).
"""

from datetime import UTC, datetime
from pathlib import Path

from scraper.db import get_connection
from scraper.models import Facet, ScrapeResult


class SQLiteWriter:
    """Writes results to SQLite. Implements ResultWriter Protocol.
    Persistent dedup via INSERT OR IGNORE on source_url."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._conn = get_connection(db_path)
        from scraper.db import init_db
        init_db(self._conn)

    def write(self, result: ScrapeResult) -> int:
        """Write result. Returns 1 if inserted, 0 if duplicate (source_url conflict)."""
        try:
            now = (result.scraped_at or datetime.now(UTC).isoformat())
            cursor = self._conn.execute(
                """INSERT OR IGNORE INTO businesses
                (source_url, business_name, category_slug, city_slug,
                 phone, email, website, facebook_url, address,
                 raw_html_hash, source_tier, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.url,
                    result.business_name,
                    result.category,
                    result.governorate,
                    result.phone,
                    ",".join(result.emails) if result.emails else "",
                    result.website,
                    result.facebook_url,
                    result.address,
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
                    """INSERT OR IGNORE INTO business_facets
                    (source_url, facet_type, slug, name)
                    VALUES (?, ?, ?, ?)""",
                    (result.url, facet.type, facet.slug, facet.name),
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
                    """INSERT OR IGNORE INTO business_facets
                    (source_url, facet_type, slug, name)
                    VALUES (?, ?, ?, ?)""",
                    (source_url, facet.type, facet.slug, facet.name),
                )
                saved_rows += cursor.rowcount
            self._conn.commit()
            return saved_rows
        except Exception:
            self._conn.rollback()
            return 0

    def close(self) -> None:
        self._conn.close()
