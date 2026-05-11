"""Copy the local SQLite scraper database into configured Postgres storage."""

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from scraper.config import Settings
from scraper.postgres_db import get_connection as get_postgres_connection
from scraper.postgres_db import init_db as init_postgres_db

TABLES = (
    "categories",
    "brands",
    "keywords",
    "locations",
    "businesses",
    "business_facets",
    "scrape_jobs",
    "schema_meta",
)

CONFLICT_TARGETS = {
    "categories": "slug",
    "brands": "slug",
    "keywords": "slug",
    "locations": "slug",
    "businesses": "source_url",
    "business_facets": "source_url, facet_type, slug",
    "scrape_jobs": "target_type, target_slug, city_slug",
    "schema_meta": "key",
}


def _sqlite_rows(sqlite_path: Path, table: str) -> tuple[list[str], list[sqlite3.Row]]:
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
        return columns, rows
    finally:
        conn.close()


def migrate(sqlite_path: str | Path, database_url: str) -> dict[str, int]:
    """Migrate rows from SQLite to Postgres, skipping existing conflicts."""
    sqlite_path = Path(sqlite_path)
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    pg = get_postgres_connection(database_url)
    init_postgres_db(pg)
    copied: dict[str, int] = {}
    try:
        for table in TABLES:
            columns, rows = _sqlite_rows(sqlite_path, table)
            if not rows:
                copied[table] = 0
                continue

            # Let Postgres generate identity ids; uniqueness is enforced by source/natural keys.
            if table in {"businesses", "scrape_jobs"} and "id" in columns:
                columns = [column for column in columns if column != "id"]

            quoted_columns = ", ".join(columns)
            placeholders = ", ".join("%s" for _ in columns)
            conflict_target = CONFLICT_TARGETS[table]
            sql = (
                f"INSERT INTO {table} ({quoted_columns}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_target}) DO NOTHING"
            )
            values: list[tuple[Any, ...]] = [
                tuple(row[column] for column in columns)
                for row in rows
            ]
            with pg.cursor() as cur:
                cur.executemany(sql, values)
                copied[table] = cur.rowcount if cur.rowcount >= 0 else 0
        pg.commit()
        return copied
    except Exception:
        pg.rollback()
        raise
    finally:
        pg.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-path", default=None)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    cfg = Settings()
    database_url = args.database_url or cfg.database_url
    if not database_url:
        raise SystemExit("Set DATABASE_URL or pass --database-url before running migration.")

    copied = migrate(args.sqlite_path or cfg.db_path, database_url)
    for table, count in copied.items():
        print(f"{table}: {count} inserted")


if __name__ == "__main__":
    main()
