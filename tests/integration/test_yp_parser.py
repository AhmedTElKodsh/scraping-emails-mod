from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_listing_urls_extracts_two_links() -> None:
    from scraper.sites.yellowpages_eg import parse_listing_urls

    html = (FIXTURES / "yp_list_page.html").read_text(encoding="utf-8")
    urls = parse_listing_urls(html)
    assert len(urls) == 2
    assert all("yellowpages.com.eg" in u for u in urls)


def test_parse_next_page_url_returns_page2() -> None:
    from scraper.sites.yellowpages_eg import parse_next_page_url

    html = (FIXTURES / "yp_list_page.html").read_text(encoding="utf-8")
    next_url = parse_next_page_url(html)
    assert next_url is not None
    assert "page=2" in next_url


def test_parse_next_page_url_none_on_empty() -> None:
    from scraper.sites.yellowpages_eg import parse_next_page_url

    html = (FIXTURES / "yp_empty_page.html").read_text(encoding="utf-8")
    assert parse_next_page_url(html) is None


def test_parse_detail_extracts_name() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://www.yellowpages.com.eg/listing/cairo-grill-1")
    assert result.business_name == "Cairo Grill"


def test_parse_detail_extracts_email_from_mailto() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://www.yellowpages.com.eg/listing/cairo-grill-1")
    assert "info@cairogrill.com" in result.emails


def test_parse_detail_extracts_cfemail() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://www.yellowpages.com.eg/listing/cairo-grill-1")
    assert "test@test.com" in result.emails


def test_parse_detail_extracts_phone() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://www.yellowpages.com.eg/listing/cairo-grill-1")
    assert result.phone == "+20221234567"


def test_parse_detail_extracts_website() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    html = (FIXTURES / "yp_listing_detail.html").read_text(encoding="utf-8")
    result = parse_detail(html, "https://www.yellowpages.com.eg/listing/cairo-grill-1")
    assert "cairogrill.com" in result.website


def test_parse_detail_missing_field_no_crash() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    sparse_html = "<html><body><h1 class='business-name'>Sparse Biz</h1></body></html>"
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
