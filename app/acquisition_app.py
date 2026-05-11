"""Separate Streamlit UI for the Apollo-compliant acquisition workbench."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.acquisition_data_access import (
    load_acquisition_overview,
    load_recent_contacts,
    load_sources,
)
from app.merge_preview import load_unified_business_preview
from scraper.acquisition_csv import import_csv
from scraper.config import Settings

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

tab_import, tab_sources, tab_contacts, tab_merge = st.tabs(
    ["CSV Import", "Sources", "Contacts", "Merge Preview"]
)

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
