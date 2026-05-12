"""Taxonomy discovery for Yellow Pages Egypt."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import structlog
from selectolax.parser import HTMLParser

from scraper.storage import Backend, open_connection, placeholder

log = structlog.get_logger()

BASE_URL = "https://yellowpages.com.eg"
DEFAULT_SEED_PATH = "data/taxonomy_seed.json"

_ALLOWED_LOCATION_TYPES = {"city", "area", "district"}
_COUNT_RE = re.compile(r"^(?P<name>.*?)\s*\((?P<count>[\d,]+)\)\s*$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SPACE_RE = re.compile(r"\s+")


def load_seed(seed_path: str | Path | None = None) -> dict[str, Any]:
    """Load taxonomy seed JSON. Returns dict with taxonomy lists."""
    if seed_path is None:
        seed_path = DEFAULT_SEED_PATH
    p = Path(seed_path)
    if not p.exists():
        log.warning("seed_not_found", path=str(p))
        return {"categories": [], "locations": [], "brands": [], "keywords": []}
    return json.loads(p.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.lower().strip()).strip("-")


def _clean_spaces(value: str) -> str:
    return _SPACE_RE.sub(" ", value.replace("\u200e", "").strip())


def _title_from_data(value: str) -> str:
    words = []
    for word in _clean_spaces(value).split(" "):
        if any(char.isdigit() for char in word):
            words.append(word.lower())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def _split_name_count(text: str) -> tuple[str, int]:
    text = _clean_spaces(text)
    match = _COUNT_RE.match(text)
    if not match:
        return text, 0
    return match.group("name").strip(), int(match.group("count").replace(",", ""))


def _href_slug(href: str, prefix: str) -> str:
    path = href.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    marker = f"{prefix}/"
    if marker not in path:
        return ""
    return path.split(marker, 1)[1].split("/")[-1]


def _unique_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        slug = str(item.get("slug", ""))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        unique.append(item)
    return unique


def parse_categories(html: str) -> list[dict[str, Any]]:
    """Parse categories from YP category index HTML."""
    tree = HTMLParser(html)
    categories: list[dict[str, Any]] = []
    for node in tree.css(".category-item a, .cat-item a, a[href*='/category/']"):
        href = node.attrs.get("href", "") or ""
        text = node.text(strip=True)
        slug = _href_slug(href, "/category")
        if not slug or not text:
            continue
        name, result_count = _split_name_count(text)
        categories.append({"slug": slug, "name": name, "result_count": result_count, "href": href})
    return _unique_items(categories)


def parse_brands(html: str) -> list[dict[str, Any]]:
    """Parse brands from YP brand index HTML."""
    tree = HTMLParser(html)
    brands: list[dict[str, Any]] = []
    for node in tree.css("a[href*='/brand/']"):
        href = node.attrs.get("href", "") or ""
        text = node.text(strip=True)
        slug = _href_slug(href, "/brand")
        if not slug or not text:
            continue
        name, result_count = _split_name_count(text)
        brands.append({"slug": slug, "name": name, "result_count": result_count, "href": href})
    return _unique_items(brands)


def parse_keywords(html: str) -> list[dict[str, Any]]:
    """Parse keywords from YP keyword index HTML."""
    tree = HTMLParser(html)
    keywords: list[dict[str, Any]] = []
    for node in tree.css("a[href*='/keyword/']"):
        href = node.attrs.get("href", "") or ""
        text = node.text(strip=True)
        slug = _href_slug(href, "/keyword")
        if slug and text:
            keywords.append({"slug": slug, "name": _clean_spaces(text), "href": href})
    return _unique_items(keywords)


def parse_last_page(html: str, base_path: str) -> int:
    """Return the largest pager page number for an index page."""
    tree = HTMLParser(html)
    page_nums = [1]
    escaped_base = re.escape(base_path.rstrip("/"))
    patterns = [re.compile(rf"{escaped_base}/p(\d+)(?:$|[?#])")]
    if base_path.endswith("keywords.html"):
        patterns.append(re.compile(r"/en/p(\d+)/keywords\.html(?:$|[?#])"))
    for node in tree.css("a[href]"):
        href = node.attrs.get("href", "") or ""
        for pattern in patterns:
            match = pattern.search(href)
            if match:
                page_nums.append(int(match.group(1)))
    return max(page_nums)


def parse_locations(html: str) -> list[dict[str, Any]]:
    """Parse city, area, and district filters from YP HTML."""
    tree = HTMLParser(html)
    locations: list[dict[str, Any]] = []

    for node in tree.css(".location-item, .city-item, .area-item"):
        slug = node.attrs.get("data-slug") or ""
        name = node.text(strip=True)
        loc_type = node.attrs.get("data-type") or "city"
        parent = node.attrs.get("data-parent", "")
        if slug and name:
            locations.append(
                {
                    "slug": slug,
                    "name": name,
                    "type": loc_type if loc_type in _ALLOWED_LOCATION_TYPES else "city",
                    "parent_slug": parent or "",
                    "external_id": "",
                    "parent_external_id": "",
                    "result_count": 0,
                }
            )

    for node in tree.css("input.locations_filter[name='locations_filter']"):
        attrs = node.attrs
        classes = attrs.get("class") or ""
        loc_type = ""
        parent_external_id = ""
        if "cities_filter" in classes:
            loc_type = "city"
        elif "areas_filter" in classes:
            loc_type = "area"
            parent_external_id = attrs.get("data-cityid", "") or ""
        elif "district_filter" in classes:
            loc_type = "district"
            parent_external_id = attrs.get("data-areaid", "") or ""
        if loc_type not in _ALLOWED_LOCATION_TYPES:
            continue

        input_id = attrs.get("id", "") or ""
        label_text = ""
        if input_id:
            label = tree.css_first(f"label[for='{input_id}']")
            if label:
                label_text = label.text(strip=True)

        raw_name = attrs.get("data-data", "") or label_text
        label_name, result_count = _split_name_count(label_text or raw_name)
        name = _title_from_data(raw_name) if raw_name else label_name
        if not name:
            continue
        locations.append(
            {
                "slug": _slugify(name),
                "name": name,
                "type": loc_type,
                "parent_slug": "",
                "external_id": attrs.get("value", "") or "",
                "parent_external_id": parent_external_id,
                "result_count": result_count,
            }
        )
    return _unique_items(locations)


def populate_from_seed(conn: Any, seed: dict[str, Any]) -> None:
    """Insert or replace taxonomy rows from seed dict. Idempotent."""
    now = ""
    _upsert_categories(conn, seed.get("categories", []), now)
    _upsert_brands(conn, seed.get("brands", []), now)
    _upsert_keywords(conn, seed.get("keywords", []), now)
    _upsert_locations(conn, seed.get("locations", []), now)
    conn.commit()
    log.info(
        "seed_populated",
        categories=len(seed.get("categories", [])),
        brands=len(seed.get("brands", [])),
        keywords=len(seed.get("keywords", [])),
        locations=len(seed.get("locations", [])),
    )


def _resolve_location_parents(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_external = {
        str(loc.get("external_id", "")): str(loc.get("slug", ""))
        for loc in locations
        if loc.get("external_id")
    }
    resolved: list[dict[str, Any]] = []
    for loc in locations:
        item = dict(loc)
        if not item.get("parent_slug") and item.get("parent_external_id"):
            item["parent_slug"] = by_external.get(str(item["parent_external_id"]), "")
        resolved.append(item)
    return resolved


def _fetch_text(url: str, pipeline: Any | None = None, referer: str | None = None) -> str:
    if pipeline is not None:
        resp = pipeline.fetch(url, referer=referer)
        return resp.text if resp.ok else ""
    from curl_cffi import requests as cffi_requests

    resp = cffi_requests.get(url, impersonate="chrome120", timeout=20)
    return str(resp.text) if 200 <= resp.status_code < 300 else ""


def _collect_paginated_index(
    path: str,
    parser: Any,
    pipeline: Any | None = None,
    keyword_pager: bool = False,
) -> list[dict[str, Any]]:
    first_url = urljoin(BASE_URL, path)
    first_html = _fetch_text(first_url, pipeline=pipeline)
    if not first_html:
        return []
    items = parser(first_html)
    last_page = parse_last_page(first_html, path)
    for page in range(2, last_page + 1):
        page_path = f"/en/p{page}/keywords.html" if keyword_pager else f"{path}/p{page}"
        html = _fetch_text(urljoin(BASE_URL, page_path), pipeline=pipeline, referer=first_url)
        if not html:
            break
        page_items = parser(html)
        if not page_items:
            break
        before = len({item["slug"] for item in items})
        items.extend(page_items)
        after = len({item["slug"] for item in items})
        if after == before:
            break
    return _unique_items(items)


def _upsert_categories(
    conn: Any,
    categories: list[dict[str, Any]],
    scraped_at: str,
    backend: Backend = "sqlite",
) -> None:
    ph = placeholder(backend)
    for cat in categories:
        params = (
            cat["slug"],
            cat["name"],
            cat.get("parent_slug", ""),
            cat.get("result_count", 0),
            cat.get("href", ""),
            scraped_at,
        )
        if backend == "postgres":
            conn.execute(
                f"""INSERT INTO categories
                (slug, name, parent_slug, result_count, href, scraped_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT (slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    parent_slug=EXCLUDED.parent_slug,
                    result_count=EXCLUDED.result_count,
                    href=EXCLUDED.href,
                    scraped_at=EXCLUDED.scraped_at""",
                params,
            )
        else:
            conn.execute(
                """INSERT OR REPLACE INTO categories
                (slug, name, parent_slug, result_count, href, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                params,
            )


def _upsert_brands(
    conn: Any,
    brands: list[dict[str, Any]],
    scraped_at: str,
    backend: Backend = "sqlite",
) -> None:
    ph = placeholder(backend)
    for brand in brands:
        params = (
            brand["slug"],
            brand["name"],
            brand.get("result_count", 0),
            brand.get("href", ""),
            scraped_at,
        )
        if backend == "postgres":
            conn.execute(
                f"""INSERT INTO brands
                (slug, name, result_count, href, scraped_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT (slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    result_count=EXCLUDED.result_count,
                    href=EXCLUDED.href,
                    scraped_at=EXCLUDED.scraped_at""",
                params,
            )
        else:
            conn.execute(
                """INSERT OR REPLACE INTO brands
                (slug, name, result_count, href, scraped_at)
                VALUES (?, ?, ?, ?, ?)""",
                params,
            )


def _upsert_keywords(
    conn: Any,
    keywords: list[dict[str, Any]],
    scraped_at: str,
    backend: Backend = "sqlite",
) -> None:
    ph = placeholder(backend)
    for keyword in keywords:
        params = (keyword["slug"], keyword["name"], keyword.get("href", ""), scraped_at)
        if backend == "postgres":
            conn.execute(
                f"""INSERT INTO keywords
                (slug, name, href, scraped_at)
                VALUES ({ph}, {ph}, {ph}, {ph})
                ON CONFLICT (slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    href=EXCLUDED.href,
                    scraped_at=EXCLUDED.scraped_at""",
                params,
            )
        else:
            conn.execute(
                """INSERT OR REPLACE INTO keywords
                (slug, name, href, scraped_at)
                VALUES (?, ?, ?, ?)""",
                params,
            )


def _location_sort_key(location: dict[str, Any]) -> int:
    return {"city": 0, "area": 1, "district": 2}.get(location.get("type", "city"), 99)


def _upsert_locations(
    conn: Any,
    locations: list[dict[str, Any]],
    scraped_at: str,
    backend: Backend = "sqlite",
) -> None:
    ph = placeholder(backend)
    for loc in sorted(_resolve_location_parents(locations), key=_location_sort_key):
        params = (
            loc["slug"],
            loc["name"],
            loc.get("type", "city"),
            loc.get("external_id", ""),
            loc.get("parent_slug") or None if backend == "postgres" else loc.get("parent_slug", ""),
            loc.get("result_count", 0),
            scraped_at,
        )
        if backend == "postgres":
            conn.execute(
                f"""INSERT INTO locations
                (slug, name, type, external_id, parent_slug, result_count, scraped_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT (slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    type=EXCLUDED.type,
                    external_id=EXCLUDED.external_id,
                    parent_slug=EXCLUDED.parent_slug,
                    result_count=EXCLUDED.result_count,
                    scraped_at=EXCLUDED.scraped_at""",
                params,
            )
        else:
            conn.execute(
                """INSERT OR REPLACE INTO locations
                (slug, name, type, external_id, parent_slug, result_count, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                params,
            )


def refresh_from_live(
    conn: Any,
    pipeline: Any | None = None,
    max_pages: int = 5,
    backend: Backend = "sqlite",
) -> None:
    """Fetch live YP taxonomy pages and update taxonomy tables."""
    log.info("refresh_from_live_start")
    scraped_at = datetime.now(UTC).isoformat()
    categories = _collect_paginated_index(
        "/en/related-categories",
        parse_categories,
        pipeline=pipeline,
    )
    brands = _collect_paginated_index("/en/related-brands", parse_brands, pipeline=pipeline)
    keywords = _collect_paginated_index(
        "/en/keywords.html",
        parse_keywords,
        pipeline=pipeline,
        keyword_pager=True,
    )
    _upsert_categories(conn, categories, scraped_at, backend)
    _upsert_brands(conn, brands, scraped_at, backend)
    _upsert_keywords(conn, keywords, scraped_at, backend)

    locations: list[dict[str, Any]] = []
    for cat in categories[:max_pages]:
        html = _fetch_text(urljoin(BASE_URL, f"/en/category/{cat['slug']}"), pipeline=pipeline)
        if html:
            locations.extend(parse_locations(html))
    _upsert_locations(conn, locations, scraped_at, backend)
    conn.commit()
    log.info(
        "refresh_from_live_done",
        categories=len(categories),
        brands=len(brands),
        keywords=len(keywords),
        locations=len(_unique_items(locations)),
    )


def init_taxonomy(
    db_path: str | Path | None = None,
    seed_path: str | Path | None = None,
    live_refresh: bool = False,
    pipeline: Any | None = None,
) -> None:
    """Initialize taxonomy DB from seed and optionally refresh live."""
    conn, backend = open_connection(db_path)
    seed = load_seed(seed_path)
    if backend == "postgres":
        now = ""
        _upsert_categories(conn, seed.get("categories", []), now, backend)
        _upsert_brands(conn, seed.get("brands", []), now, backend)
        _upsert_keywords(conn, seed.get("keywords", []), now, backend)
        _upsert_locations(conn, seed.get("locations", []), now, backend)
        conn.commit()
    else:
        populate_from_seed(conn, seed)
    if live_refresh:
        refresh_from_live(conn, pipeline=pipeline, backend=backend)
    conn.close()
