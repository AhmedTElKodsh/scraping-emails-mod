"""Apollo.io public-only POC scraper (Tier 3 mandatory, isolated, low-yield expected)."""
from __future__ import annotations

import structlog
from selectolax.parser import HTMLParser

from scraper.email_extract import extract_emails
from scraper.models import ScrapeResult

log = structlog.get_logger()

BASE_URL = "https://app.apollo.io"
ROBOTS_DISALLOW = True  # Apollo robots.txt disallows scraping — documented decision

_NAME_SELECTORS = ["h1.company-name", "h1.org-name", "h1"]
_WEBSITE_SELECTORS = ["a.company-website", "a[href^='https']"]
_INDUSTRY_SELECTORS = [".industry", ".company-industry"]
_LOCATION_SELECTORS = [".location", ".company-location"]


def parse_company(html: str, url: str) -> ScrapeResult:
    tree = HTMLParser(html)
    seen: set[str] = set()
    emails = extract_emails(html, seen)

    name = ""
    for sel in _NAME_SELECTORS:
        node = tree.css_first(sel)
        if node and node.text(strip=True):
            name = node.text(strip=True)
            break

    website = ""
    for sel in _WEBSITE_SELECTORS:
        node = tree.css_first(sel)
        if node and node.attrs.get("href", ""):
            website = str(node.attrs["href"])
            break

    category = ""
    for sel in _INDUSTRY_SELECTORS:
        node = tree.css_first(sel)
        if node and node.text(strip=True):
            category = node.text(strip=True)
            break

    governorate = ""
    for sel in _LOCATION_SELECTORS:
        node = tree.css_first(sel)
        if node and node.text(strip=True):
            governorate = node.text(strip=True)
            break

    return ScrapeResult(
        url=url,
        business_name=name,
        category=category,
        governorate=governorate,
        emails=emails,
        website=website,
        source_tier=3,
    )


def scrape_company(slug: str, pipeline: object, csv_writer: object) -> int:
    from scraper.csv_writer import CSVWriter
    from scraper.pipeline import BlockedError, Pipeline

    assert isinstance(pipeline, Pipeline)
    assert isinstance(csv_writer, CSVWriter)

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

    result = parse_company(resp.text, url)
    log.info("apollo_scraped", slug=slug, emails=result.emails, name=result.business_name)
    return csv_writer.write(result)
