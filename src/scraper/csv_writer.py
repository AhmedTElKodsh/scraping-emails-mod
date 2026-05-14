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
    "category",
    "governorate",
    "phone",
    "email",
    "website",
    "facebook_url",
    "address",
    "source_url",
    "source_tier",
    "raw_html_hash",
    "scraped_at",
]


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
        is_new = not self._path.exists()
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
                writer.writerow(
                    {
                        "business_name": result.business_name,
                        "category": result.category,
                        "governorate": result.governorate,
                        "phone": result.phone,
                        "email": canonical,
                        "website": result.website,
                        "facebook_url": result.facebook_url,
                        "address": result.address,
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
