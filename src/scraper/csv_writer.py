import csv
from datetime import datetime, timezone
from pathlib import Path

from scraper.models import ScrapeResult

FIELDNAMES = [
    "business_name",
    "category",
    "governorate",
    "phone",
    "email",
    "website",
    "address",
    "source_url",
    "scraped_at",
]


class CSVWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._seen: set[str] = set()
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        with self._path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("email"):
                    self._seen.add(row["email"].lower().strip())

    def write(self, result: ScrapeResult) -> int:
        is_new = not self._path.exists()
        written = 0
        with self._path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if is_new:
                writer.writeheader()
            emails = result.emails if result.emails else [""]
            for email in emails:
                canonical = email.lower().strip()
                if canonical and canonical in self._seen:
                    continue
                if canonical:
                    self._seen.add(canonical)
                writer.writerow(
                    {
                        "business_name": result.business_name,
                        "category": result.category,
                        "governorate": result.governorate,
                        "phone": result.phone,
                        "email": canonical,
                        "website": result.website,
                        "address": result.address,
                        "source_url": result.url,
                        "scraped_at": result.scraped_at
                        or datetime.now(timezone.utc).isoformat(),
                    }
                )
                written += 1
        return written

    @property
    def seen_count(self) -> int:
        return len(self._seen)
