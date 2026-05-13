import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode

import structlog
from selectolax.parser import HTMLParser

from scraper.email_extract import extract_emails
from scraper.models import Facet, ScrapeResult
from scraper.sites._util import _first_attr, _first_text

if TYPE_CHECKING:
    from scraper.csv_writer import ResultWriter
    from scraper.pipeline import Pipeline
    from scraper.proxy_pool import ProxyPool
    from scraper.rate_limiter import RateLimiter

log = structlog.get_logger()

BASE_URL = "https://yellowpages.com.eg"
TARGET_TYPES = {"category", "brand", "keyword"}
ARABIC_ROLE_SEARCH_TERMS = {
    "مصنع",
    "استيراد",
    "تصدير",
    "استيراد وتصدير",
    "توزيع",
}
SEARCH_ALIASES = {
    "factory": "factory",
    "import": "import",
    "export": "export",
    "distribution": "distribution",
    "مصنع": "factory",
    "استيراد": "import",
    "تصدير": "export",
    "توزيع": "distribution",
}
CATEGORY_ALIASES = {"استيراد وتصدير": "import-&-export"}

# Site-wide footer/chrome emails that appear on every profile — never per-business.
_EMAIL_DENYLIST = {"customercare@yellow.com.eg"}

_PHONE_RETRIES = 3
_CONTACT_RETRIES = 1

_PROFILE_HREF_PREFIX = "/en/profile/"
_NAME_SELECTORS = ["h1.companyName", "h1"]
_PHONE_SELECTORS = ["a[href^='tel:']", ".phoneNum", ".phone"]
_WEBSITE_SELECTORS = ["a.website", "a.btn.website", ".website a"]
_ADDRESS_SELECTORS = [".company-address span", ".company-address", "[itemprop='streetAddress']"]
_CATEGORY_SELECTORS = [".companyName-category", ".category"]
_GOVERNORATE_SELECTORS = [".company-governorate", "[itemprop='addressRegion']"]


@dataclass(frozen=True)
class ListingCard:
    url: str
    facets: list[Facet]


def build_category_url(category: str, governorate: str | None, page: int = 1) -> str:
    path = f"/en/category/{quote(category, safe='-&')}/p{page}"
    qs = f"?{urlencode({'city': governorate})}" if governorate else ""
    return f"{BASE_URL}{path}{qs}"


def build_target_url(
    target_type: str,
    slug: str,
    page: int = 1,
    city_slug: str | None = None,
) -> str:
    if target_type not in TARGET_TYPES:
        raise ValueError(f"Unsupported target_type: {target_type}")
    encoded_slug = quote(slug, safe="-&")
    if slug in ARABIC_ROLE_SEARCH_TERMS and target_type in {"category", "keyword"}:
        path = f"/en/search/{encoded_slug}" if page == 1 else f"/en/search/{encoded_slug}/p{page}"
    elif target_type == "keyword":
        path = f"/en/keyword/{encoded_slug}" if page == 1 else f"/en/keyword/{encoded_slug}/p{page}"
    else:
        path = f"/en/{target_type}/{encoded_slug}/p{page}"
    qs = f"?{urlencode({'city': city_slug})}" if city_slug else ""
    return f"{BASE_URL}{path}{qs}"


def _normalize_href(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return BASE_URL + href
    return href


def parse_listing_urls(html: str) -> list[str]:
    return [card.url for card in parse_listing_cards(html)]


def _facet_from_href(href: str, name: str) -> Facet | None:
    path = href.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    for facet_type in TARGET_TYPES:
        marker = f"/en/{facet_type}/"
        if marker in path:
            slug = path.split(marker, 1)[1].split("/")[-1]
            if slug:
                return Facet(type=facet_type, slug=slug, name=name)
    return None


def _best_card_container(node) -> object:  # type: ignore[no-untyped-def]
    container = node.parent
    best = container or node
    for _ in range(5):
        if container is None:
            break
        html = container.html or ""
        if "/en/category/" in html or "/en/brand/" in html or "/en/keyword/" in html:
            best = container
            break
        best = container
        container = container.parent
    return best


def parse_listing_cards(html: str) -> list[ListingCard]:
    tree = HTMLParser(html)
    seen: set[str] = set()
    cards: list[ListingCard] = []
    for node in tree.css(f"a[href*='{_PROFILE_HREF_PREFIX}']"):
        href = node.attrs.get("href", "") or ""
        if _PROFILE_HREF_PREFIX not in href:
            continue
        full = _normalize_href(href.split("?", 1)[0].split("#", 1)[0])
        if not full or full in seen:
            continue
        seen.add(full)
        container = _best_card_container(node)
        facets: list[Facet] = []
        facet_keys: set[tuple[str, str]] = set()
        for facet_node in container.css("a[href]"):  # type: ignore[attr-defined]
            facet_href = facet_node.attrs.get("href", "") or ""
            facet_name = facet_node.text(strip=True)
            facet = _facet_from_href(facet_href, facet_name)
            if facet is None:
                continue
            key = (facet.type, facet.slug)
            if key in facet_keys:
                continue
            facet_keys.add(key)
            facets.append(facet)
        cards.append(ListingCard(url=full, facets=facets))
    return cards


def is_empty_page(html: str) -> bool:
    return len(parse_listing_urls(html)) == 0


def parse_detail(html: str, url: str) -> ScrapeResult:
    tree = HTMLParser(html)
    seen: set[str] = set(_EMAIL_DENYLIST)
    emails = extract_emails(html, seen)
    emails = [e for e in emails if e not in _EMAIL_DENYLIST]

    # Phones are loaded via AJAX (/en/getPhones/{id}/false) — not in static HTML.
    # All tel: links in static HTML are YP site-wide footer numbers, not business phones.
    # scrape_category calls _fetch_phones() to populate result.phone after parse_detail.
    phone = ""

    website = _first_attr(tree, _WEBSITE_SELECTORS, "href")
    if not website or website == "#" or website.startswith("javascript:"):
        website = ""

    fb_node = tree.css_first("a.facebook[href]")
    facebook_url = ""
    if fb_node:
        fb_href = fb_node.attrs.get("href", "") or ""
        if "facebook.com" in fb_href:
            facebook_url = fb_href

    return ScrapeResult(
        url=url,
        business_name=_first_text(tree, _NAME_SELECTORS),
        category=_first_text(tree, _CATEGORY_SELECTORS),
        governorate=_first_text(tree, _GOVERNORATE_SELECTORS),
        phone=phone,
        emails=emails,
        website=website,
        facebook_url=facebook_url,
        address=_first_text(tree, _ADDRESS_SELECTORS),
        raw_html_hash=hashlib.md5(html.encode()).hexdigest(),
        scraped_at=datetime.now(UTC).isoformat(),
    )


def arabic_profile_url(url: str) -> str:
    return url.replace("/en/profile/", "/ar/profile/", 1)


def merge_arabic_detail(result: ScrapeResult, arabic_html: str) -> ScrapeResult:
    arabic = parse_detail(arabic_html, arabic_profile_url(result.url))
    result.business_name_ar = arabic.business_name
    result.category_ar = arabic.category
    result.governorate_ar = arabic.governorate
    result.address_ar = arabic.address
    return result


def _extract_business_id(url: str) -> str | None:
    parts = url.rstrip("/").split("/")
    candidate = parts[-1] if parts else ""
    return candidate if candidate.isdigit() else None


def _fetch_phones(pipeline: "Pipeline", biz_id: str, referer: str) -> str:
    phones_url = f"{BASE_URL}/en/getPhones/{biz_id}/false"
    try:
        resp = pipeline.fetch(phones_url, referer=referer)
        if not resp.ok:
            return ""
        data = json.loads(resp.text.strip())
        phones = [p for group in data if isinstance(group, list) for p in group if p]
        return ", ".join(phones)
    except Exception:
        return ""


def _backfill_existing_arabic_detail(
    listing_url: str,
    pipeline: "Pipeline",
    csv_writer: "ResultWriter",
) -> int:
    has_arabic_fields = getattr(csv_writer, "has_arabic_fields", None)
    update_arabic_fields = getattr(csv_writer, "update_arabic_fields", None)
    if not callable(has_arabic_fields) or not callable(update_arabic_fields):
        return 0
    if has_arabic_fields(listing_url):
        return 0
    arabic_url = arabic_profile_url(listing_url)
    if arabic_url == listing_url:
        return 0
    try:
        arabic_resp = pipeline.fetch(arabic_url, referer=listing_url)
        if not arabic_resp.ok:
            return 0
        arabic = parse_detail(arabic_resp.text, arabic_url)
        return int(update_arabic_fields(listing_url, arabic) or 0)
    except Exception:
        log.warning("arabic_detail_unavailable", url=arabic_url)
        return 0


def _crawl_facets(
    listing_facets: list[Facet],
    target_type: str,
    slug: str,
    city_slug: str | None,
) -> list[Facet]:
    facets = list(listing_facets)
    source_facet = Facet(type=target_type, slug=slug, name=slug)
    if not any(f.type == source_facet.type and f.slug == source_facet.slug for f in facets):
        facets.append(source_facet)
    if city_slug and not any(f.type == "city" and f.slug == city_slug for f in facets):
        facets.append(Facet(type="city", slug=city_slug, name=city_slug))
    return facets


def scrape_category(
    category: str,
    governorate: str | None,
    pipeline: "Pipeline",
    csv_writer: "ResultWriter",
    rate_limiter: "RateLimiter",
    proxy_pool: "ProxyPool | None" = None,
    max_pages: int = 50,
    consecutive_empty_halt: int = 5,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    return scrape_target(
        "category",
        category,
        governorate,
        pipeline,
        csv_writer,
        rate_limiter,
        proxy_pool=proxy_pool,
        max_pages=max_pages,
        consecutive_empty_halt=consecutive_empty_halt,
        progress_callback=progress_callback,
    )


def scrape_target(
    target_type: str,
    slug: str,
    city_slug: str | None,
    pipeline: "Pipeline",
    csv_writer: "ResultWriter",
    rate_limiter: "RateLimiter",
    proxy_pool: "ProxyPool | None" = None,
    max_pages: int = 50,
    consecutive_empty_halt: int = 5,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    from scraper.pipeline import BlockedError

    if target_type not in TARGET_TYPES:
        raise ValueError(f"Unsupported target_type: {target_type}")
    if max_pages <= 0:
        raise ValueError(f"max_pages must be positive, got {max_pages}")
    if consecutive_empty_halt <= 0:
        raise ValueError(f"consecutive_empty_halt must be positive, got {consecutive_empty_halt}")

    total_written = 0
    consecutive_empty = 0
    referer = f"{BASE_URL}/en"

    for page_num in range(1, max_pages + 1):
        page_url = build_target_url(target_type, slug, page=page_num, city_slug=city_slug)
        proxy = proxy_pool.get() if proxy_pool else None

        log.info("scraping_page", page=page_num, url=page_url, proxy=proxy)
        try:
            resp = pipeline.fetch(page_url, proxy=proxy, referer=referer)
        except BlockedError:
            log.error("category_blocked", url=page_url)
            if proxy_pool and proxy:
                proxy_pool.record_failure(proxy)
            break

        if not resp.ok:
            consecutive_empty += 1
            log.warning("non_ok_response", page=page_num, url=page_url, status=resp.status_code)
            if progress_callback:
                progress_callback(page_num, total_written)
            if consecutive_empty >= consecutive_empty_halt:
                log.error("dom_drift_halt", consecutive=consecutive_empty, last_url=page_url)
                break
            continue

        listing_cards = parse_listing_cards(resp.text)

        if not listing_cards:
            consecutive_empty += 1
            log.warning("empty_page", page=page_num, url=page_url, consecutive=consecutive_empty)
            if progress_callback:
                progress_callback(page_num, total_written)
            if consecutive_empty >= consecutive_empty_halt:
                log.error("dom_drift_halt", consecutive=consecutive_empty, last_url=page_url)
                break
            continue

        consecutive_empty = 0
        for listing_card in listing_cards:
            listing_url = listing_card.url
            facets = _crawl_facets(listing_card.facets, target_type, slug, city_slug)
            has_url = getattr(csv_writer, "has_url", None)
            if callable(has_url) and has_url(listing_url):
                write_facets = getattr(csv_writer, "write_facets", None)
                saved_facets = write_facets(listing_url, facets) if callable(write_facets) else 0
                updated_arabic = _backfill_existing_arabic_detail(
                    listing_url,
                    pipeline,
                    csv_writer,
                )
                log.info(
                    "listing_skip_existing",
                    url=listing_url,
                    saved_facets=saved_facets,
                    updated_arabic=updated_arabic,
                )
                continue
            result = None
            detail_resp = None
            max_attempts = max(_PHONE_RETRIES, _CONTACT_RETRIES) + 1
            for attempt in range(1, max_attempts + 1):
                rate_limiter.wait()
                detail_proxy = proxy_pool.get() if proxy_pool else None
                try:
                    detail_resp = pipeline.fetch(listing_url, proxy=detail_proxy, referer=page_url)
                except BlockedError:
                    log.warning("listing_blocked", url=listing_url)
                    if proxy_pool and detail_proxy:
                        proxy_pool.record_failure(detail_proxy)
                    detail_resp = None
                    break
                result = parse_detail(detail_resp.text, listing_url)
                arabic_url = arabic_profile_url(listing_url)
                if arabic_url != listing_url:
                    try:
                        arabic_resp = pipeline.fetch(
                            arabic_url,
                            proxy=detail_proxy,
                            referer=listing_url,
                        )
                        if arabic_resp.ok:
                            result = merge_arabic_detail(result, arabic_resp.text)
                    except Exception:
                        log.warning("arabic_detail_unavailable", url=arabic_url)
                result.source_tier = detail_resp.tier
                result.facets = facets
                biz_id = _extract_business_id(listing_url)
                if biz_id:
                    result.phone = _fetch_phones(pipeline, biz_id, referer=listing_url)
                has_phone = bool(result.phone)
                has_contact = (
                    bool(result.emails)
                    or bool(result.website)
                    or bool(result.facebook_url)
                )
                phone_budget = _PHONE_RETRIES + 1
                contact_budget = _CONTACT_RETRIES + 1
                if has_phone and has_contact:
                    break
                if not has_phone and attempt < phone_budget:
                    log.info("retry_listing_no_phone", url=listing_url, attempt=attempt)
                    continue
                if has_phone and not has_contact and attempt < contact_budget:
                    log.info("retry_listing_no_contact", url=listing_url, attempt=attempt)
                    continue
                break
            if result is None:
                continue
            rows = csv_writer.write(result)
            total_written += rows
            log.info(
                "listing_scraped",
                url=listing_url,
                emails=result.emails,
                phone=bool(result.phone),
                website=bool(result.website),
                rows_written=rows,
            )

        rate_limiter.wait()
        if progress_callback:
            progress_callback(page_num, total_written)

    return total_written
