"""Read helpers for the separate acquisition workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scraper.acquisition_db import get_connection, init_acquisition_db


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _scalar(row: Any, key: str = "value") -> Any:
    return row[key]


def load_sources(db_path: str | Path) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    try:
        rows = conn.execute(
            """SELECT source_name,
                      source_type,
                      allowed_use_note,
                      terms_url,
                      requires_api_key,
                      can_collect_people,
                      can_collect_contacts,
                      can_enrich,
                      is_paid,
                      enabled
            FROM sources
            ORDER BY enabled DESC, is_paid, source_name"""
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def load_acquisition_overview(db_path: str | Path) -> dict[str, int]:
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    try:
        return {
            "enabled_sources": _scalar(
                conn.execute("SELECT COUNT(*) AS value FROM sources WHERE enabled=1").fetchone()
            ),
            "business_count": _scalar(
                conn.execute("SELECT COUNT(*) AS value FROM businesses").fetchone()
            ),
            "people_count": _scalar(
                conn.execute("SELECT COUNT(*) AS value FROM people").fetchone()
            ),
            "contact_count": _scalar(
                conn.execute("SELECT COUNT(*) AS value FROM contacts").fetchone()
            ),
            "run_count": _scalar(
                conn.execute("SELECT COUNT(*) AS value FROM acquisition_runs").fetchone()
            ),
            "blocked_task_count": _scalar(
                conn.execute(
                    """SELECT COUNT(*) AS value
                    FROM acquisition_tasks
                    WHERE status IN ('blocked_budget','blocked_rate','skipped_policy')"""
                ).fetchone()
            ),
        }
    finally:
        conn.close()


def load_recent_contacts(db_path: str | Path, limit: int = 100) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    try:
        rows = conn.execute(
            """SELECT c.contact_type,
                      c.contact_value,
                      c.source_name,
                      c.verification_status,
                      c.confidence,
                      c.acquired_at,
                      COALESCE(p.full_name, '') AS person_name,
                      COALESCE(b.business_name, '') AS business_name,
                      COALESCE(b.website, '') AS website
            FROM contacts c
            LEFT JOIN people p ON p.id=c.person_id
            LEFT JOIN businesses b ON b.id=c.business_id
            ORDER BY c.acquired_at DESC, c.id DESC
            LIMIT ?""",
            (limit,),
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()
