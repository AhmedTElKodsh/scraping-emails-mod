"""Integration tests for full scraper flow with mocked HTTP responses."""
from pathlib import Path

import pytest


@pytest.mark.integration
def test_yp_scraper_full_flow_with_mock_responses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test complete YP scraping flow with mocked HTTP responses."""
    from scraper.csv_writer import CSVWriter
    from scraper.http_client import Response, Tier1Client
    from scraper.pipeline import Pipeline
    from scraper.rate_limiter import RateLimiter
    from scraper.sites.yellowpages_eg import scrape_category

    # Mock HTML responses
    list_page_html = """
    <html>
        <a href="/en/profile/test-biz/710101?position=1">Test Business</a>
    </html>
    """

    detail_page_html = """
    <html>
        <h1 class="companyName">Test Business</h1>
        <div class="companyName-category">Restaurants</div>
        <div class="company-governorate">Cairo</div>
        <a href="tel:+20221234567">+20221234567</a>
        <a href="mailto:info@testbiz.com" class="companyName-email">info@testbiz.com</a>
        <a href="https://testbiz.com" class="btn website">testbiz.com</a>
        <div class="company-address"><span>123 Test St</span></div>
    </html>
    """

    phones_json = '[["0221234567"],[],[]]'
    call_count = [0]

    class MockTier1(Tier1Client):
        def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
            call_count[0] += 1
            if "/en/getPhones/" in url:
                return Response(200, phones_json, {}, 1)
            elif "/en/profile/" in url:
                return Response(200, detail_page_html, {}, 1)
            else:
                return Response(200, list_page_html, {}, 1)

    csv_path = tmp_path / "test_output.csv"
    csv_writer = CSVWriter(csv_path)
    pipeline = Pipeline(tiers=[MockTier1()])
    rate_limiter = RateLimiter(delay_fn=lambda: 0.0)

    total = scrape_category(
        "restaurants",
        "cairo",
        pipeline,
        csv_writer,
        rate_limiter,
        proxy_pool=None,
        max_pages=1,
        consecutive_empty_halt=5,
    )

    assert total == 1
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    assert "Test Business" in content
    assert "info@testbiz.com" in content
    assert "0221234567" in content


@pytest.mark.integration
def test_apollo_scraper_full_flow_with_mock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test complete Apollo scraping flow with mocked HTTP responses."""
    from scraper.csv_writer import CSVWriter
    from scraper.http_client import BaseClient, Response
    from scraper.pipeline import Pipeline
    from scraper.sites.apollo_public import scrape_company

    apollo_html = """
    <html>
        <h1 class="company-name">Acme Corp</h1>
        <span class="industry">Technology</span>
        <span class="location">Cairo, Egypt</span>
        <a href="https://www.acme.com" class="company-website">acme.com</a>
        <p>Contact: contact@acme.com</p>
    </html>
    """

    class MockTier3(BaseClient):
        tier = 3

        def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
            return Response(200, apollo_html, {}, 3)

    csv_path = tmp_path / "apollo_output.csv"
    csv_writer = CSVWriter(csv_path)
    pipeline = Pipeline(tiers=[MockTier3()])

    total = scrape_company("acme-corp", pipeline, csv_writer)

    assert total == 1
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    assert "Acme Corp" in content
    assert "contact@acme.com" in content


@pytest.mark.integration
def test_proxy_pool_integration_with_failure_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test proxy pool sticky sessions and failure tracking in scraper flow."""
    from scraper.proxy_pool import ProxyPool

    def always_alive(url: str) -> bool:
        return True

    proxies = ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
    pool = ProxyPool(proxies, checker=always_alive, sticky_count=3, max_failures=2)

    # Get proxy 3 times (sticky session)
    first = pool.get()
    second = pool.get()
    third = pool.get()
    assert first == second == third

    # Record failures
    if first:
        pool.record_failure(first)
        pool.record_failure(first)

    # Should rotate to different proxy after failures
    fourth = pool.get()
    assert fourth != first

    # Verify alive count decreased
    assert pool.alive_count() == 2


@pytest.mark.integration
def test_csv_resume_across_runs(tmp_path: Path) -> None:
    """Test CSV writer resume functionality across multiple runs."""
    from scraper.csv_writer import CSVWriter
    from scraper.models import ScrapeResult

    csv_path = tmp_path / "resume_test.csv"

    # First run
    writer1 = CSVWriter(csv_path)
    result1 = ScrapeResult(
        url="https://example.com/1",
        business_name="Business 1",
        emails=["first@example.com"],
    )
    written1 = writer1.write(result1)
    assert written1 == 1

    # Second run - same email should be skipped
    writer2 = CSVWriter(csv_path)
    result2 = ScrapeResult(
        url="https://example.com/2",
        business_name="Business 2",
        emails=["first@example.com", "second@example.com"],
    )
    written2 = writer2.write(result2)
    assert written2 == 1  # Only second@example.com written

    # Verify total rows
    content = csv_path.read_text(encoding="utf-8")
    lines = [line for line in content.splitlines() if line.strip()]
    assert len(lines) == 3  # header + 2 data rows
