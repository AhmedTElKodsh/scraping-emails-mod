from pathlib import Path

import pytest

from scraper.models import Facet, ScrapeResult


def test_load_businesses_filters_by_single_facet_group(tmp_path: Path) -> None:
    from app.data_access import load_businesses
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    writer.write(
        ScrapeResult(
            url="https://example.com/1",
            business_name="Cool Air",
            facets=[
                Facet(type="category", slug="air-conditioning", name="Air Conditioning"),
                Facet(type="brand", slug="carrier", name="Carrier"),
            ],
        )
    )
    writer.write(
        ScrapeResult(
            url="https://example.com/2",
            business_name="Warm Air",
            facets=[Facet(type="category", slug="heaters", name="Heaters")],
        )
    )
    writer.close()

    rows = load_businesses(db_path, {"category": ["air-conditioning"]})

    assert [row["business_name"] for row in rows] == ["Cool Air"]
    assert rows[0]["matched_facets"] == "brand: Carrier, category: Air Conditioning"


def test_load_taxonomy_options_returns_table_fields(tmp_path: Path) -> None:
    from app.data_access import load_taxonomy_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.execute(
        """INSERT INTO brands (slug, name, result_count, href, scraped_at)
        VALUES ('samsung', 'Samsung', 1914, '/en/brand/samsung', '2026-05-09')"""
    )
    conn.commit()
    conn.close()

    rows = load_taxonomy_options(db_path, "brands")

    assert rows == [
        {
            "slug": "samsung",
            "name": "Samsung",
            "result_count": 1914,
            "href": "/en/brand/samsung",
            "scraped_at": "2026-05-09",
        }
    ]


def test_load_businesses_ands_across_facet_groups(tmp_path: Path) -> None:
    from app.data_access import load_businesses
    from scraper.sqlite_writer import SQLiteWriter

    db_path = tmp_path / "test.sqlite"
    writer = SQLiteWriter(db_path)
    writer.write(
        ScrapeResult(
            url="https://example.com/1",
            business_name="Carrier Cairo",
            facets=[
                Facet(type="brand", slug="carrier", name="Carrier"),
                Facet(type="city", slug="cairo", name="Cairo"),
            ],
        )
    )
    writer.write(
        ScrapeResult(
            url="https://example.com/2",
            business_name="Carrier Giza",
            facets=[
                Facet(type="brand", slug="carrier", name="Carrier"),
                Facet(type="city", slug="giza", name="Giza"),
            ],
        )
    )
    writer.close()

    rows = load_businesses(db_path, {"brand": ["carrier"], "city": ["cairo"]})

    assert [row["business_name"] for row in rows] == ["Carrier Cairo"]


def test_load_businesses_arabic_role_keyword_matches_category_facet(tmp_path: Path) -> None:
    from app.data_access import load_businesses, load_crawl_target_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO businesses (source_url, business_name)
        VALUES
            ('https://example.com/1', 'Factory One'),
            ('https://example.com/2', 'Distributor Two');

        INSERT INTO business_facets (source_url, facet_type, slug, name)
        VALUES
            ('https://example.com/1', 'category', 'مصنع', 'مصنع'),
            ('https://example.com/2', 'category', 'موزع', 'موزع');
        """
    )
    conn.close()

    options = load_crawl_target_options(db_path)
    rows = load_businesses(db_path, {"keyword": ["مصنع"]})

    assert {"slug": "مصنع", "name": "مصنع"} in [
        {"slug": row["slug"], "name": row["name"]} for row in options["categories"]
    ]
    assert {"slug": "مصنع", "name": "مصنع"} in [
        {"slug": row["slug"], "name": row["name"]} for row in options["keywords"]
    ]
    assert [row["business_name"] for row in rows] == ["Factory One"]


def test_load_matching_jobs_filters_selected_targets_and_city(tmp_path: Path) -> None:
    from app.data_access import load_matching_jobs
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO scrape_jobs
            (target_type, target_slug, category_slug, city_slug, status, rows_written)
        VALUES
            ('category', 'restaurants', 'restaurants', 'cairo', 'done', 10),
            ('category', 'hospitals', 'hospitals', 'cairo', 'done', 0),
            ('category', 'restaurants', 'restaurants', 'giza', 'done', 3),
            ('brand', 'carrier', 'carrier', 'cairo', 'done', 7),
            ('keyword', 'Advertising', 'Advertising', 'cairo', 'done', 4);
        """
    )
    conn.close()

    rows = load_matching_jobs(
        db_path,
        {"category": ["restaurants"], "brand": ["carrier"]},
        ["cairo"],
    )

    assert rows == [
        {
            "target_type": "brand",
            "target_slug": "carrier",
            "city_slug": "cairo",
            "status": "done",
            "rows_written": 7,
        },
        {
            "target_type": "category",
            "target_slug": "restaurants",
            "city_slug": "cairo",
            "status": "done",
            "rows_written": 10,
        }
    ]


def test_load_facet_options_only_returns_values_with_saved_businesses(tmp_path: Path) -> None:
    from app.data_access import load_facet_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO categories (slug, name)
        VALUES
            ('restaurants', 'Restaurants'),
            ('hospitals', 'Hospitals');

        INSERT INTO locations (slug, name, type, parent_slug)
        VALUES
            ('cairo', 'Cairo', 'city', ''),
            ('giza', 'Giza', 'city', ''),
            ('maadi', 'Maadi', 'area', 'cairo');

        INSERT INTO businesses (source_url, business_name)
        VALUES
            ('https://example.com/1', 'One'),
            ('https://example.com/2', 'Two');

        INSERT INTO business_facets (source_url, facet_type, slug, name)
        VALUES
            ('https://example.com/1', 'category', 'restaurants', 'Restaurants'),
            ('https://example.com/2', 'category', 'restaurants', 'Restaurants'),
            ('https://example.com/1', 'city', 'cairo', 'Cairo'),
            ('https://example.com/2', 'city', 'giza', 'Giza'),
            ('https://example.com/1', 'area', 'maadi', 'Maadi');
        """
    )
    conn.close()

    categories = load_facet_options(db_path, "category")
    cities = load_facet_options(db_path, "city")
    cairo_areas = load_facet_options(db_path, "area", parent_slug="cairo")
    giza_areas = load_facet_options(db_path, "area", parent_slug="giza")

    assert categories == [{"slug": "restaurants", "name": "Restaurants", "count": 2}]
    assert cities == [
        {"slug": "cairo", "name": "Cairo", "count": 1},
        {"slug": "giza", "name": "Giza", "count": 1},
    ]
    assert cairo_areas == [{"slug": "maadi", "name": "Maadi", "count": 1}]
    assert giza_areas == []


def test_load_facet_options_returns_districts_for_selected_area(tmp_path: Path) -> None:
    from app.data_access import load_businesses, load_facet_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO locations (slug, name, type, parent_slug)
        VALUES
            ('cairo', 'Cairo', 'city', ''),
            ('maadi', 'Maadi', 'area', 'cairo'),
            ('new-maadi', 'New Maadi', 'district', 'maadi');

        INSERT INTO businesses (source_url, business_name)
        VALUES ('https://example.com/1', 'New Maadi Shop');

        INSERT INTO business_facets (source_url, facet_type, slug, name)
        VALUES
            ('https://example.com/1', 'city', 'cairo', 'Cairo'),
            ('https://example.com/1', 'area', 'maadi', 'Maadi'),
            ('https://example.com/1', 'district', 'new-maadi', 'New Maadi');
        """
    )
    conn.close()

    districts = load_facet_options(db_path, "district", parent_slug="maadi")
    rows = load_businesses(
        db_path,
        {"city": ["cairo"], "area": ["maadi"], "district": ["new-maadi"]},
    )

    assert districts == [{"slug": "new-maadi", "name": "New Maadi", "count": 1}]
    assert [row["business_name"] for row in rows] == ["New Maadi Shop"]


def test_load_filter_options_returns_saved_business_facets(tmp_path: Path) -> None:
    from app.data_access import load_filter_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO categories (slug, name, result_count)
        VALUES
            ('restaurants', 'Restaurants', 100),
            ('atms', 'ATMs', 11);

        INSERT INTO brands (slug, name, result_count)
        VALUES
            ('carrier', 'Carrier', 20),
            ('sony', 'Sony', 10);

        INSERT INTO keywords (slug, name)
        VALUES
            ('air-condition', 'Air Condition'),
            ('compressor', 'Compressor');

        INSERT INTO locations (slug, name, type, parent_slug)
        VALUES
            ('cairo', 'Cairo', 'city', '');

        INSERT INTO businesses (source_url, business_name)
        VALUES
            ('https://example.com/1', 'One'),
            ('https://example.com/2', 'Two');

        INSERT INTO business_facets (source_url, facet_type, slug, name)
        VALUES
            ('https://example.com/1', 'category', 'restaurants', 'Restaurants'),
            ('https://example.com/2', 'category', 'restaurants', 'Restaurants'),
            ('https://example.com/1', 'brand', 'carrier', 'Carrier');
        """
    )
    conn.close()

    options = load_filter_options(db_path)

    assert options["categories"] == [{"slug": "restaurants", "name": "Restaurants", "count": 2}]
    assert options["brands"] == [{"slug": "carrier", "name": "Carrier", "count": 1}]
    assert options["keywords"] == []
    assert options["cities"] == []


def test_load_crawl_target_options_returns_scraped_taxonomy_items(tmp_path: Path) -> None:
    from app.data_access import load_crawl_target_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO categories (slug, name, result_count)
        VALUES
            ('restaurants', 'Restaurants', 100),
            ('atms', 'ATMs', 11);

        INSERT INTO brands (slug, name, result_count)
        VALUES
            ('carrier', 'Carrier', 20),
            ('sony', 'Sony', 10);

        INSERT INTO keywords (slug, name)
        VALUES
            ('air-condition', 'Air Condition'),
            ('compressor', 'Compressor');

        INSERT INTO locations (slug, name, type, parent_slug)
        VALUES
            ('cairo', 'Cairo', 'city', '');
        """
    )
    conn.close()

    options = load_crawl_target_options(db_path)

    assert [row["slug"] for row in options["categories"]][:2] == ["atms", "restaurants"]
    assert {row["slug"] for row in options["categories"]} >= {"مصنع", "مستورد", "موزع"}
    assert [row["slug"] for row in options["brands"]] == ["carrier", "sony"]
    assert [row["slug"] for row in options["keywords"]][:2] == ["air-condition", "compressor"]
    assert {row["slug"] for row in options["keywords"]} >= {"مصنع", "مستورد", "موزع"}
    assert options["cities"] == [{"slug": "cairo", "name": "Cairo"}]


def test_ensure_seed_taxonomy_populates_empty_deployment_db(tmp_path: Path) -> None:
    from app.data_access import ensure_seed_taxonomy, load_crawl_target_options
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        """{
          "categories": [{"slug": "restaurants", "name": "Restaurants"}],
          "locations": [{"slug": "cairo", "name": "Cairo", "type": "city"}],
          "brands": [],
          "keywords": []
        }""",
        encoding="utf-8",
    )
    conn = get_connection(db_path)
    init_db(conn)
    conn.close()

    assert ensure_seed_taxonomy(db_path, seed_path) is True

    options = load_crawl_target_options(db_path)
    assert options["categories"][0]["slug"] == "restaurants"
    assert options["cities"] == [{"slug": "cairo", "name": "Cairo"}]


def test_ensure_seed_taxonomy_skips_populated_db(tmp_path: Path) -> None:
    from app.data_access import ensure_seed_taxonomy
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        """{
          "categories": [{"slug": "hotels", "name": "Hotels"}],
          "locations": [{"slug": "giza", "name": "Giza", "type": "city"}]
        }""",
        encoding="utf-8",
    )
    conn = get_connection(db_path)
    init_db(conn)
    conn.execute("INSERT INTO categories (slug, name) VALUES ('restaurants', 'Restaurants')")
    conn.execute("INSERT INTO locations (slug, name, type) VALUES ('cairo', 'Cairo', 'city')")
    conn.commit()
    conn.close()

    assert ensure_seed_taxonomy(db_path, seed_path) is False


def test_ensure_seed_taxonomy_populates_empty_postgres_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app import data_access

    class FakeResult:
        def __init__(self, value: int = 0) -> None:
            self.value = value

        def fetchone(self) -> dict[str, int]:
            return {"value": self.value}

    class FakePostgresConnection:
        def __init__(self) -> None:
            self.statements: list[tuple[str, tuple[object, ...]]] = []
            self.committed = False
            self.closed = False

        def execute(
            self,
            query: str,
            params: tuple[object, ...] = (),
        ) -> FakeResult:
            self.statements.append((query, params))
            return FakeResult(0)

        def commit(self) -> None:
            self.committed = True

        def close(self) -> None:
            self.closed = True

    conn = FakePostgresConnection()
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        """{
          "categories": [{"slug": "restaurants", "name": "Restaurants"}],
          "locations": [{"slug": "cairo", "name": "Cairo", "type": "city"}],
          "brands": [{"slug": "carrier", "name": "Carrier"}],
          "keywords": [{"slug": "air-condition", "name": "Air Condition"}]
        }""",
        encoding="utf-8",
    )
    monkeypatch.setattr(data_access, "_open", lambda _db_path: (conn, "postgres"))

    assert data_access.ensure_seed_taxonomy("postgresql://example", seed_path) is True

    insert_statements = [
        statement for statement, _params in conn.statements if "INSERT INTO" in statement
    ]
    assert len(insert_statements) == 4
    assert all("%s" in statement for statement in insert_statements)
    assert conn.committed is True
    assert conn.closed is True


def test_streamlit_full_crawl_uses_http_tiers_only(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    import os

    from streamlit.testing.v1 import AppTest

    db_path = tmp_path / "test.sqlite"
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        """{
          "categories": [{"slug": "restaurants", "name": "Restaurants"}],
          "locations": [{"slug": "cairo", "name": "Cairo", "type": "city"}],
          "brands": [],
          "keywords": []
        }""",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_run_mass_crawl(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("TAXONOMY_SEED_PATH", str(seed_path))
    monkeypatch.setattr("scraper.mass_crawl.run_mass_crawl", fake_run_mass_crawl)

    at = AppTest.from_file("app/streamlit_app.py")
    at.run(timeout=60)
    button = next(item for item in at.button if item.label == "Run Full Dataset Crawl")
    button.click().run(timeout=60)

    assert captured["headless"] is False
    assert captured["target_types"] == ["category", "brand", "keyword"]
    assert captured["city_slugs"] is None
    os.environ.pop("DB_PATH", None)
    os.environ.pop("TAXONOMY_SEED_PATH", None)


def test_streamlit_cloud_entrypoint_reruns_real_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from streamlit.testing.v1 import AppTest

    db_path = tmp_path / "test.sqlite"
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        """{
          "categories": [{"slug": "restaurants", "name": "Restaurants"}],
          "locations": [{"slug": "cairo", "name": "Cairo", "type": "city"}],
          "brands": [],
          "keywords": []
        }""",
        encoding="utf-8",
    )
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("TAXONOMY_SEED_PATH", str(seed_path))

    at = AppTest.from_file("streamlit_app.py")
    at.run(timeout=60)
    assert [title.value for title in at.title] == [
        "YellowPages Egypt - Business Contacts",
        "Filters",
    ]

    next(button for button in at.button if button.label == "Refresh Log").click().run(timeout=60)

    assert [title.value for title in at.title] == [
        "YellowPages Egypt - Business Contacts",
        "Filters",
    ]
    assert not at.exception


def test_load_crawl_progress_summarizes_queue_and_saved_data(tmp_path: Path) -> None:
    from app.data_access import load_crawl_progress
    from scraper.db import get_connection, init_db

    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)
    init_db(conn)
    conn.executescript(
        """
        INSERT INTO businesses (source_url, business_name)
        VALUES
            ('https://example.com/1', 'One'),
            ('https://example.com/2', 'Two');

        INSERT INTO business_facets (source_url, facet_type, slug, name)
        VALUES
            ('https://example.com/1', 'brand', 'carrier', 'Carrier'),
            ('https://example.com/1', 'city', 'cairo', 'Cairo'),
            ('https://example.com/2', 'brand', 'carrier', 'Carrier');

        INSERT INTO scrape_jobs (
            target_type, target_slug, category_slug, city_slug,
            status, pages_scraped, rows_written
        )
        VALUES
            ('category', 'restaurants', 'restaurants', 'cairo', 'done', 4, 2),
            ('brand', 'carrier', 'carrier', 'cairo', 'running', 3, 0),
            ('keyword', 'Advertising', 'Advertising', 'cairo', 'pending', 0, 0),
            ('category', 'hospitals', 'hospitals', 'giza', 'failed', 1, 0);
        """
    )
    conn.close()

    progress = load_crawl_progress(db_path)

    assert progress["total_jobs"] == 4
    assert progress["done_jobs"] == 1
    assert progress["running_jobs"] == 1
    assert progress["pending_jobs"] == 1
    assert progress["failed_jobs"] == 1
    assert progress["pages_checked"] == 8
    assert progress["rows_written"] == 2
    assert progress["business_count"] == 2
    assert progress["recent_business_count"] == 0
    assert progress["current_jobs"][0]["target_slug"] == "carrier"
    assert progress["current_jobs"][0]["matching_saved_businesses"] == 1
