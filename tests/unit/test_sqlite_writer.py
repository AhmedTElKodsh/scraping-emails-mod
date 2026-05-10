"""Unit tests for sqlite_writer.py."""

from pathlib import Path

from scraper.models import Facet, ScrapeResult


def test_write_returns_1_on_insert(tmp_path: Path) -> None:
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    result = ScrapeResult(url="http://example.com/1", business_name="Test Biz")
    assert writer.write(result) == 1
    writer.close()


def test_duplicate_source_url_returns_0_not_raises(tmp_path: Path) -> None:
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    result = ScrapeResult(url="http://example.com/1", business_name="Test Biz")
    writer.write(result)
    assert writer.write(result) == 0
    writer.close()


def test_dedup_persists_across_writer_instances(tmp_path: Path) -> None:
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer1 = SQLiteWriter(db_path)
    r1 = ScrapeResult(url="http://example.com/1", business_name="Biz 1")
    assert writer1.write(r1) == 1
    writer1.close()

    writer2 = SQLiteWriter(db_path)
    assert writer2.write(r1) == 0
    writer2.close()


def test_null_email_handled(tmp_path: Path) -> None:
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    result = ScrapeResult(url="http://example.com/2", emails=[])
    assert writer.write(result) == 1
    writer.close()


def test_duplicate_business_with_new_facet_counts_as_saved_work(tmp_path: Path) -> None:
    from scraper.db import get_connection
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    writer.write(
        ScrapeResult(
            url="http://example.com/1",
            business_name="Test Biz",
            facets=[Facet(type="category", slug="air-conditioning", name="Air Conditioning")],
        )
    )
    assert writer.write(
        ScrapeResult(
            url="http://example.com/1",
            business_name="Test Biz",
            facets=[Facet(type="brand", slug="carrier", name="Carrier")],
        )
    ) == 1
    writer.close()

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT facet_type, slug, name FROM business_facets WHERE source_url=? ORDER BY facet_type",
        ("http://example.com/1",),
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("brand", "carrier", "Carrier"),
        ("category", "air-conditioning", "Air Conditioning"),
    ]
    conn.close()


def test_has_url_and_write_facets_support_skip_without_detail_refetch(tmp_path: Path) -> None:
    from scraper.db import get_connection
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    source_url = "http://example.com/1"
    writer.write(ScrapeResult(url=source_url, business_name="Test Biz"))

    assert writer.has_url(source_url) is True
    assert writer.write_facets(
        source_url,
        [Facet(type="brand", slug="carrier", name="Carrier")],
    ) == 1
    writer.close()

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT facet_type, slug, name FROM business_facets WHERE source_url=?",
        (source_url,),
    ).fetchall()
    assert [tuple(row) for row in rows] == [("brand", "carrier", "Carrier")]
    conn.close()
