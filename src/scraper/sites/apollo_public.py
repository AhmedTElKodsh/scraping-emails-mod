"""Apollo.io public-only POC scraper (Tier 3 mandatory, isolated, low-yield expected)."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from selectolax.parser import HTMLParser

from scraper.email_extract import extract_emails
from scraper.models import ScrapeResult
from scraper.sites._util import _first_attr, _first_text

if TYPE_CHECKING:
    from scraper.csv_writer import CSVWriter
    from scraper.pipeline import Pipeline

log = structlog.get_logger()

BASE_URL = "https://app.apollo.io"
ROBOTS_DISALLOW = True  # Apollo robots.txt disallows scraping — documented decision

_NAME_SELECTORS = ["h1.company-name", "h1.org-name", "h1"]
_WEBSITE_SELECTORS = ["a.company-website", "a.website-link", ".contact-info a[href^='https']"]
_INDUSTRY_SELECTORS = [".industry", ".company-industry"]
_LOCATION_SELECTORS = [".location", ".company-location"]


def parse_company(html: str, url: str) -> ScrapeResult:
    tree = HTMLParser(html)
    seen: set[str] = set()
    emails = extract_emails(html, seen)

    return ScrapeResult(
        url=url,
        business_name=_first_text(tree, _NAME_SELECTORS),
        category=_first_text(tree, _INDUSTRY_SELECTORS),
        governorate=_first_text(tree, _LOCATION_SELECTORS),
        emails=emails,
        website=_first_attr(tree, _WEBSITE_SELECTORS, "href"),
        raw_html_hash=hashlib.md5(html.encode()).hexdigest(),
        scraped_at=datetime.now(UTC).isoformat(),
    )


def scrape_company(slug: str, pipeline: Pipeline, csv_writer: CSVWriter) -> int:
    from scraper.pipeline import BlockedError

    if ROBOTS_DISALLOW:
        log.warning(
            "apollo_robots_disallow",
            msg="Apollo robots.txt disallows scraping. Proceeding as documented POC decision.",
        )

    url = f"{BASE_URL}/companies/{slug}"
    try:
        resp = pipeline.fetch(url)
    except BlockedError:
        log.error("apollo_blocked", slug=slug)
        return 0

    if not resp.text:
        log.warning("apollo_empty_response", slug=slug, url=url)
        return 0

    result = parse_company(resp.text, url)
    result.source_tier = resp.tier
    log.info("apollo_scraped", slug=slug, emails=result.emails, name=result.business_name)
    return csv_writer.write(result)
