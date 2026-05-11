from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_listing_urls_extracts_profile_links() -> None:
    from scraper.sites.yellowpages_eg import parse_listing_urls

    html = (FIXTURES / "yp_list_page.html").read_text(encoding="utf-8")
    urls = parse_listing_urls(html)
    assert len(urls) == 2
    assert all("/en/profile/" in u for u in urls)
    assert all(u.startswith("https://") for u in urls)


def test_build_category_url_with_governorate() -> None:
    from scraper.sites.yellowpages_eg import build_category_url

    url = build_category_url("restaurants", "cairo", page=2)
    assert url == "https://yellowpages.com.eg/en/category/restaurants/p2?city=cairo"


def test_build_category_url_without_governorate() -> None:
    from scraper.sites.yellowpages_eg import build_category_url

    url = build_category_url("restaurants", None, page=1)
    assert url == "https://yellowpages.com.eg/en/category/restaurants/p1"


def test_build_target_url_for_category_brand_and_keyword() -> None:
    from scraper.sites.yellowpages_eg import build_target_url

    assert build_target_url("category", "air-conditioning", page=3) == (
        "https://yellowpages.com.eg/en/category/air-conditioning/p3"
    )
    assert build_target_url("brand", "samsung", page=2) == (
        "https://yellowpages.com.eg/en/brand/samsung/p2"
    )
    assert build_target_url("keyword", "Air-Condition", page=1) == (
        "https://yellowpages.com.eg/en/keyword/Air-Condition"
    )


def test_parse_listing_cards_extracts_profile_url_and_visible_facets() -> None:
    from scraper.sites.yellowpages_eg import parse_listing_cards

    html = """
    <div class="result-item">
      <a href="//yellowpages.com.eg/en/profile/cool-air/123?position=1">Cool Air</a>
      <a href="/en/category/air-conditioning">Air Conditioning</a>
      <a href="/en/keyword/central-ac-duct-works">Central AC Duct Works</a>
      <a href="/en/brand/carrier">Carrier</a>
    </div>
    """

    cards = parse_listing_cards(html)
    assert len(cards) == 1
    assert cards[0].url == "https://yellowpages.com.eg/en/profile/cool-air/123"
    assert {(facet.type, facet.slug, facet.name) for facet in cards[0].facets} == {
        ("category", "air-conditioning", "Air Conditioning"),
        ("keyword", "central-ac-duct-works", "Central AC Duct Works"),
        ("brand", "carrier", "Carrier"),
    }


def test_parse_detail_extracts_name() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    assert result.business_name == "Cairo Grill"


def test_parse_detail_extracts_email_from_mailto() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    assert "info@cairogrill.com" in result.emails


def test_parse_detail_extracts_cfemail() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    assert "test@test.com" in result.emails


def test_parse_detail_phone_empty_for_ajax_endpoint() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    # Phones come from /en/getPhones/{id}/false AJAX, not static HTML
    assert result.phone == ""


def test_parse_detail_extracts_facebook_url() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    assert "facebook.com/cairogrill" in result.facebook_url


def test_parse_detail_extracts_website() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    assert "cairogrill.com" in result.website


def test_parse_detail_extracts_address() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://yellowpages.com.eg/en/profile/cairo-grill/710101")
    assert "Tahrir" in result.address


def test_parse_detail_missing_field_no_crash() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    sparse_html = "<html><body><h1>Sparse Biz</h1></body></html>"
    result = parse_detail(sparse_html, "https://example.com/sparse")
    assert result.business_name == "Sparse Biz"
    assert result.phone == ""
    assert result.emails == []


def test_is_empty_page_true_for_no_results() -> None:
    from scraper.sites.yellowpages_eg import is_empty_page

    html = (FIXTURES / "yp_empty_page.html").read_text(encoding="utf-8")
    assert is_empty_page(html) is True


def test_is_empty_page_false_for_results() -> None:
    from scraper.sites.yellowpages_eg import is_empty_page

    html = (FIXTURES / "yp_list_page.html").read_text(encoding="utf-8")
    assert is_empty_page(html) is False


def test_scrape_target_reports_progress_for_empty_pages() -> None:
    from scraper.http_client import Response
    from scraper.sites.yellowpages_eg import scrape_target

    class EmptyPipeline:
        def fetch(self, url, proxy=None, referer=None):  # type: ignore[no-untyped-def]
            return Response(200, "<html><body>No listings</body></html>", {}, 1)

    class NoopWriter:
        def write(self, result):  # type: ignore[no-untyped-def]
            return 1

    class NoopRateLimiter:
        def wait(self) -> None:
            pass

    progress: list[tuple[int, int]] = []

    rows = scrape_target(
        target_type="category",
        slug="empty",
        city_slug=None,
        pipeline=EmptyPipeline(),  # type: ignore[arg-type]
        csv_writer=NoopWriter(),  # type: ignore[arg-type]
        rate_limiter=NoopRateLimiter(),  # type: ignore[arg-type]
        max_pages=2,
        consecutive_empty_halt=2,
        progress_callback=lambda pages, written: progress.append((pages, written)),
    )

    assert rows == 0
    assert progress == [(1, 0), (2, 0)]
