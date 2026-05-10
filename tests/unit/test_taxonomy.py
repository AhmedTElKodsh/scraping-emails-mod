"""Unit tests for taxonomy.py - parse functions with HTML fixtures."""




def test_parse_categories_from_fixture() -> None:
    from scraper.taxonomy import parse_categories

    html = """
    <div>
        <a class="category-item" href="/en/category/restaurants">Restaurants (42)</a>
        <a class="category-item" href="/en/category/hotels">Hotels</a>
    </div>
    """
    cats = parse_categories(html)
    assert len(cats) == 2
    assert any(c["slug"] == "restaurants" for c in cats)
    assert any(c["name"] == "Hotels" for c in cats)
    assert cats[0]["result_count"] == 42
    assert cats[0]["href"] == "/en/category/restaurants"


def test_parse_brands_from_related_index() -> None:
    from scraper.taxonomy import parse_brands

    html = """
    <a href="/en/brand/samsung">Samsung (1914)</a>
    <a href="/en/brand/ray-ban">Ray Ban (575)</a>
    <a href="/en/category/air-conditioning">Air Conditioning (4239)</a>
    """

    brands = parse_brands(html)
    assert brands == [
        {"slug": "samsung", "name": "Samsung", "result_count": 1914, "href": "/en/brand/samsung"},
        {"slug": "ray-ban", "name": "Ray Ban", "result_count": 575, "href": "/en/brand/ray-ban"},
    ]


def test_parse_keywords_from_keywords_index() -> None:
    from scraper.taxonomy import parse_keywords

    html = """
    <a href="/en/keyword/Marble-&-Granite-Supply">Marble & Granite Supply</a>
    <a href="/en/keyword/Air-Condition">Air Condition</a>
    <a href="/en/related-categories">Browse by Category</a>
    """

    keywords = parse_keywords(html)
    assert keywords == [
        {
            "slug": "Marble-&-Granite-Supply",
            "name": "Marble & Granite Supply",
            "href": "/en/keyword/Marble-&-Granite-Supply",
        },
        {"slug": "Air-Condition", "name": "Air Condition", "href": "/en/keyword/Air-Condition"},
    ]


def test_parse_last_page_finds_highest_pager() -> None:
    from scraper.taxonomy import parse_last_page

    html = """
    <a href="/en/related-brands/p8">8</a>
    <a href="/en/related-brands/p250">Last</a>
    """

    assert parse_last_page(html, "/en/related-brands") == 250


def test_parse_locations_hierarchy_from_fixture() -> None:
    from scraper.taxonomy import parse_locations

    html = """
    <div>
        <div class="location-item" data-slug="cairo" data-type="city">Cairo</div>
        <div class="location-item" data-slug="maadi" data-type="area"
             data-parent="cairo">Maadi</div>
        <div class="location-item" data-slug="new-maadi" data-type="district"
             data-parent="maadi">New Maadi</div>
    </div>
    """
    locs = parse_locations(html)
    assert len(locs) == 3
    cities = [loc for loc in locs if loc["type"] == "city"]
    areas = [loc for loc in locs if loc["type"] == "area"]
    districts = [loc for loc in locs if loc["type"] == "district"]
    assert len(cities) == 1
    assert len(areas) == 1
    assert len(districts) == 1
    assert areas[0]["parent_slug"] == "cairo"
    assert districts[0]["parent_slug"] == "maadi"


def test_parse_locations_from_filter_inputs_with_parent_external_ids() -> None:
    from scraper.taxonomy import parse_locations

    html = """
    <form id="myFiltersForm">
      <input value="13" data-data="CAIRO" class="locations_filter cities_filter"
             id="filled-in-box-0-cit" name="locations_filter" type="checkbox">
      <label for="filled-in-box-0-cit">Cairo(1441)</label>
      <input value="2" data-data="15th OF MAY CITY" data-cityid="13"
             class="locations_filter areas_filter" id="filled-in-box-0-area"
             name="locations_filter" type="checkbox">
      <label for="filled-in-box-0-area">15th of may city(12)</label>
      <input value="7" data-data="INDUSTRIAL ZONE" data-areaid="2"
             class="locations_filter district_filter" id="filled-in-box-0-dist"
             name="locations_filter" type="checkbox">
      <label for="filled-in-box-0-dist">Industrial Zone(3)</label>
    </form>
    """

    locations = parse_locations(html)
    assert locations == [
        {
            "slug": "cairo",
            "name": "Cairo",
            "type": "city",
            "parent_slug": "",
            "external_id": "13",
            "parent_external_id": "",
            "result_count": 1441,
        },
        {
            "slug": "15th-of-may-city",
            "name": "15th Of May City",
            "type": "area",
            "parent_slug": "",
            "external_id": "2",
            "parent_external_id": "13",
            "result_count": 12,
        },
        {
            "slug": "industrial-zone",
            "name": "Industrial Zone",
            "type": "district",
            "parent_slug": "",
            "external_id": "7",
            "parent_external_id": "2",
            "result_count": 3,
        },
    ]


def test_empty_page_returns_empty_list_not_raises() -> None:
    from scraper.taxonomy import parse_categories, parse_locations

    html = "<html><body>No categories here</body></html>"
    assert parse_categories(html) == []
    assert parse_locations(html) == []


def test_pagination_followed() -> None:
    """Stub test - pagination logic not yet implemented in taxonomy.py."""
    from scraper.taxonomy import parse_categories

    html = """
    <div>
        <a class="category-item" href="/category/cat1">Cat 1</a>
        <a class="pagination-next" href="/categories?page=2">Next</a>
    </div>
    """
    cats = parse_categories(html)
    assert len(cats) == 1  # Only one category parsed from this page
