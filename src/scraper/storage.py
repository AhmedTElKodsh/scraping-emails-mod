"""Storage backend selection helpers."""

from pathlib import Path
from typing import Any, Literal

from scraper.config import Settings
from scraper.db import get_connection as get_sqlite_connection
from scraper.db import init_db as init_sqlite_db

Backend = Literal["sqlite", "postgres"]


def is_postgres_url(value: str | Path | None) -> bool:
    """Return True when a storage value is a Postgres connection URL."""
    if value is None:
        return False
    text = str(value).strip().lower()
    return text.startswith(("postgres://", "postgresql://"))


def storage_target(
    db_path: str | Path | None = None,
    settings: Settings | None = None,
) -> str | Path:
    """Return the active storage target, preferring DATABASE_URL over DB_PATH."""
    settings = settings or Settings()
    return settings.database_url or db_path or settings.db_path


def open_connection(target: str | Path | None = None) -> tuple[Any, Backend]:
    """Open and initialize the configured SQLite or Postgres database."""
    if is_postgres_url(target):
        from scraper.postgres_db import get_connection, init_db

        conn = get_connection(str(target))
        init_db(conn)
        return conn, "postgres"

    conn = get_sqlite_connection(target)
    init_sqlite_db(conn)
    return conn, "sqlite"


def placeholder(backend: Backend) -> str:
    return "%s" if backend == "postgres" else "?"
