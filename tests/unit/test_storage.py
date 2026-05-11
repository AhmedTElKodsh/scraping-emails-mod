from pathlib import Path
from types import SimpleNamespace

from scraper.storage import storage_target


def test_storage_target_honors_explicit_db_path_over_database_url(tmp_path: Path) -> None:
    db_path = tmp_path / "local.sqlite"
    settings = SimpleNamespace(
        database_url="postgresql://example/db",
        db_path="data/scraper.sqlite",
    )

    assert storage_target(db_path, settings) == db_path


def test_storage_target_uses_database_url_when_no_explicit_db_path() -> None:
    settings = SimpleNamespace(
        database_url="postgresql://example/db",
        db_path="data/scraper.sqlite",
    )

    assert storage_target(None, settings) == "postgresql://example/db"
