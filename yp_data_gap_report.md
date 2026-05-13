# Egypt Yellow Pages — Data Gap Analysis Report

**CSV File:** `yp_export_20260512 (3).csv`  
**Total rows in CSV:** 234  
**Analysis Date:** 2026-05-12

---

## Summary Table

| Topic | YP Live Results | Scraped Matches | Coverage % | Missing (~) | Status |
|---|---|---|---|---|---|
| **Factory** (`factory` / `مصنع`) | **1,018** | 229 | 22.5% | **789** | 🔴 CRITICAL GAP |
| **Import** (`import` / `استيراد`) | **2,595** | 2 | 0.1% | **2,593** | 🔴 CRITICAL GAP |
| **Export** (`export` / `تصدير`) | **2,107** | 1 | 0.05% | **2,106** | 🔴 CRITICAL GAP |
| **Import & Export** (category) | **1,172** | 1 | 0.09% | **1,171** | 🔴 CRITICAL GAP |
| **Distribution** (`توزيع`) | **641** | 1 | 0.2% | **640** | 🔴 CRITICAL GAP |

> [!CAUTION]
> **The CSV captures only ~234 records total. The five target topics alone represent 7,533+ live listings on Yellow Pages — meaning less than 4% of relevant data was captured.**

---

## Topic-by-Topic Breakdown

### 1. Factory (`factory` / `مصنع`)

- **YP Live Count:** 1,018 results at [`/en/search/factory`](https://yellowpages.com.eg/en/search/factory)
- **CSV Matches:** 229 rows (matched via `keyword: مصنع` in `matched_facets`)
- **Gap:** ~789 records missing
- **Root Cause:** The scraper only captured businesses where `مصنع` appeared as a keyword facet. It did NOT scrape:
  - Businesses from Arabic search URL (`/ar/search/factory`)
  - The dedicated category page (`/en/category/factory-equipment-and-supplies`)
  - Businesses where "factory" appears in the EN keyword but not in Arabic

### 2. Import (`import` / `استيراد`)

- **YP Live Count:** 2,595 results at [`/en/search/import`](https://yellowpages.com.eg/en/search/import)
- **CSV Matches:** 2 rows (only matching `Chemical Importer` keyword)
- **Gap:** ~2,593 records missing
- **Root Cause:** The `استيراد` / `import` search was **never scraped** as a standalone URL. The 2 matches are incidental.

### 3. Export (`export` / `تصدير`)

- **YP Live Count:** 2,107 results at [`/en/search/export`](https://yellowpages.com.eg/en/search/export)
- **CSV Matches:** 1 row (the same single Import & Export company)
- **Gap:** ~2,106 records missing
- **Root Cause:** Export search URLs were never scraped.

### 4. Import & Export (category)

- **YP Live Count:** 1,172 results at [`/en/category/import-&-export`](https://yellowpages.com.eg/en/category/import-&-export)
- **CSV Matches:** 1 row
- **Gap:** ~1,171 records missing
- **Root Cause:** Category URL was never targeted in the scrape.

### 5. Distribution (`توزيع`)

- **YP Live Count:** 641 results at [`/ar/search/distribution`](https://yellowpages.com.eg/ar/search/distribution)
- **CSV Matches:** 1 row (matched `Authorized Distributor` in business name)
- **Gap:** ~640 records missing
- **Root Cause:** Distribution search URL was never scraped.

---

## CSV Data Structure Findings

The CSV has **18 columns**, with the key ones being:

| Column | Content |
|---|---|
| `business_name` | English business name |
| `business_name_ar` | Arabic business name |
| `category_slug` | URL slug for category (mostly empty!) |
| `category_ar` | Arabic category name (mostly empty!) |
| `matched_facets` | Comma-separated facets: `category: X, city: Y, keyword: Z` |
| `source_url` | The YP profile URL scraped |

> [!WARNING]
> The `category_slug` and `category_ar` columns are **mostly empty** in the current CSV. All category/keyword information is crammed into the `matched_facets` string column, making it hard to filter by category.

---

## What Was Actually Scraped

The 234 rows appear to be from a **single search query** (`keyword: مصنع` — factory in Arabic) filtered to a few cities (Cairo, Giza). Evidence:
- 229/234 rows (97.9%) contain `keyword: مصنع` in `matched_facets`
- All records are from Cairo/Giza area
- Source tier is uniformly `1`

---

## Recommended Scraping Actions

To capture the missing data, the scraper needs to target these URLs:

| Priority | URL | Est. Records |
|---|---|---|
| 🔴 High | `https://yellowpages.com.eg/en/search/import` | 2,595 |
| 🔴 High | `https://yellowpages.com.eg/en/search/export` | 2,107 |
| 🔴 High | `https://yellowpages.com.eg/en/category/import-&-export` | 1,172 |
| 🔴 High | `https://yellowpages.com.eg/ar/category/import-&-export` | ~1,172 |
| 🔴 High | `https://yellowpages.com.eg/en/search/factory` (all pages) | 1,018 |
| 🟡 Medium | `https://yellowpages.com.eg/ar/search/factory` | ~1,018 |
| 🟡 Medium | `https://yellowpages.com.eg/ar/search/distribution` | 641 |
| 🟡 Medium | `https://yellowpages.com.eg/en/category/factory-equipment-and-supplies` | Unknown |
| 🟡 Medium | `https://yellowpages.com.eg/ar/search/import` | ~2,595 |
| 🟡 Medium | `https://yellowpages.com.eg/ar/search/export` | ~2,107 |

> [!TIP]
> **Total estimated missing records: ~7,300–8,000+**
> Current coverage of target searches: **< 4%**

---

## Notes on Overlap

- The `export`, `import`, and `import & export` searches likely have significant **overlap** (same companies appear in all three). The net unique companies is likely around **3,000–4,000** rather than 5,874 (2595+2107+1172).
- The factory category (1,018) is largely distinct from the import/export category.
- Distribution (641) may partially overlap with import/export companies.
