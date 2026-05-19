"""
Standalone local scraper for YellowPages Egypt.

Targets (keywords + categories):
  - استيراد      → /ar/search/import      (import)
  - تصدير        → /ar/search/export      (export)
  - مصنع         → /ar/search/factory     (factory)
  - توزيع        → /ar/search/distribution (distribution)
  - استيراد وتصدير → /ar/category/import-&-export (category)

Scrapes ALL Egyptian cities. Saves output to output/local_scrape_<timestamp>.csv

Usage:
    .venv\\Scripts\\python run_local_scrape.py [--max-pages N] [--output PATH]
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Path setup: make src/ importable ---
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from scraper.csv_writer import CSVWriter
from scraper.http_client import Tier1Client, Tier2Client
from scraper.pipeline import Pipeline
from scraper.proxy_pool import ProxyPool
from scraper.rate_limiter import RateLimiter
from scraper.sites.yellowpages_eg import scrape_target
from scraper.storage import is_postgres_url, storage_target

# ---------------------------------------------------------------------------
# Targets
#   Each entry is (target_type, slug)
#   The slug is the Arabic key - yellowpages_eg.py maps it via SEARCH_ALIASES
#   to the correct English search/category URL on the Arabic subdomain.
#   Arabic & English search pages return IDENTICAL listings, so we only scrape
#   Arabic to avoid duplicates.
# ---------------------------------------------------------------------------
TARGETS = [
    # search-based targets (-> /ar/search/<english-slug>)
    ("keyword", "استيراد"),           # import
    ("keyword", "تصدير"),             # export
    ("keyword", "مصنع"),              # factory
    ("keyword", "توزيع"),             # distribution
    # category-based targets.
    ("category", "استيراد وتصدير"),
    ("category", "factory-equipment-and-supplies"),
]

TARGET_ALIASES = {
    "import": "استيراد",
    "استيراد": "استيراد",
    "export": "تصدير",
    "تصدير": "تصدير",
    "factory": "مصنع",
    "مصنع": "مصنع",
    "distribution": "توزيع",
    "توزيع": "توزيع",
    "import-&-export": "استيراد وتصدير",
    "استيراد وتصدير": "استيراد وتصدير",
    "factory-equipment-and-supplies": "factory-equipment-and-supplies",
}

# ---------------------------------------------------------------------------
# Egyptian city slugs known on yellowpages.com.eg
# An empty string means "no city filter" (nationwide).
# ---------------------------------------------------------------------------
AR_IMPORT = "\u0627\u0633\u062a\u064a\u0631\u0627\u062f"
AR_EXPORT = "\u062a\u0635\u062f\u064a\u0631"
AR_FACTORY = "\u0645\u0635\u0646\u0639"
AR_DISTRIBUTION = "\u062a\u0648\u0632\u064a\u0639"
AR_IMPORT_EXPORT = "\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0648\u062a\u0635\u062f\u064a\u0631"

TARGETS = [
    ("keyword", AR_IMPORT),
    ("keyword", AR_EXPORT),
    ("keyword", AR_FACTORY),
    ("keyword", AR_DISTRIBUTION),
    ("category", AR_IMPORT_EXPORT),
    ("category", "factory-equipment-and-supplies"),
]

TARGET_ALIASES = {
    "import": AR_IMPORT,
    AR_IMPORT: AR_IMPORT,
    "export": AR_EXPORT,
    AR_EXPORT: AR_EXPORT,
    "factory": AR_FACTORY,
    AR_FACTORY: AR_FACTORY,
    "distribution": AR_DISTRIBUTION,
    AR_DISTRIBUTION: AR_DISTRIBUTION,
    "import-&-export": AR_IMPORT_EXPORT,
    AR_IMPORT_EXPORT: AR_IMPORT_EXPORT,
    "factory-equipment-and-supplies": "factory-equipment-and-supplies",
}

CITY_SLUGS = [
    "",               # nationwide (no city filter)
    "cairo",
    "giza",
    "alexandria",
    "qalyubia",
    "sharqia",
    "dakahlia",
    "beheira",
    "monufia",
    "gharbia",
    "kafr-el-sheikh",
    "port-said",
    "ismailia",
    "suez",
    "faiyum",
    "beni-suef",
    "minya",
    "asyut",
    "sohag",
    "qena",
    "aswan",
    "luxor",
    "red-sea",
    "north-sinai",
    "south-sinai",
    "matruh",
    "new-valley",
    "damietta",
    "menofia",
]

YP_PAGE_SIZE = 20


def _label(target_type: str, slug: str, city: str) -> str:
    city_label = city or "nationwide"
    return f"[{target_type}:{slug}] city={city_label}"


def _split_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def _filter_targets(value: str | None) -> list[tuple[str, str]]:
    requested = _split_filter(value)
    if not requested:
        return TARGETS
    normalized = {TARGET_ALIASES.get(item, item) for item in requested}
    return [(target_type, slug) for target_type, slug in TARGETS if slug in normalized]


def _filter_cities(value: str | None) -> list[str]:
    requested = _split_filter(value)
    if not requested:
        return CITY_SLUGS
    normalized = {"": "nationwide", "nationwide": ""}.get
    wanted = {normalized(item, item) for item in requested}
    return [city for city in CITY_SLUGS if city in wanted]


def _resume_start_index(
    csv_path: Path,
    combos: list[tuple[str, str, str]],
) -> int:
    """Return the combo index to resume from based on persisted CSV target/city rows."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return 0

    last_row: dict[str, str] | None = None
    seen_combos: set[tuple[str, str, str]] = set()
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            last_row = row
            seen_combos.add(
                (
                    (row.get("target_type") or "").strip(),
                    (row.get("target_slug") or "").strip(),
                    (row.get("city_slug") or "").strip(),
                )
            )

    if not last_row:
        return 0

    last_combo = (
        (last_row.get("target_type") or "").strip(),
        (last_row.get("target_slug") or "").strip(),
        (last_row.get("city_slug") or "").strip(),
    )
    try:
        last_index = combos.index(last_combo)
    except ValueError:
        print(
            "[resume] Existing CSV found, but its last target/city is not in "
            "this run's filter set; starting from the first requested combo."
        )
        return 0

    for index, combo in enumerate(combos[:last_index]):
        if combo not in seen_combos:
            print(
                "[resume] Existing CSV uses a narrower filter than this run; "
                "resuming at the first requested target/city not present in the CSV."
            )
            return index
    return last_index


def _existing_page_resume(
    csv_path: Path,
    target_type: str,
    slug: str,
    city: str,
    *,
    page_size: int = YP_PAGE_SIZE,
) -> int:
    """Estimate the next listing page to request from rows already in the CSV."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return 1

    matching_rows = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (
                (row.get("target_type") or "").strip() == target_type
                and (row.get("target_slug") or "").strip() == slug
                and (row.get("city_slug") or "").strip() == city
            ):
                matching_rows += 1

    if matching_rows <= 0:
        return 1
    return (matching_rows // page_size) + 1


class CompositeWriter:
    """Write to CSV and the shared database without creating duplicate business rows."""

    refresh_existing = True

    def __init__(self, writers: list[object]) -> None:
        self._writers = writers

    def write(self, result: object) -> int:
        return sum(int(getattr(writer, "write")(result)) for writer in self._writers)

    def has_url(self, source_url: str) -> bool:
        statuses = [
            bool(getattr(writer, "has_url")(source_url))
            for writer in self._writers
            if callable(getattr(writer, "has_url", None))
        ]
        return bool(statuses and all(statuses))

    def write_facets(self, source_url: str, facets: object) -> int:
        total = 0
        for writer in self._writers:
            write_facets = getattr(writer, "write_facets", None)
            if callable(write_facets):
                total += int(write_facets(source_url, facets))
        return total

    def close(self) -> None:
        for writer in self._writers:
            close = getattr(writer, "close", None)
            if callable(close):
                close()

    @property
    def seen_count(self) -> int:
        return max(
            [int(getattr(writer, "seen_count", 0)) for writer in self._writers],
            default=0,
        )


def _build_writer(csv_path: Path, db_path: str | None, no_db_sync: bool) -> CompositeWriter | CSVWriter:
    csv_writer = CSVWriter(csv_path)
    if no_db_sync:
        return csv_writer

    from scraper.config import Settings

    cfg = Settings()
    active_target = storage_target(db_path, cfg)
    if not is_postgres_url(active_target):
        print("[info] DATABASE_URL is not set; local run will write CSV only.")
        return csv_writer

    from scraper.postgres_writer import PostgresWriter

    print("[info] DATABASE_URL detected; mirroring local scrape into shared Supabase/Postgres.")
    return CompositeWriter([csv_writer, PostgresWriter(str(active_target))])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local YellowPages scraper - import/export/factory/distribution"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Max listing pages per target/city combo (default: 50)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: output/local_scrape_<timestamp>.csv)",
    )
    parser.add_argument(
        "--targets",
        type=str,
        default=None,
        help=(
            "Comma-separated target filter, e.g. import,factory or "
            "factory-equipment-and-supplies"
        ),
    )
    parser.add_argument(
        "--cities",
        type=str,
        default=None,
        help="Comma-separated city filter, e.g. nationwide,cairo,giza",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Optional explicit database target. Defaults to DATABASE_URL when set.",
    )
    parser.add_argument(
        "--no-db-sync",
        action="store_true",
        help="Write CSV only, even when DATABASE_URL is configured.",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=2.0,
        help="Min seconds between requests (default: 2.0)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=6.0,
        help="Max seconds between requests (default: 6.0)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start from the first requested target/city even if the output CSV already exists.",
    )
    args = parser.parse_args()

    # --- Output path ---
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.output:
        csv_path = Path(args.output)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = output_dir / f"local_scrape_{stamp}.csv"

    # --- Build pipeline (no browser tier for local run) ---
    pipeline = Pipeline(tiers=[Tier1Client(), Tier2Client()])
    rate_limiter = RateLimiter(min_delay=args.min_delay, max_delay=args.max_delay)
    proxy_pool = ProxyPool([], checker=lambda _: True)
    csv_writer = _build_writer(csv_path, args.db_path, args.no_db_sync)
    targets = _filter_targets(args.targets)
    city_slugs = _filter_cities(args.cities)
    if not targets:
        raise SystemExit(f"No targets matched --targets={args.targets!r}")
    if not city_slugs:
        raise SystemExit(f"No cities matched --cities={args.cities!r}")

    combos = [
        (target_type, slug, city)
        for target_type, slug in targets
        for city in city_slugs
    ]
    total_combos = len(combos)
    resume_index = 0
    skipped_combos = resume_index
    print(f"\n{'='*70}")
    print("  YellowPages Egypt - Local Scraper")
    print(f"{'='*70}")
    print(f"  Targets   : {len(targets)} ({', '.join(s for _, s in targets)})")
    print(f"  Cities    : {len(city_slugs)} (including nationwide)")
    print(f"  Combos    : {total_combos}")
    if csv_path.exists() and not args.no_resume:
        print("  Resume    : page-aware from existing CSV rows")
    elif args.no_resume:
        print("  Resume    : disabled")
    print(f"  Max pages : {args.max_pages} per combo")
    print(f"  Output    : {csv_path}")
    print(f"{'='*70}\n")

    grand_total = 0
    combo_num = skipped_combos

    current_target: str | None = None
    target_total = 0
    for target_type, slug, city in combos[resume_index:]:
        if slug != current_target:
            if current_target is not None:
                print(f"    Subtotal for '{current_target}': {target_total} rows")
            current_target = slug
            target_total = 0
            print(f"\n>>> Target: [{target_type}] '{slug}'")

        combo_num += 1
        label = _label(target_type, slug, city)
        print(f"  ({combo_num}/{total_combos}) {label} ...", end=" ", flush=True)

        start_page = (
            1
            if args.no_resume
            else _existing_page_resume(csv_path, target_type, slug, city)
        )
        if start_page > args.max_pages:
            print(
                f"already has >= {args.max_pages} pages in CSV; skipping     "
            )
            continue

        def make_progress(lbl: str):
            def _cb(page: int, rows: int) -> None:
                print(f"\r  ({combo_num}/{total_combos}) {lbl} - page {page}, +{rows} rows   ", end="", flush=True)
            return _cb

        try:
            rows_written = scrape_target(
                target_type=target_type,
                slug=slug,
                city_slug=city if city else None,
                pipeline=pipeline,
                csv_writer=csv_writer,
                rate_limiter=rate_limiter,
                proxy_pool=proxy_pool,
                max_pages=args.max_pages,
                consecutive_empty_halt=3,
                consecutive_no_new_halt=5,
                progress_callback=make_progress(label),
                start_page=start_page,
            )
            print(f"\r  ({combo_num}/{total_combos}) {label} -> {rows_written} rows written     ")
            target_total += rows_written
            grand_total += rows_written

        except KeyboardInterrupt:
            print(f"\n\n[!] Interrupted at {label}. Partial results saved to: {csv_path}")
            print(f"    Total rows written so far: {grand_total}")
            sys.exit(0)
        except Exception as exc:
            print(f"\r  ({combo_num}/{total_combos}) {label} -> ERROR: {type(exc).__name__}: {exc}")

    if current_target is not None:
        print(f"    Subtotal for '{current_target}': {target_total} rows")

    print(f"\n{'='*70}")
    print(f"  DONE. Total rows written: {grand_total}")
    print(f"  Output: {csv_path}")
    print(f"{'='*70}\n")
    close = getattr(csv_writer, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":
    main()
