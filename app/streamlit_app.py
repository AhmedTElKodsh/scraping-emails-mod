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

os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

import pandas as pd
import streamlit as st

from app.crawl_plan import build_crawl_plan
from app.data_access import (
    ensure_seed_taxonomy,
    load_businesses,
    load_crawl_progress,
    load_crawl_target_options,
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
DB_PATH = getattr(cfg, "database_url", "") or getattr(cfg, "db_path", "data/scraper.sqlite")
AUTO_REFRESH_SECONDS = 15
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
        label = f"{row['name']} ({row['slug']})"
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

if SEED_WAS_LOADED:
    st.session_state["starter_taxonomy_loaded"] = True

if st.session_state.get("starter_taxonomy_loaded"):
    st.sidebar.success("Loaded starter taxonomy for this fresh deployment.")

filter_options = load_crawl_target_options(DB_PATH)
category_options = _option_labels(filter_options["categories"])
brand_options = _option_labels(filter_options["brands"])
keyword_options = _option_labels(filter_options["keywords"])
city_options = _option_labels(filter_options["cities"])

selected_categories = _sidebar_multiselect(
    "Categories",
    list(category_options.keys()),
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
if keyword_options:
    selected_keywords = _sidebar_multiselect(
        "Keywords",
        list(keyword_options.keys()),
        key="selected_keywords",
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

filters = {
    "category": _selected_slugs(category_options, selected_categories),
    "brand": _selected_slugs(brand_options, selected_brands),
    "keyword": _selected_slugs(keyword_options, selected_keywords),
    "city": selected_city_slugs,
    "area": selected_area_slugs,
    "district": _selected_slugs(district_options, selected_districts),
}

target_slugs_by_type = {
    target_type: slugs
    for target_type, slugs in {
        "category": filters["category"],
        "brand": filters["brand"],
        "keyword": filters["keyword"],
    }.items()
    if slugs
}
crawl_plan = build_crawl_plan(target_slugs_by_type, filters["city"])

st.title("YellowPages Egypt - Business Contacts")

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
            "Scoped crawl started. Existing saved businesses will be skipped."
        )
    elif started:
        st.session_state["crawl_status_message"] = (
            "Full dataset crawl started. Existing saved businesses will be skipped."
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
            "Rows count newly saved unique businesses; existing matches are skipped."
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

businesses = load_businesses(DB_PATH, filters)

if not businesses:
    matching_jobs = load_matching_jobs(
        DB_PATH,
        target_slugs_by_type,
        filters["city"],
    )
    if target_slugs_by_type and not matching_jobs:
        st.info(
            "No saved businesses for the selected taxonomy yet. "
            "Use Run Scoped Crawl to fetch them."
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
        st.info("The selected crawl job completed, but wrote 0 businesses.")
    elif matching_jobs:
        st.info("Saved businesses exist for this crawl, but none match all selected filters.")
    else:
        st.info("No saved businesses match the selected filters.")
else:
    df = pd.DataFrame(businesses)
    columns = [
        "business_name",
        "business_name_ar",
        "phone",
        "email",
        "website",
        "address",
        "address_ar",
        "source_url",
        "matched_facets",
        "scraped_at",
    ]
    visible_columns = [column for column in columns if column in df.columns]
    st.write(f"**{len(df)}** businesses found (showing up to 500)")
    st.dataframe(df[visible_columns], width="stretch")

    csv_data = df.drop_duplicates(subset=["source_url"]).to_csv(index=False)
    st.download_button(
        "Download CSV",
        csv_data,
        f"yp_export_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv",
        key="download_csv_button",
    )
