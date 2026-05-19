import csv
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from scraper.models import ScrapeResult


class ResultWriter(Protocol):
    def write(self, result: ScrapeResult | None) -> int:
        """Write result. Return 1 if written, 0 if duplicate.
        Implementors MUST be idempotent on source_url and MUST accept None gracefully."""
        ...

    def has_url(self, source_url: str) -> bool:
        """Return True when this source URL has already been persisted."""
        ...


FIELDNAMES = [
    "business_name",
    "business_name_ar",
    "category",
    "category_ar",
    "governorate",
    "governorate_ar",
    "phone",
    "email",
    "website",
    "facebook_url",
    "address",
    "address_ar",
    "target_type",
    "target_slug",
    "target_name",
    "target_name_ar",
    "city_slug",
    "facet_categories",
    "facet_keywords",
    "facet_brands",
    "facet_cities",
    "facet_names",
    "facet_names_ar",
    "source_url",
    "source_tier",
    "raw_html_hash",
    "scraped_at",
]

AR_FACTORY = "\u0645\u0635\u0646\u0639"
AR_IMPORT = "\u0627\u0633\u062a\u064a\u0631\u0627\u062f"
AR_EXPORT = "\u062a\u0635\u062f\u064a\u0631"
AR_IMPORT_EXPORT = "\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0648\u062a\u0635\u062f\u064a\u0631"
AR_DISTRIBUTION = "\u062a\u0648\u0632\u064a\u0639"


class CSVWriter:
    """Writes results to CSV. Implements ResultWriter (best-effort in-process dedup only).
    For persistent cross-run dedup, use SQLiteWriter."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._seen_emails: set[str] = set()
        self._seen_urls: set[str] = set()
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        with self._path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                email = row.get("email")
                if email:
                    self._seen_emails.add(email.lower().strip())
                url = row.get("source_url")
                if url:
                    self._seen_urls.add(url.strip())

    def write(self, result: ScrapeResult | None) -> int:
        """Write result. Returns 1 if written, 0 if duplicate (best-effort in-process dedup)."""
        with self._lock:
            return self._write_locked(result)

    def _write_locked(self, result: ScrapeResult | None) -> int:
        """Called with self._lock held."""
        if result is None:
            return 0
        if result.url and result.url in self._seen_urls:
            return 0
        # Check file size to avoid TOCTOU race condition
        is_new = not self._path.exists() or self._path.stat().st_size == 0
        written = 0
        with self._path.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if is_new:
                writer.writeheader()
            emails = [e for e in (result.emails or []) if isinstance(e, str) and e]
            new_emails = [e for e in emails if e.lower().strip() not in self._seen_emails]
            rows = new_emails if new_emails else [""]
            for email in rows:
                canonical = email.lower().strip()
                if canonical:
                    self._seen_emails.add(canonical)
                facet_row = _facet_row(result)
                writer.writerow(
                    {
                        "business_name": result.business_name,
                        "business_name_ar": result.business_name_ar,
                        "category": result.category,
                        "category_ar": result.category_ar,
                        "governorate": result.governorate,
                        "governorate_ar": result.governorate_ar,
                        "phone": result.phone,
                        "email": canonical,
                        "website": result.website,
                        "facebook_url": result.facebook_url,
                        "address": result.address,
                        "address_ar": result.address_ar,
                        **facet_row,
                        "source_url": result.url,
                        "source_tier": result.source_tier,
                        "raw_html_hash": result.raw_html_hash,
                        "scraped_at": result.scraped_at
                        or datetime.now(UTC).isoformat(),
                    }
                )
                written += 1
        if result.url:
            self._seen_urls.add(result.url)
        return written

    def has_url(self, source_url: str) -> bool:
        return bool(source_url and source_url in self._seen_urls)

    @property
    def seen_count(self) -> int:
        return len(self._seen_emails)


def _join_unique(values: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return " | ".join(ordered)


def _facet_row(result: ScrapeResult) -> dict[str, str]:
    facets = result.facets or []
    target_from_facets = next(
        (
            facet
            for facet in facets
            if facet.type in {"category", "keyword"}
            and (facet.name_ar or facet.slug) in {
                "استيراد",
                "تصدير",
                "مصنع",
                "توزيع",
                "استيراد وتصدير",
                "import",
                "export",
                "factory",
                "distribution",
                "import-&-export",
                "factory-equipment-and-supplies",
            }
        ),
        None,
    )
    city = result.city_slug or next((facet.slug for facet in facets if facet.type == "city"), "")
    return {
        "target_type": result.target_type or (target_from_facets.type if target_from_facets else ""),
        "target_slug": result.target_slug or (target_from_facets.slug if target_from_facets else ""),
        "target_name": result.target_name or (target_from_facets.name if target_from_facets else ""),
        "target_name_ar": result.target_name_ar
        or (target_from_facets.name_ar if target_from_facets else ""),
        "city_slug": city,
        "facet_categories": _join_unique(
            [facet.slug for facet in facets if facet.type == "category"]
        ),
        "facet_keywords": _join_unique(
            [facet.slug for facet in facets if facet.type == "keyword"]
        ),
        "facet_brands": _join_unique([facet.slug for facet in facets if facet.type == "brand"]),
        "facet_cities": _join_unique([facet.slug for facet in facets if facet.type == "city"]),
        "facet_names": _join_unique([facet.name for facet in facets]),
        "facet_names_ar": _join_unique([facet.name_ar for facet in facets]),
    }
