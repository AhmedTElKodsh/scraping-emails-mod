"""Separate Streamlit UI for the Apollo-compliant acquisition workbench."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.acquisition_data_access import (  # noqa: E402
    load_acquisition_overview,
    load_recent_contacts,
    load_sources,
)
from app.merge_preview import load_unified_business_preview  # noqa: E402
from scraper.acquisition_csv import import_csv  # noqa: E402
from scraper.apollo_people_search import ApolloPeopleSearchError, run_people_search  # noqa: E402
from scraper.config import Settings  # noqa: E402

st.set_page_config(page_title="Acquisition Workbench", layout="wide")

cfg = Settings()
DB_PATH = cfg.acquisition_db_path

st.title("Compliant Acquisition Workbench")

overview = load_acquisition_overview(DB_PATH)
cols = st.columns(5)
cols[0].metric("Sources", overview["enabled_sources"])
cols[1].metric("Businesses", overview["business_count"])
cols[2].metric("People", overview["people_count"])
cols[3].metric("Contacts", overview["contact_count"])
cols[4].metric("Runs", overview["run_count"])

tab_apollo, tab_import, tab_sources, tab_contacts, tab_merge = st.tabs(
    ["Apollo Search", "CSV Import", "Sources", "Contacts", "Merge Preview"]
)

with tab_apollo:
    st.subheader("Official Apollo People Search")
    person_titles = st.text_input("Person titles", value="Owner, Founder")
    person_locations = st.text_input(
        "Person locations",
        value=cfg.apollo_default_person_locations,
    )
    q_keywords = st.text_input("Keywords", value="")
    person_seniorities = st.text_input("Seniorities", value="")
    col_page, col_per_page = st.columns(2)
    page = col_page.number_input("Page", min_value=1, max_value=500, value=1, step=1)
    per_page = col_per_page.number_input("Per page", min_value=1, max_value=100, value=25, step=1)
    include_similar_titles = st.checkbox("Include similar titles", value=True)
    live = st.checkbox("Live API request", value=False)
    api_key = st.text_input(
        "Apollo API key",
        value=cfg.apollo_api_key,
        type="password",
        disabled=not live,
    )
    st.caption(
        "People Search stores candidate people, businesses, and website contacts only. "
        "Emails and phones require a later enrichment step."
    )
    if st.button("Run Apollo Search"):
        try:
            result = run_people_search(
                db_path=DB_PATH,
                api_key=api_key,
                person_titles=[part.strip() for part in person_titles.split(",")],
                person_locations=[part.strip() for part in person_locations.split(",")],
                q_keywords=q_keywords,
                person_seniorities=[part.strip() for part in person_seniorities.split(",")],
                include_similar_titles=include_similar_titles,
                page=int(page),
                per_page=int(per_page),
                dry_run=not live,
                base_url=cfg.apollo_api_base_url,
            )
        except (ApolloPeopleSearchError, ValueError) as exc:
            st.error(str(exc))
        else:
            if result.dry_run:
                st.success(f"Dry run created run #{result.run_id}. No Apollo request was sent.")
            else:
                st.success(
                    f"Run #{result.run_id} wrote {result.businesses_written} businesses, "
                    f"{result.people_written} people, and {result.contacts_written} "
                    "website contacts."
                )
            st.rerun()

with tab_import:
    st.subheader("User-Owned CSV Import")
    upload = st.file_uploader("CSV file", type=["csv"])
    provenance_note = st.text_input("Source note", value="User-owned CSV import")
    if upload is not None and st.button("Import CSV"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(upload.getbuffer())
            tmp_path = Path(tmp.name)
        try:
            result = import_csv(
                tmp_path,
                db_path=DB_PATH,
                source_name="csv_import",
                provenance_note=provenance_note,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
        st.success(
            f"Imported {result.businesses_written} businesses, "
            f"{result.people_written} people, and {result.contacts_written} contacts."
        )
        st.rerun()

with tab_sources:
    st.subheader("Source Policy")
    sources = load_sources(DB_PATH)
    st.dataframe(pd.DataFrame(sources), use_container_width=True, hide_index=True)

with tab_contacts:
    st.subheader("Recent Contacts")
    contacts = load_recent_contacts(DB_PATH)
    if contacts:
        st.dataframe(pd.DataFrame(contacts), use_container_width=True, hide_index=True)
    else:
        st.info(
            "No acquisition contacts yet. Start with CSV import or Apollo People "
            "Search dry runs."
        )

with tab_merge:
    st.subheader("Read-Only Merge Preview")
    preview_rows = load_unified_business_preview(cfg.db_path, DB_PATH, limit=500)
    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No YellowPages or acquisition businesses available to preview yet.")
