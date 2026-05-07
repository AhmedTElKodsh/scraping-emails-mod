import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from selectolax.parser import HTMLParser

from scraper.email_extract import extract_emails
from scraper.models import ScrapeResult

if TYPE_CHECKING:
    from scraper.csv_writer import CSVWriter
    from scraper.pipeline import Pipeline
    from scraper.rate_limiter import RateLimiter

BASE_URL = "https://www.yellowpages.com.eg"
_LISTING_URL_SELECTORS = [".listing-item a.listing-link", ".business-listing a.detail-link"]
_NEXT_PAGE_SELECTORS = ["a.next-page", "a[rel='next']", ".pagination a.next"]
_NAME_SELECTORS = ["h1.business-name", "h1.listing-title", "h1", ".business-name"]
_PHONE_SELECTORS = ["a.phone-link", "a[href^='tel:']", ".phone-number", ".phone"]
_WEBSITE_SELECTORS = ["a.website-link", "a[rel='nofollow'][href^='http']", ".website a"]
_ADDRESS_SELECTORS = [".address", ".business-address", "[itemprop='streetAddress']"]
_CATEGORY_SELECTORS = [".category-tag", ".category", "[itemprop='businessType']"]
_GOVERNORATE_SELECTORS = [".governorate", ".location", "[itemprop='addressRegion']"]
_EMPTY_SELECTORS = [".no-results", ".empty-results", "p.no-listings"]


def _first_text(tree: HTMLParser, selectors: list[str]) -> str:
    for sel in selectors:
        node = tree.css_first(sel)
        if node and node.text(strip=True):
            return node.text(strip=True)
    return ""


def _first_attr(tree: HTMLParser, selectors: list[str], attr: str) -> str:
    for sel in selectors:
        node = tree.css_first(sel)
        if node and node.attrs.get(attr):
            return str(node.attrs[attr])
    return ""


def parse_listing_urls(html: str, base_url: str = BASE_URL) -> list[str]:
    tree = HTMLParser(html)
    urls: list[str] = []
    for sel in _LISTING_URL_SELECTORS:
        for node in tree.css(sel):
            href = node.attrs.get("href", "") or ""
            if href and not href.startswith("http"):
                href = base_url + href
            if href:
                urls.append(href)
        if urls:
            break
    return urls


def parse_next_page_url(html: str, base_url: str = BASE_URL) -> str | None:
    tree = HTMLParser(html)
    for sel in _NEXT_PAGE_SELECTORS:
        node = tree.css_first(sel)
        if node:
            href = node.attrs.get("href", "") or ""
            if not href:
                continue
            if not href.startswith("http"):
                href = base_url + href
            return href
    return None


def is_empty_page(html: str) -> bool:
    tree = HTMLParser(html)
    for sel in _EMPTY_SELECTORS:
        if tree.css_first(sel):
            return True
    listing_nodes = tree.css(".listing-item, .business-listing")
    return len(listing_nodes) == 0


def parse_detail(html: str, url: str) -> ScrapeResult:
    tree = HTMLParser(html)
    seen: set[str] = set()
    emails = extract_emails(html, seen)

    phone_node = tree.css_first("a[href^='tel:']")
    phone = ""
    if phone_node:
        href = phone_node.attrs.get("href", "") or ""
        phone = href.replace("tel:", "") or phone_node.text(strip=True)
    if not phone:
        phone = _first_text(tree, _PHONE_SELECTORS)

    website = _first_attr(tree, _WEBSITE_SELECTORS, "href")

    return ScrapeResult(
        url=url,
        business_name=_first_text(tree, _NAME_SELECTORS),
        category=_first_text(tree, _CATEGORY_SELECTORS),
        governorate=_first_text(tree, _GOVERNORATE_SELECTORS),
        phone=phone,
        emails=emails,
        website=website,
        address=_first_text(tree, _ADDRESS_SELECTORS),
        raw_html_hash=hashlib.md5(html.encode()).hexdigest(),
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


import structlog

log = structlog.get_logger()


def scrape_category(
    category_url: str,
    pipeline: "Pipeline",
    csv_writer: "CSVWriter",
    rate_limiter: "RateLimiter",
    proxy: str | None = None,
    max_pages: int = 50,
    consecutive_empty_halt: int = 5,
) -> int:
    from scraper.pipeline import BlockedError

    total_written = 0
    consecutive_empty = 0
    page_url: str | None = category_url

    for page_num in range(1, max_pages + 1):
        if page_url is None:
            break

        log.info("scraping_page", page=page_num, url=page_url)
        try:
            resp = pipeline.fetch(page_url, proxy=proxy)
        except BlockedError:
            log.error("category_blocked", url=page_url)
            break

        listing_urls = parse_listing_urls(resp.text)

        if not listing_urls or is_empty_page(resp.text):
            consecutive_empty += 1
            log.warning(
                "empty_page",
                page=page_num,
                url=page_url,
                consecutive=consecutive_empty,
            )
            if consecutive_empty >= consecutive_empty_halt:
                log.error(
                    "dom_drift_halt",
                    msg="Halting: too many consecutive empty pages. Possible DOM drift.",
                    consecutive=consecutive_empty,
                    last_url=page_url,
                )
                break
        else:
            consecutive_empty = 0

        for listing_url in listing_urls:
            rate_limiter.wait()
            try:
                detail_resp = pipeline.fetch(listing_url, proxy=proxy)
                result = parse_detail(detail_resp.text, listing_url)
                result.source_tier = detail_resp.tier
                rows = csv_writer.write(result)
                total_written += rows
                log.info(
                    "listing_scraped",
                    url=listing_url,
                    emails=result.emails,
                    rows_written=rows,
                )
            except BlockedError:
                log.warning("listing_blocked", url=listing_url)
                continue

        page_url = parse_next_page_url(resp.text)
        if page_url:
            rate_limiter.wait()

    return total_written
