from pathlib import Path
from unittest.mock import MagicMock

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_company_extracts_name() -> None:
    from scraper.sites.apollo_public import parse_company

    html = (FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8")
    result = parse_company(html, "https://www.apollo.io/companies/acme-corp")
    assert result.business_name == "Acme Corp"


def test_parse_company_extracts_category() -> None:
    from scraper.sites.apollo_public import parse_company

    html = (FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8")
    result = parse_company(html, "https://www.apollo.io/companies/acme-corp")
    assert result.category == "Technology"


def test_parse_company_extracts_governorate() -> None:
    from scraper.sites.apollo_public import parse_company

    html = (FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8")
    result = parse_company(html, "https://www.apollo.io/companies/acme-corp")
    assert result.governorate == "Cairo, Egypt"


def test_parse_company_extracts_website() -> None:
    from scraper.sites.apollo_public import parse_company

    html = (FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8")
    result = parse_company(html, "https://www.apollo.io/companies/acme-corp")
    assert result.website == "https://www.acme.com"


def test_parse_company_emails_empty_on_public_page() -> None:
    from scraper.sites.apollo_public import parse_company

    html = (FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8")
    result = parse_company(html, "https://www.apollo.io/companies/acme-corp")
    assert result.emails == []


def test_parse_company_populates_metadata() -> None:
    from scraper.sites.apollo_public import parse_company

    html = (FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8")
    result = parse_company(html, "https://www.apollo.io/companies/acme-corp")
    assert result.scraped_at != ""
    assert result.raw_html_hash != ""


def test_parse_company_no_crash_on_sparse_html() -> None:
    from scraper.sites.apollo_public import parse_company

    result = parse_company("<html><body></body></html>", "https://www.apollo.io/companies/x")
    assert result.business_name == ""
    assert result.emails == []


def test_scrape_company_sets_source_tier_from_response() -> None:
    from scraper.http_client import Response
    from scraper.sites.apollo_public import scrape_company

    mock_pipeline = MagicMock()
    mock_pipeline.fetch.return_value = Response(
        status_code=200,
        text=(FIXTURES / "apollo" / "company_page.html").read_text(encoding="utf-8"),
        headers={},
        tier=3,
    )
    mock_csv = MagicMock()
    mock_csv.write.return_value = 0

    scrape_company("acme-corp", mock_pipeline, mock_csv)

    written_result = mock_csv.write.call_args[0][0]
    assert written_result.source_tier == 3


def test_scrape_company_returns_zero_on_blocked() -> None:
    from scraper.pipeline import BlockedError
    from scraper.sites.apollo_public import scrape_company

    mock_pipeline = MagicMock()
    mock_pipeline.fetch.side_effect = BlockedError("blocked")
    mock_csv = MagicMock()

    result = scrape_company("acme-corp", mock_pipeline, mock_csv)
    assert result == 0
    mock_csv.write.assert_not_called()
