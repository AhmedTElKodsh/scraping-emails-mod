"""Postgres ResultWriter implementation."""

from datetime import UTC, datetime

from scraper.models import Facet, ScrapeResult
from scraper.postgres_db import get_connection, init_db


class PostgresWriter:
    """Writes scrape results to Postgres with source URL deduplication."""

    def __init__(self, database_url: str) -> None:
        self._conn = get_connection(database_url)
        init_db(self._conn)

    def write(self, result: ScrapeResult) -> int:
        """Write result. Returns 1 if anything new was inserted, otherwise 0."""
        try:
            now = result.scraped_at or datetime.now(UTC).isoformat()
            cursor = self._conn.execute(
                """INSERT INTO businesses
                (source_url, business_name, business_name_ar,
                 category_slug, category_ar, city_slug, governorate_ar,
                 phone, email, website, facebook_url, address,
                 address_ar, raw_html_hash, source_tier, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO NOTHING""",
                (
                    result.url,
                    result.business_name,
                    result.business_name_ar,
                    result.category,
                    result.category_ar,
                    result.governorate,
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
            saved_rows += self.write_facets(result.url, result.facets, commit=False)
            self._conn.commit()
            return 1 if saved_rows > 0 else 0
        except Exception:
            self._conn.rollback()
            return 0

    def has_url(self, source_url: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM businesses WHERE source_url=%s LIMIT 1",
            (source_url,),
        ).fetchone()
        return row is not None

    def has_arabic_fields(self, source_url: str) -> bool:
        row = self._conn.execute(
            """SELECT business_name_ar, address_ar
            FROM businesses WHERE source_url=%s LIMIT 1""",
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
                SET business_name_ar=COALESCE(NULLIF(%s, ''), business_name_ar),
                    category_ar=COALESCE(NULLIF(%s, ''), category_ar),
                    governorate_ar=COALESCE(NULLIF(%s, ''), governorate_ar),
                    address_ar=COALESCE(NULLIF(%s, ''), address_ar)
                WHERE source_url=%s""",
                (
                    arabic.business_name,
                    arabic.category,
                    arabic.governorate,
                    arabic.address,
                    source_url,
                ),
            )
            self._conn.commit()
            return cursor.rowcount
        except Exception:
            self._conn.rollback()
            return 0

    def write_facets(
        self,
        source_url: str,
        facets: list[Facet],
        commit: bool = True,
    ) -> int:
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
                    (source_url, facet_type, slug, name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_url, facet_type, slug) DO NOTHING""",
                    (source_url, facet.type, facet.slug, facet.name),
                )
                saved_rows += cursor.rowcount
            if commit:
                self._conn.commit()
            return saved_rows
        except Exception:
            self._conn.rollback()
            return 0

    def close(self) -> None:
        self._conn.close()
