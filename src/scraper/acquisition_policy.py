"""Policy gate for compliant acquisition sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scraper.acquisition_db import get_connection, init_acquisition_db


class PolicyBlockedError(RuntimeError):
    """Raised when a source is blocked by acquisition policy."""


@dataclass(frozen=True)
class SourcePolicy:
    source_name: str
    source_type: str
    allowed_use_note: str
    terms_url: str
    requires_api_key: bool
    can_collect_people: bool
    can_collect_contacts: bool
    can_enrich: bool
    is_paid: bool
    enabled: bool


def _as_bool(value: object) -> bool:
    if value is None:
        return False
    return bool(int(str(value)))


def get_source_policy(db_path: str | Path, source_name: str) -> SourcePolicy:
    conn = get_connection(db_path)
    init_acquisition_db(conn)
    row = conn.execute(
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
        WHERE source_name=?""",
        (source_name,),
    ).fetchone()
    conn.close()
    if row is None:
        raise PolicyBlockedError(f"Source '{source_name}' is not registered")

    return SourcePolicy(
        source_name=row["source_name"],
        source_type=row["source_type"],
        allowed_use_note=row["allowed_use_note"],
        terms_url=row["terms_url"],
        requires_api_key=_as_bool(row["requires_api_key"]),
        can_collect_people=_as_bool(row["can_collect_people"]),
        can_collect_contacts=_as_bool(row["can_collect_contacts"]),
        can_enrich=_as_bool(row["can_enrich"]),
        is_paid=_as_bool(row["is_paid"]),
        enabled=_as_bool(row["enabled"]),
    )


def require_source_allowed(
    db_path: str | Path,
    source_name: str,
    *,
    credit_budget: int | None = None,
) -> SourcePolicy:
    source = get_source_policy(db_path, source_name)
    if not source.enabled:
        raise PolicyBlockedError(f"Source '{source_name}' is disabled")
    if not source.allowed_use_note.strip() or not source.terms_url.strip():
        raise PolicyBlockedError(f"Source '{source_name}' is blocked until terms are documented")
    if source.is_paid and (credit_budget is None or credit_budget <= 0):
        raise PolicyBlockedError(f"Source '{source_name}' requires an explicit credit budget")
    return source
