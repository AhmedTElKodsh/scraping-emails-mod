
# -*- coding: utf-8 -*-
"""
Audit script: compare scraped CSV against target YP search terms.
Run with: $env:PYTHONIOENCODING='utf-8'; python analyze_coverage.py
"""

import csv
import sys
import re
from collections import defaultdict

CSV_PATH = r"d:\AI Projects\Gentech\scraping-emails-mod\yp_export_20260512 (3).csv"

# All target search terms (en + ar) grouped by topic
TARGET_GROUPS = {
    "factory": {
        "en": ["factory", "factories"],
        "ar": ["مصنع", "مصانع"],
        "urls": [
            "https://yellowpages.com.eg/en/search/factory",
            "https://yellowpages.com.eg/ar/search/factory",
            "https://yellowpages.com.eg/en/category/factory-equipment-and-supplies",
        ],
    },
    "import": {
        "en": ["import", "importing"],
        "ar": ["استيراد"],
        "urls": [
            "https://yellowpages.com.eg/en/search/import",
            "https://yellowpages.com.eg/ar/search/import",
        ],
    },
    "export": {
        "en": ["export", "exporting"],
        "ar": ["تصدير"],
        "urls": [
            "https://yellowpages.com.eg/en/search/export",
            "https://yellowpages.com.eg/ar/search/export",
        ],
    },
    "import_export": {
        "en": ["import & export", "import-&-export", "import and export", "import export"],
        "ar": ["استيراد وتصدير", "استيراد و تصدير"],
        "urls": [
            "https://yellowpages.com.eg/en/category/import-&-export",
            "https://yellowpages.com.eg/ar/category/import-&-export",
        ],
    },
    "distribution": {
        "en": ["distribution", "distributor", "distributors"],
        "ar": ["توزيع", "موزع", "موزعين"],
        "urls": [
            "https://yellowpages.com.eg/ar/search/distribution",
        ],
    },
}

# YP actual result counts from live site (confirmed above)
YP_LIVE_COUNTS = {
    "factory": 1018,
    "import": "~unknown",
    "export": "~unknown",
    "import_export": "~unknown",
    "distribution": "~unknown",
}


def load_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def get_searchable_text(row):
    """Combine all relevant columns into one searchable string."""
    cols = [
        row.get("Categories", ""),
        row.get("Keywords", ""),
        row.get("matched_facets", ""),
        row.get("category_slugs", ""),
        row.get("categories_ar", ""),
        row.get("Category", ""),
        row.get("Keyword", ""),
    ]
    return " | ".join(c for c in cols if c).lower()


def term_found_in(text, terms):
    """Check if any of the terms appear in text (case-insensitive for en, exact substring for ar)."""
    for t in terms:
        if t.lower() in text:
            return True
    return False


def analyze(rows):
    total = len(rows)
    print(f"\nTotal rows in CSV: {total}")
    print("=" * 70)

    results = {}
    for group_name, group_data in TARGET_GROUPS.items():
        en_terms = group_data["en"]
        ar_terms = group_data["ar"]
        all_terms = en_terms + ar_terms

        matched_rows = []
        for row in rows:
            text = get_searchable_text(row)
            if term_found_in(text, all_terms):
                matched_rows.append(row)

        results[group_name] = matched_rows

        live_count = YP_LIVE_COUNTS.get(group_name, "?")
        scraped_count = len(matched_rows)
        pct = (scraped_count / total * 100) if total > 0 else 0

        print(f"\n{'=' * 70}")
        print(f"TOPIC: {group_name.upper().replace('_', ' ')}")
        print(f"  YP live results:   {live_count}")
        print(f"  Scraped matches:   {scraped_count}  ({pct:.1f}% of CSV)")
        print(f"  URLs checked:")
        for url in group_data["urls"]:
            print(f"    - {url}")

        if scraped_count == 0:
            print(f"  *** COMPLETELY MISSING from CSV! ***")
        elif isinstance(live_count, int) and scraped_count < live_count:
            gap = live_count - scraped_count
            print(f"  *** SIGNIFICANT GAP: {gap} records missing (captured {scraped_count}/{live_count}) ***")
        else:
            print(f"  Status: Data present")

        # Show sample matched rows
        if matched_rows:
            print(f"\n  Sample matches (first 5):")
            for r in matched_rows[:5]:
                name = r.get("Name", r.get("name", r.get("Company Name", "N/A")))
                cats = r.get("Categories", r.get("Category", ""))
                kws = r.get("Keywords", r.get("Keyword", r.get("matched_facets", "")))
                print(f"    - {name[:60]}")
                print(f"        Cat: {cats[:80]}")
                print(f"        KW : {kws[:80]}")

    # Cross-analysis
    print(f"\n{'=' * 70}")
    print("CROSS-TOPIC SUMMARY")
    print(f"{'=' * 70}")

    all_matched_ids = set()
    for group_name, matched_rows in results.items():
        count = len(matched_rows)
        live = YP_LIVE_COUNTS.get(group_name, "?")
        status = "MISSING" if count == 0 else (f"GAP: {live - count}" if isinstance(live, int) and count < live else "OK")
        print(f"  {group_name:<20} scraped={count:<5} live={str(live):<8} {status}")
        for r in matched_rows:
            row_id = r.get("id", r.get("Name", r.get("Company Name", str(id(r)))))
            all_matched_ids.add(row_id)

    covered = len(all_matched_ids)
    print(f"\n  Total unique rows matching ANY target term: {covered} / {total}")
    print(f"  Rows with NO target terms: {total - covered}")


def show_csv_columns(rows):
    if rows:
        print("\nCSV COLUMNS DETECTED:")
        for col in rows[0].keys():
            sample = rows[0].get(col, "")[:60]
            print(f"  '{col}': {sample!r}")


def main():
    print("Loading CSV...")
    rows = load_csv(CSV_PATH)
    show_csv_columns(rows)
    analyze(rows)


if __name__ == "__main__":
    main()
