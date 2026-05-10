# Yellow Pages Taxonomy, Target Crawling, and Filtered Results UI Plan

**Target Markdown File:** `docs/superpowers/plans/2026-05-09-yellowpages-taxonomy-targets-ui.md`

## Summary

Build on the existing Yellow Pages Egypt scraper so it can scrape and store selectable filters for:

- Categories from https://yellowpages.com.eg/en/related-categories
- Brands from https://yellowpages.com.eg/en/related-brands
- Keywords from https://yellowpages.com.eg/en/keywords.html
- Locations from Yellow Pages result filter panels, starting with Cities and then Areas/Districts using `data-cityid` / `data-areaid` when available

The Streamlit UI will let users select saved taxonomy filters and show already-scraped business results that match them.

Current repo facts: `src/scraper/taxonomy.py` has a live-refresh stub, `yellowpages_eg.py` scrapes category listing pages, SQLite currently stores one `category_slug` and `city_slug` per business, and `app/streamlit_app.py` already has a basic read-only category/city UI.

## Key Changes

- Add taxonomy scraping in `src/scraper/taxonomy.py`:
  - Parse category links matching `/en/category/{slug}` plus display counts from `Name (123)`.
  - Parse brand links matching `/en/brand/{slug}` plus display counts.
  - Parse keyword links matching `/en/keyword/{keyword-slug}`; keyword index pages paginate as `/en/pN/keywords.html`.
  - Follow pager `Last` links for category and brand indexes; stop when no new items are found.
  - Parse location filters from result pages via `input.locations_filter`:
    - city: class `cities_filter`, value is external location id
    - area: class `areas_filter`, `data-cityid` gives parent city external id
    - district: class `district_filter`, `data-areaid` gives parent area external id

- Extend SQLite schema in `src/scraper/db.py`:
  - Add `brands(slug, name, result_count, href, scraped_at)`.
  - Add `keywords(slug, name, href, scraped_at)`.
  - Extend `locations` with `external_id`, `result_count`, and parent support by slug.
  - Add `business_facets(source_url, facet_type, slug, name)` with facet types `category`, `brand`, `keyword`, `city`, `area`, `district`.
  - Evolve `scrape_jobs` from category-only to `target_type`, `target_slug`, optional `city_slug`, and status fields; keep migration logic idempotent for existing DBs.

- Generalize Yellow Pages crawling in `src/scraper/sites/yellowpages_eg.py`:
  - Introduce `build_target_url(target_type, slug, page)` for `category`, `brand`, and `keyword`.
  - Replace category-only crawl internals with `scrape_target(target_type, slug, city_slug, ...)`.
  - Keep `scrape_category(...)` as a compatibility wrapper.
  - Parse listing cards, not only profile URLs, so each saved business also records visible category/brand/keyword facets from the result card.
  - Always attach the source target facet and selected city facet to rows written during that crawl.

- Update writers and models:
  - Add a small `Facet` model and `ScrapeResult.facets`.
  - Update `SQLiteWriter.write()` to insert/ignore the business row, then upsert all facets for `result.url`.
  - Keep `businesses.source_url` as the dedup authority.

- Update CLI and mass crawl:
  - `scraper taxonomy` refreshes categories, brands, keywords, and cities by default; `--seed-only` remains supported.
  - `scraper scrape TARGET --target-type category|brand|keyword --city CITY_SLUG_OR_ID` scrapes one selected target.
  - `scraper crawl-all --target-types category,brand,keyword --cities all|top` creates generic jobs using the new job key.
  - `--dry-run` prints target/job counts without crawling.

- Rework `app/streamlit_app.py`:
  - Sidebar filters: Category, Brand, Keyword, City; Area/District appear when taxonomy has parent mappings.
  - Use searchable `st.multiselect` controls because lists can be large, especially brands.
  - Results query joins `business_facets`; OR within each selected group, AND across groups.
  - Show saved results only: business name, phone, email, website, address, source URL, scraped date, and matched facets.
  - Keep CSV export for the currently filtered rows.
  - Keep crawl status, but report generic target jobs instead of category/city-only jobs.

## Test Plan

- Baseline already checked with `python -m pytest tests/unit/test_taxonomy.py tests/unit/test_yp_parser.py tests/unit/test_db.py tests/unit/test_sqlite_writer.py -q`: 26 passed.
- Add parser fixture tests for:
  - related categories page with pager and counts
  - related brands page with pager and counts
  - keywords page with `/en/pN/keywords.html` pager
  - location filters for city, area, and district parent IDs
  - listing-card facet extraction from category/brand/keyword anchors
- Add DB tests for new tables, idempotent migrations, and `business_facets` uniqueness.
- Add SQLite writer tests proving duplicate businesses can still gain new facets from later crawls.
- Add CLI tests for taxonomy refresh options and generic crawl dry-run job creation.
- Add Streamlit query helper tests for filtering by one group and by multiple groups together.

## Assumptions

- V1 location crawling exposes Cities as the required location filter; Areas and Districts are parsed and stored when parent IDs are available, then exposed in UI only when mappings are reliable.
- Existing CSV output remains supported for single runs, but SQLite is the source of truth for the UI.
- Keyword result pages are crawled from their `/en/keyword/{slug}` URL and only paginated if the result page itself exposes pager links.
- The plan file should be saved at `docs/superpowers/plans/2026-05-09-yellowpages-taxonomy-targets-ui.md`.
