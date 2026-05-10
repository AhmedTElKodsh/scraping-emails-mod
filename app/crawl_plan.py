"""Pure helpers for Streamlit crawl queue decisions."""

from dataclasses import dataclass

ALL_TARGET_TYPES = ("category", "brand", "keyword")


@dataclass(frozen=True)
class CrawlPlan:
    target_types: list[str]
    target_slugs_by_type: dict[str, list[str]] | None
    cities: str
    city_slugs: list[str] | None
    is_scoped: bool


def _clean_slugs(values: list[str] | None) -> list[str]:
    return [value for value in (values or []) if value]


def build_crawl_plan(
    target_slugs_by_type: dict[str, list[str]] | None,
    city_slugs: list[str] | None,
) -> CrawlPlan:
    selected_targets = {
        target_type: _clean_slugs(slugs)
        for target_type, slugs in (target_slugs_by_type or {}).items()
        if _clean_slugs(slugs)
    }
    selected_cities = _clean_slugs(city_slugs)

    return CrawlPlan(
        target_types=list(selected_targets) or list(ALL_TARGET_TYPES),
        target_slugs_by_type=selected_targets or None,
        cities="none" if selected_cities else "all",
        city_slugs=selected_cities or None,
        is_scoped=bool(selected_targets or selected_cities),
    )
