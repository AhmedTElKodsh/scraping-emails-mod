from pathlib import Path


def test_valid_location_parent_rows_only_keeps_existing_parents(tmp_path: Path) -> None:
    from scraper.db import get_connection, init_db
    from scraper.migrate_to_postgres import _valid_location_parent_rows

    db_path = tmp_path / "scraper.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO locations (slug, name, type, parent_slug)
        VALUES
            ('cairo', 'Cairo', 'city', ''),
            ('maadi', 'Maadi', 'area', 'cairo'),
            ('orphan-area', 'Orphan Area', 'area', 'missing-city');
        """
    )
    conn.close()

    assert _valid_location_parent_rows(db_path) == [("cairo", "maadi")]
