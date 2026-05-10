"""Streamlit UI for saved Yellow Pages Egypt scrape results."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app.crawl_plan import build_crawl_plan
from app.data_access import (
    load_businesses,
    load_crawl_progress,
    load_crawl_target_options,
    load_facet_options,
    load_job_summary,
    load_matching_jobs,
)
from scraper.config import Settings

st.set_page_config(page_title="YP Egypt Scraper", layout="wide")

cfg = Settings()
DB_PATH = cfg.db_path


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


st.sidebar.title("Filters")

filter_options = load_crawl_target_options(DB_PATH)
category_options = _option_labels(filter_options["categories"])
brand_options = _option_labels(filter_options["brands"])
keyword_options = _option_labels(filter_options["keywords"])
city_options = _option_labels(filter_options["cities"])

selected_categories = st.sidebar.multiselect("Categories", list(category_options.keys()))
selected_brands = st.sidebar.multiselect("Brands", list(brand_options.keys()))
selected_keywords = st.sidebar.multiselect("Keywords", list(keyword_options.keys()))
selected_cities = st.sidebar.multiselect("Cities", list(city_options.keys()))

selected_city_slugs = _selected_slugs(city_options, selected_cities)

area_options: dict[str, str] = {}
if len(selected_city_slugs) == 1:
    area_options = _option_labels(load_facet_options(DB_PATH, "area", selected_city_slugs[0]))
selected_areas = (
    st.sidebar.multiselect("Areas", list(area_options.keys()))
    if area_options
    else []
)
selected_area_slugs = _selected_slugs(area_options, selected_areas)

district_options: dict[str, str] = {}
if len(selected_area_slugs) == 1:
    district_options = _option_labels(
        load_facet_options(DB_PATH, "district", selected_area_slugs[0])
    )
selected_districts = (
    st.sidebar.multiselect("Districts", list(district_options.keys()))
    if district_options
    else []
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
                f"{row['jobs']} jobs, {row['pages_scraped'] or 0} pages, "
                f"{row['rows_written'] or 0} rows"
            )
    else:
        st.info("No crawl jobs yet.")

progress = load_crawl_progress(DB_PATH)
active_crawl = st.session_state.get("crawl_running", False) or progress["running_jobs"] > 0
crawl_button_label = "Run Scoped Crawl" if crawl_plan.is_scoped else "Run Full Dataset Crawl"

if st.sidebar.button(crawl_button_label, disabled=active_crawl):
    st.session_state["crawl_running"] = True
    import threading

    from scraper.mass_crawl import run_mass_crawl

    def crawl_thread() -> None:
        try:
            run_mass_crawl(
                db_path=DB_PATH,
                max_pages=cfg.mass_crawl_max_pages,
                target_types=crawl_plan.target_types,
                target_slugs_by_type=crawl_plan.target_slugs_by_type,
                cities=crawl_plan.cities,
                city_slugs=crawl_plan.city_slugs,
            )
        finally:
            st.session_state["crawl_running"] = False

    threading.Thread(target=crawl_thread, daemon=True).start()
    if crawl_plan.is_scoped:
        st.session_state["crawl_status_message"] = (
            "Scoped crawl started. Existing saved businesses will be skipped."
        )
    else:
        st.session_state["crawl_status_message"] = (
            "Full dataset crawl started. Existing saved businesses will be skipped."
        )

if st.session_state.get("crawl_status_message"):
    st.sidebar.success(st.session_state["crawl_status_message"])

if progress["total_jobs"]:
    completed = progress["done_jobs"]
    total = progress["total_jobs"]
    ratio = min(completed / total, 1.0)
    status_text = f"{completed:,} of {total:,} crawl jobs complete ({ratio:.1%})"
    st.sidebar.progress(ratio, text=status_text)
    st.sidebar.caption(
        f"{progress['business_count']:,} businesses saved | "
        f"{progress['running_jobs']:,} running | "
        f"{progress['pending_jobs']:,} queued | "
        f"{progress['failed_jobs']:,} failed"
    )
    if active_crawl:
        st.sidebar.info("Crawler is working in the background. Refresh to update progress.")
    if progress["running_jobs"]:
        with st.sidebar.expander("Running Now", expanded=True):
            for job in progress["current_jobs"]:
                city = job["city_slug"] or "all cities"
                st.write(f"{job['target_type']}: {job['target_slug']} ({city})")
    if progress["failed_jobs"]:
        st.sidebar.warning("Some crawl jobs failed. They will be retried on the next run.")

if st.sidebar.button("Refresh Log"):
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
        "phone",
        "email",
        "website",
        "address",
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
    )
