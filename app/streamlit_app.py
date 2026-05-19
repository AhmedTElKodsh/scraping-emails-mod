"""Streamlit UI for saved Yellow Pages Egypt scrape results."""

# ruff: noqa: E402

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

import pandas as pd
import streamlit as st

from app.crawl_plan import build_crawl_plan
from app.data_access import (
    ensure_seed_taxonomy,
    get_last_crawl_time,
    load_businesses,
    load_crawl_progress,
    load_crawl_target_options,
    load_database_stats,
    load_facet_options,
    load_job_summary,
    load_matching_jobs,
)
from scraper.config import Settings

st.set_page_config(page_title="YP Egypt Scraper", layout="wide")


def _apply_streamlit_secret_env() -> None:
    try:
        database_url = st.secrets.get("DATABASE_URL") or st.secrets.get("database_url")
    except Exception:
        return
    if database_url and not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = str(database_url)


_apply_streamlit_secret_env()
cfg = Settings()
# Prioritize DATABASE_URL (Supabase) over local SQLite
DB_PATH = cfg.database_url or getattr(cfg, "db_path", "data/scraper.sqlite")
AUTO_REFRESH_SECONDS = 15

# Determine database type for display
from scraper.storage import is_postgres_url
IS_USING_SUPABASE = is_postgres_url(DB_PATH)
SEED_WAS_LOADED = ensure_seed_taxonomy(
    DB_PATH,
    getattr(cfg, "taxonomy_seed_path", "data/taxonomy_seed.json"),
)

st.markdown(
    """
    <style>
    .crawl-live {
        align-items: center;
        display: flex;
        gap: 0.55rem;
        margin: 0.25rem 0 0.6rem;
    }
    .crawl-spinner {
        animation: crawlspin 0.9s linear infinite;
        border: 2px solid rgba(49, 130, 206, 0.22);
        border-top-color: #3182ce;
        border-radius: 50%;
        height: 0.9rem;
        width: 0.9rem;
    }
    .crawl-live-text {
        color: #8ec5ff;
        font-size: 0.9rem;
        font-weight: 600;
    }
    .crawl-detail {
        color: rgba(250, 250, 250, 0.72);
        font-size: 0.82rem;
        line-height: 1.45;
        margin-top: -0.25rem;
    }
    div[data-testid="stDataFrame"] {
        font-size: 0.78rem;
    }
    @keyframes crawlspin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _option_labels(rows: list[dict[str, Any]]) -> dict[str, str]:
    labels = {}
    for row in rows:
        name = row["name"]
        name_ar = row.get("name_ar") or ""
        display_name = f"{name} / {name_ar}" if name_ar and name_ar != name else name
        label = f"{display_name} ({row['slug']})"
        result_count = row.get("count") or row.get("result_count")
        if result_count:
            label = f"{label} - {result_count}"
        labels[label] = row["slug"]
    return labels


def _selected_slugs(label_to_slug: dict[str, str], selected: list[str]) -> list[str]:
    return [label_to_slug[label] for label in selected if label in label_to_slug]


def _prune_multiselect_state(key: str, options: list[str]) -> None:
    valid_options = set(options)
    selected = st.session_state.get(key, [])
    if not isinstance(selected, list):
        st.session_state[key] = []
        return
    st.session_state[key] = [value for value in selected if value in valid_options]


def _sidebar_multiselect(
    label: str,
    options: list[str],
    *,
    key: str,
    disabled: bool = False,
) -> list[str]:
    _prune_multiselect_state(key, options)
    return st.sidebar.multiselect(label, options, key=key, disabled=disabled)


@st.cache_resource
def _crawl_runtime() -> dict[str, Any]:
    return {
        "thread": None,
        "lock": threading.Lock(),
        "last_error": "",
        "last_result": None,
    }


def _thread_is_alive(thread: threading.Thread | None) -> bool:
    return bool(thread and thread.is_alive())


def _start_crawl_thread(
    *,
    db_path: str,
    max_pages: int,
    target_types: list[str],
    target_slugs_by_type: dict[str, list[str]] | None,
    cities: str,
    city_slugs: list[str] | None,
) -> bool:
    runtime = _crawl_runtime()
    with runtime["lock"]:
        if _thread_is_alive(runtime["thread"]):
            return False
        runtime["last_error"] = ""
        runtime["last_result"] = None

        def crawl_thread() -> None:
            try:
                from scraper.mass_crawl import run_mass_crawl

                runtime["last_result"] = run_mass_crawl(
                    db_path=db_path,
                    max_pages=max_pages,
                    headless=False,
                    resume=True,
                    target_types=target_types,
                    target_slugs_by_type=target_slugs_by_type,
                    cities=cities,
                    city_slugs=city_slugs,
                )
            except Exception as exc:  # pragma: no cover - defensive background guard
                runtime["last_error"] = f"{type(exc).__name__}: {exc}"

        thread = threading.Thread(target=crawl_thread, daemon=True, name="yp-crawl")
        runtime["thread"] = thread
        thread.start()
        return True


def _crawl_runtime_snapshot() -> dict[str, Any]:
    runtime = _crawl_runtime()
    with runtime["lock"]:
        return {
            "alive": _thread_is_alive(runtime["thread"]),
            "last_error": runtime["last_error"],
            "last_result": runtime["last_result"],
        }


st.sidebar.title("Filters")

# Show last update time in sidebar
last_update = get_last_crawl_time(DB_PATH)
if last_update:
    st.sidebar.caption(f"🕒 Last updated: {last_update}")

if SEED_WAS_LOADED:
    st.session_state["starter_taxonomy_loaded"] = True

if st.session_state.get("starter_taxonomy_loaded"):
    st.sidebar.success("Loaded starter taxonomy for this fresh deployment.")

filter_options = load_crawl_target_options(DB_PATH)
category_options = _option_labels(filter_options["categories"])
brand_options = _option_labels(filter_options["brands"])
keyword_options = _option_labels(filter_options["keywords"])
city_options = _option_labels(filter_options["cities"])

# Only show the allowed import/export/factory/distribution scope.
ALLOWED_KEYWORDS = {"استيراد", "تصدير", "استيراد وتصدير", "مصنع", "توزيع"}
ALLOWED_CATEGORIES = {"import-&-export", "factory-equipment-and-supplies"}
restricted_category_options = {
    label: slug for label, slug in category_options.items() if slug in ALLOWED_CATEGORIES
}
restricted_keyword_options = {
    label: slug for label, slug in keyword_options.items() if slug in ALLOWED_KEYWORDS
}

selected_categories: list[str] = []
if restricted_category_options:
    selected_categories = _sidebar_multiselect(
        "Categories",
        list(restricted_category_options.keys()),
        key="selected_categories",
    )

selected_brands: list[str] = []
if brand_options:
    selected_brands = _sidebar_multiselect(
        "Brands",
        list(brand_options.keys()),
        key="selected_brands",
    )

selected_keywords: list[str] = []
if restricted_keyword_options:
    selected_keywords = _sidebar_multiselect(
        "Keywords",
        list(restricted_keyword_options.keys()),
        key="selected_keywords",
    )
    if selected_keywords:
        st.sidebar.caption(
            "ℹ️ Arabic keywords automatically include English equivalents "
            "(e.g., 'مصنع' includes 'factory')"
        )
selected_cities = _sidebar_multiselect(
    "Cities",
    list(city_options.keys()),
    key="selected_cities",
)

selected_city_slugs = _selected_slugs(city_options, selected_cities)

area_options: dict[str, str] = {}
if len(selected_city_slugs) == 1:
    area_options = _option_labels(load_facet_options(DB_PATH, "area", selected_city_slugs[0]))
selected_areas: list[str] = []
if area_options:
    selected_areas = _sidebar_multiselect(
        "Areas",
        list(area_options.keys()),
        key="selected_areas",
    )
selected_area_slugs = _selected_slugs(area_options, selected_areas)

district_options: dict[str, str] = {}
if len(selected_area_slugs) == 1:
    district_options = _option_labels(
        load_facet_options(DB_PATH, "district", selected_area_slugs[0])
    )
selected_districts: list[str] = []
if district_options:
    selected_districts = _sidebar_multiselect(
        "Districts",
        list(district_options.keys()),
        key="selected_districts",
    )

search_query = ""

filters = {
    "category": _selected_slugs(restricted_category_options, selected_categories),
    "brand": _selected_slugs(brand_options, selected_brands),
    "keyword": _selected_slugs(restricted_keyword_options, selected_keywords),
    "city": selected_city_slugs,
    "area": selected_area_slugs,
    "district": _selected_slugs(district_options, selected_districts),
}

_EXPANSION_MAP = {
    "مصنع": ["factory", "factories", "factory-equipment-and-supplies"],
    "استيراد": ["import"],
    "تصدير": ["export"],
    "استيراد وتصدير": ["import-&-export", "import-export", "import export", "استيراد-وتصدير"],
    "توزيع": ["distribution"],
}


def _expand_keywords(slugs: set[str]) -> set[str]:
    result = set(slugs)
    for arabic, english_slugs in _EXPANSION_MAP.items():
        if arabic in result:
            result.update(english_slugs)
    return result


# Expand Arabic keywords to include their English equivalents for scraping
expanded_keywords = _expand_keywords(set(filters["keyword"]))
target_slugs_by_type = {
    target_type: slugs
    for target_type, slugs in {
        "category": filters["category"],
        "brand": filters["brand"],
        "keyword": list(expanded_keywords),
    }.items()
    if slugs
}
default_expanded_keywords = _expand_keywords(set(restricted_keyword_options.values()))
default_target_slugs_by_type = {
    "category": ["import-&-export", "factory-equipment-and-supplies"],
    "keyword": list(default_expanded_keywords),
}
crawl_plan = build_crawl_plan(
    target_slugs_by_type,
    filters["city"],
    default_target_slugs_by_type,
)

st.title("YellowPages Egypt - Business Contacts")

# Show database connection status
if IS_USING_SUPABASE:
    st.success("🌐 Connected to Supabase (Cloud Database) - All data is synchronized online")
else:
    st.warning("💾 Using Local SQLite Database - Data is stored locally only")

# Database Statistics Dashboard
with st.expander("📊 Database Statistics", expanded=False):
    stats = load_database_stats(DB_PATH)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Businesses", f"{stats['total_businesses']:,}")
    with col2:
        st.metric("With Arabic Names", f"{stats['arabic_businesses']:,}")
    with col3:
        st.metric("With Emails", f"{stats['businesses_with_email']:,}")
    with col4:
        st.metric("With Phones", f"{stats['businesses_with_phone']:,}")
    
    col5, col6 = st.columns(2)
    with col5:
        st.metric("Unique Categories", f"{stats['unique_categories']:,}")
    with col6:
        st.metric("Unique Cities", f"{stats['unique_cities']:,}")
    
    # Data quality percentages
    if stats['total_businesses'] > 0:
        email_rate = (stats['businesses_with_email'] / stats['total_businesses']) * 100
        phone_rate = (stats['businesses_with_phone'] / stats['total_businesses']) * 100
        arabic_rate = (stats['arabic_businesses'] / stats['total_businesses']) * 100
        
        st.caption(
            f"📈 Data Quality: "
            f"{email_rate:.1f}% have emails | "
            f"{phone_rate:.1f}% have phones | "
            f"{arabic_rate:.1f}% have Arabic names"
        )
    
    # Last update time
    last_update = get_last_crawl_time(DB_PATH)
    if last_update:
        st.caption(f"🕒 Last updated: {last_update}")

with st.expander("Crawl Status"):
    summary = load_job_summary(DB_PATH)
    if summary:
        for row in summary:
            st.write(
                f"**{row['target_type']} / {row['status']}**: "
                f"{row['jobs']} jobs, {row['pages_scraped'] or 0} pages checked, "
                f"{row['rows_written'] or 0} new rows"
            )
    else:
        st.info("No crawl jobs yet.")

progress = load_crawl_progress(DB_PATH)
runtime_snapshot = _crawl_runtime_snapshot()
active_crawl = runtime_snapshot["alive"] or progress["running_jobs"] > 0
crawl_button_label = "Run Scoped Crawl" if crawl_plan.is_scoped else "Run Full Dataset Crawl"
crawl_started_this_run = False

if st.sidebar.button(crawl_button_label, disabled=active_crawl, key="run_crawl_button"):
    started = _start_crawl_thread(
        db_path=DB_PATH,
        max_pages=cfg.mass_crawl_max_pages,
        target_types=crawl_plan.target_types,
        target_slugs_by_type=crawl_plan.target_slugs_by_type,
        cities=crawl_plan.cities,
        city_slugs=crawl_plan.city_slugs,
    )
    crawl_started_this_run = started
    if started and crawl_plan.is_scoped:
        st.session_state["crawl_status_message"] = (
            "Scoped crawl resumed. Completed jobs are skipped and interrupted jobs continue from saved progress."
        )
    elif started:
        st.session_state["crawl_status_message"] = (
            "Full dataset crawl resumed. Completed jobs are skipped and interrupted jobs continue from saved progress."
        )
    else:
        st.session_state["crawl_status_message"] = "A crawl is already running."

runtime_snapshot = _crawl_runtime_snapshot()
active_crawl = crawl_started_this_run or runtime_snapshot["alive"] or progress["running_jobs"] > 0

if st.session_state.get("crawl_status_message"):
    st.sidebar.success(st.session_state["crawl_status_message"])

def _render_live_crawl_status() -> None:
    live_progress = load_crawl_progress(DB_PATH)
    live_runtime = _crawl_runtime_snapshot()
    live_active = live_runtime["alive"] or live_progress["running_jobs"] > 0

    if live_runtime["last_error"]:
        st.error(f"Crawl failed: {live_runtime['last_error']}")

    if live_active:
        st.markdown(
            f"""
            <div class="crawl-live">
                <span class="crawl-spinner"></span>
                <span class="crawl-live-text">Crawler is adding data</span>
            </div>
            <div class="crawl-detail">
                Auto-refreshes every {AUTO_REFRESH_SECONDS} seconds.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if live_progress["total_jobs"]:
        completed = live_progress["done_jobs"]
        total = live_progress["total_jobs"]
        running_page_fraction = min(
            live_progress["pages_checked"] / max(cfg.mass_crawl_max_pages, 1),
            live_progress["running_jobs"],
        )
        ratio = min((completed + running_page_fraction) / total, 1.0)
        status_text = f"{completed:,} of {total:,} crawl jobs complete ({ratio:.1%})"
        st.progress(ratio, text=status_text)
        st.caption(
            f"{live_progress['business_count']:,} businesses saved | "
            f"{live_progress['recent_business_count']:,} added in last 10 min | "
            f"{live_progress['running_jobs']:,} running | "
            f"{live_progress['pending_jobs']:,} queued | "
            f"{live_progress['failed_jobs']:,} failed"
        )
        st.caption(
            "Rows count newly saved unique businesses; completed jobs are skipped on resume."
        )
        if live_active:
            st.info(
                f"{live_progress['pages_checked']:,} pages checked and "
                f"{live_progress['rows_written']:,} new rows recorded across the crawl queue."
            )
        if live_progress["running_jobs"]:
            with st.expander("Running Now", expanded=True):
                for job in live_progress["current_jobs"]:
                    city = job["city_slug"] or "all cities"
                    st.write(f"**{job['target_type']}**: {job['target_slug']} ({city})")
                    st.caption(
                        f"{job.get('matching_saved_businesses', 0):,} saved matches available now"
                    )
        if live_progress["failed_jobs"]:
            st.warning("Some crawl jobs failed. They will be retried on the next run.")
    elif live_active:
        st.progress(0, text="Preparing crawl queue...")
        st.info(
            "Creating crawl jobs from the saved taxonomy. This will update automatically."
        )
    elif live_runtime["last_result"] == 0:
        st.info(
            "The last crawl finished without new rows. "
            "Check taxonomy and filters if this was unexpected."
        )


with st.sidebar:
    if active_crawl:
        @st.fragment(run_every=f"{AUTO_REFRESH_SECONDS}s")
        def _render_live_crawl_status_fragment() -> None:
            _render_live_crawl_status()

        _render_live_crawl_status_fragment()
    else:
        _render_live_crawl_status()

if st.sidebar.button("Refresh Log", key="refresh_log_button"):
    log_path = Path("data/crawl.log")
    if log_path.exists():
        st.code(log_path.read_text(encoding="utf-8")[-2000:], language="text")

def _render_data_table() -> None:
    businesses = load_businesses(DB_PATH, filters, search_query=search_query, limit=1_000_000)

    if not businesses:
        matching_jobs = load_matching_jobs(
            DB_PATH,
            target_slugs_by_type,
            filters["city"],
        )
        if target_slugs_by_type and not matching_jobs:
            st.info(
                "No saved businesses for the selected taxonomy yet. "
                "Click 'Run Scoped Crawl' above to fetch them."
            )
        elif matching_jobs and any(job["status"] == "running" for job in matching_jobs):
            st.info("The selected crawl is running. Refresh shortly to see newly saved businesses.")
        elif matching_jobs and all(job["status"] == "pending" for job in matching_jobs):
            st.info("The selected crawl is queued. Use Run Scoped Crawl to prioritize it.")
        elif matching_jobs and any(job["status"] == "failed" for job in matching_jobs):
            st.info("The selected crawl has failed jobs. Check the crawl log before retrying.")
        elif (
            matching_jobs
            and all(job["status"] == "done" for job in matching_jobs)
            and all((job["rows_written"] or 0) == 0 for job in matching_jobs)
        ):
            saved_matches = sum(job.get("matching_saved_businesses", 0) for job in matching_jobs)
            if saved_matches:
                st.info(
                    f"The selected crawl is complete. {saved_matches:,} saved businesses "
                    "already match this selection."
                )
            else:
                st.info("The selected crawl job completed, but wrote 0 businesses.")
        elif matching_jobs:
            st.info("Saved businesses exist for this crawl, but none match all selected filters.")
        else:
            st.info("No saved businesses match the selected filters. Try clearing filters or running a crawl.")
    else:
        df = pd.DataFrame(businesses)
        columns = [
            "business_name_ar",
            "phone",
            "email",
            "address_ar",
            "category_ar",
            "governorate",
            "governorate_ar",
            "city_slug",
            "facet_categories",
            "facet_keywords",
            "facet_cities",
            "source_url",
            "matched_facets",
            "scraped_at",
        ]
        visible_columns = [column for column in columns if column in df.columns]
        total_count = len(df)
        
        # Calculate data quality metrics for filtered results
        email_count = df["email"].notna().sum() if "email" in df.columns else 0
        phone_count = df["phone"].notna().sum() if "phone" in df.columns else 0
        arabic_count = df["business_name_ar"].notna().sum() if "business_name_ar" in df.columns else 0
        
        email_rate = (email_count / total_count * 100) if total_count > 0 else 0
        phone_rate = (phone_count / total_count * 100) if total_count > 0 else 0
        arabic_rate = (arabic_count / total_count * 100) if total_count > 0 else 0
        
        st.write(f"**{total_count:,}** businesses found")
        st.caption(
            f"📊 Filtered Data Quality: "
            f"{email_rate:.1f}% have emails ({email_count:,}) | "
            f"{phone_rate:.1f}% have phones ({phone_count:,}) | "
            f"{arabic_rate:.1f}% have Arabic names ({arabic_count:,})"
        )
        
        # Keep Arabic column names to make it clear we're showing Arabic data
        display_df = df[visible_columns].rename(columns={
            "business_name_ar": "اسم الشركة (Business Name)",
            "address_ar": "العنوان (Address)",
            "category_ar": "الفئة (Category)",
            "governorate": "Governorate",
            "governorate_ar": "المحافظة (Governorate)",
            "city_slug": "City Slug",
            "facet_categories": "Category Slugs",
            "facet_keywords": "Keyword Slugs",
            "facet_cities": "City Facets",
            "phone": "الهاتف (Phone)",
            "email": "البريد الإلكتروني (Email)",
            "source_url": "رابط المصدر (Source URL)",
            "matched_facets": "التصنيفات (Categories)",
            "scraped_at": "تاريخ الجمع (Scraped Date)",
        })
        st.dataframe(display_df, width="stretch")

        # Regular filtered CSV export (keep original column names for CSV)
        csv_df = df[visible_columns].drop_duplicates(subset=["source_url"])
        csv_data = csv_df.to_csv(index=False).encode("utf-8-sig")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Download Filtered CSV",
                csv_data,
                f"yp_filtered_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv; charset=utf-8-sig",
                key="download_csv_button",
                help="Downloads businesses matching current filters (up to 1M rows)",
            )
        
        # Export ALL data button (no filters)
        with col2:
            if st.button("Export All Data (Unfiltered)", key="export_all_button", help="Downloads ALL businesses from database (may take time for large datasets)"):
                progress_bar = st.progress(0, text="Preparing export...")
                try:
                    with st.spinner("Loading all data from database..."):
                        progress_bar.progress(25, text="Connecting to database...")
                        all_businesses = load_businesses(DB_PATH, filters={}, search_query="", limit=10_000_000)
                        
                        if all_businesses:
                            progress_bar.progress(50, text=f"Processing {len(all_businesses):,} businesses...")
                            all_df = pd.DataFrame(all_businesses)
                            all_visible_columns = [column for column in columns if column in all_df.columns]
                            all_csv_df = all_df[all_visible_columns].drop_duplicates(subset=["source_url"])
                            
                            progress_bar.progress(75, text="Generating CSV file...")
                            all_csv_data = all_csv_df.to_csv(index=False).encode("utf-8-sig")
                            
                            progress_bar.progress(100, text="Ready for download!")
                            st.download_button(
                                f"Download All {len(all_csv_df):,} Businesses",
                                all_csv_data,
                                f"yp_all_data_{datetime.now().strftime('%Y%m%d')}.csv",
                                "text/csv; charset=utf-8-sig",
                                key="download_all_csv_button",
                            )
                            st.success(f"✅ Prepared {len(all_csv_df):,} businesses for download")
                        else:
                            progress_bar.empty()
                            st.warning("No businesses found in database")
                except Exception as e:
                    progress_bar.empty()
                    st.error(f"Error exporting data: {str(e)}")


if active_crawl:
    @st.fragment(run_every=f"{AUTO_REFRESH_SECONDS}s")
    def _render_data_table_fragment() -> None:
        _render_data_table()

    _render_data_table_fragment()
else:
    _render_data_table()
