"""Read-only preview for future YellowPages/acquisition merges."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.acquisition_db import get_connection as get_acquisition_connection
from scraper.acquisition_db import init_acquisition_db
from scraper.db import get_connection as get_scraper_connection

MERGE_BUSINESS_KEYS = [
    "origin",
    "source_url",
    "business_name",
    "category_slug",
    "city_slug",
    "phone",
    "email",
    "website",
    "facebook_url",
    "address",
    "raw_html_hash",
    "source_tier",
    "scraped_at",
    "confidence",
]


def _row_value(row: dict[str, Any], key: str, default: Any = "") -> Any:
    value = row.get(key, default)
    return default if value is None else value


def _normalize(row: dict[str, Any], origin: str, confidence: str | float) -> dict[str, Any]:
    return {
        "origin": origin,
        "source_url": _row_value(row, "source_url"),
        "business_name": _row_value(row, "business_name"),
        "category_slug": _row_value(row, "category_slug"),
        "city_slug": _row_value(row, "city_slug"),
        "phone": _row_value(row, "phone"),
        "email": _row_value(row, "email"),
        "website": _row_value(row, "website"),
        "facebook_url": _row_value(row, "facebook_url"),
        "address": _row_value(row, "address"),
        "raw_html_hash": _row_value(row, "raw_html_hash"),
        "source_tier": _row_value(row, "source_tier"),
        "scraped_at": _row_value(row, "scraped_at"),
        "confidence": confidence,
    }


def _load_yellowpages_rows(db_path: str | Path, limit: int) -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.exists():
        return []
    conn = get_scraper_connection(path)
    try:
        rows = conn.execute(
            """SELECT source_url,
                      business_name,
                      category_slug,
                      city_slug,
                      phone,
                      email,
                      website,
                      facebook_url,
                      address,
                      raw_html_hash,
                      source_tier,
                      scraped_at
            FROM businesses
            ORDER BY scraped_at DESC, business_name
            LIMIT ?""",
            (limit,),
        ).fetchall()
        return [_normalize(dict(row), "yellowpages", "yellowpages") for row in rows]
    finally:
        conn.close()


def _load_acquisition_rows(db_path: str | Path, limit: int) -> list[dict[str, Any]]:
    conn = get_acquisition_connection(db_path)
    init_acquisition_db(conn)
    try:
        rows = conn.execute(
            """SELECT source_url,
                      business_name,
                      category_slug,
                      city_slug,
                      phone,
                      email,
                      website,
                      facebook_url,
                      address,
                      raw_html_hash,
                      source_tier,
                      scraped_at,
                      confidence
            FROM businesses
            ORDER BY scraped_at DESC, business_name
            LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            _normalize(dict(row), "acquisition", float(row["confidence"]))
            for row in rows
        ]
    finally:
        conn.close()


def load_unified_business_preview(
    yellowpages_db_path: str | Path,
    acquisition_db_path: str | Path,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return read-only rows in the future merge shape."""
    acquisition_rows = _load_acquisition_rows(acquisition_db_path, limit)
    yellowpages_rows = _load_yellowpages_rows(yellowpages_db_path, limit)
    return (acquisition_rows + yellowpages_rows)[:limit]
