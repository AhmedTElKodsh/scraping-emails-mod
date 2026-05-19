"""Read helpers for the Streamlit UI."""

from pathlib import Path
from typing import Any

from scraper.storage import Backend, open_connection, placeholder
from scraper.taxonomy import load_seed, populate_from_seed

ARABIC_ROLE_TERMS = {
    "مصنع",
    "استيراد",
    "تصدير",
    "استيراد وتصدير",
    "توزيع",
}
RELATED_CATEGORY_TARGETS = {
    "import-&-export",
    "import-export",
    "import export",
    "factory",
    "factories",
    "factory-equipment-and-supplies",
    "distribution",
    "استيراد وتصدير",
    "استيراد-وتصدير",
    "مصنع",
    "تصدير",
    "توزيع",
}
RELATED_KEYWORD_TARGETS = {
    "import",
    "export",
    "factory",
    "distribution",
    "import-&-export",
    "استيراد",
    "تصدير",
    "مصنع",
    "توزيع",
    "استيراد وتصدير",
    "استيراد-وتصدير",
}

CATEGORY_TARGET_GROUPS = {
    "import-&-export": {
        "slug": "import-&-export",
        "name": "Import & Export",
        "name_ar": "استيراد وتصدير",
        "aliases": {
            "import-&-export",
            "import-export",
            "import export",
            "استيراد وتصدير",
            "استيراد-وتصدير",
        },
    },
    "factory-equipment-and-supplies": {
        "slug": "factory-equipment-and-supplies",
        "name": "Factory Equipment & Supplies",
        "name_ar": "مستلزمات مصانع",
        "aliases": {
            "factory-equipment-and-supplies",
        },
    },
}

ROLE_KEYWORD_EXPANSIONS = {
    "مصنع": ["factory", "factories", "factory-equipment-and-supplies"],
    "استيراد": ["import"],
    "تصدير": ["export"],
    "استيراد وتصدير": ["import-&-export", "import-export", "import export", "استيراد-وتصدير"],
    "استيراد-وتصدير": ["import-&-export", "import-export", "import export", "استيراد وتصدير"],
    "توزيع": ["distribution"],
}


def _canonical_category_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for row in rows:
        values = {
            str(row.get("slug") or ""),
            str(row.get("name") or ""),
            str(row.get("name_ar") or ""),
            str(row.get("href") or ""),
        }
        for group in CATEGORY_TARGET_GROUPS.values():
            if not any(alias in value for alias in group["aliases"] for value in values):
                continue
            item = canonical.setdefault(
                group["slug"],
                {
                    "slug": group["slug"],
                    "name": group["name"],
                    "name_ar": group["name_ar"],
                    "count": 0,
                },
            )
            item["count"] = max(
                int(item.get("count") or 0),
                int(row.get("count") or row.get("result_count") or 0),
            )
            break
    for group in CATEGORY_TARGET_GROUPS.values():
        canonical.setdefault(
            group["slug"],
            {
                "slug": group["slug"],
                "name": group["name"],
                "name_ar": group["name_ar"],
                "count": 0,
            },
        )
    return [canonical[group["slug"]] for group in CATEGORY_TARGET_GROUPS.values()]


def _open(db_path: str | Path) -> tuple[Any, Backend]:
    return open_connection(db_path)


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _scalar(row: Any, key: str, index: int = 0) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]


def _like_pattern(value: str) -> str:
    return f"%{value.strip()}%"


def _facet_search_clause(alias: str, ph: str, backend: Backend) -> str:
    fields = (
        f"{alias}.slug",
        f"{alias}.name",
        f"COALESCE({alias}.name_ar, '')",
    )
    if backend == "postgres":
        return " OR ".join(f"{field} ILIKE {ph}" for field in fields)
    return " OR ".join(f"LOWER({field}) LIKE LOWER({ph})" for field in fields)


def _business_search_clause(ph: str, backend: Backend) -> str:
    fields = (
        "b.business_name",
        "b.business_name_ar",
        "b.category_slug",
        "b.category_ar",
        "b.city_slug",
        "b.governorate_ar",
        "b.phone",
        "b.email",
        "b.website",
        "b.facebook_url",
        "b.address",
        "b.address_ar",
        "b.source_url",
    )
    if backend == "postgres":
        return " OR ".join(f"COALESCE({field}, '') ILIKE {ph}" for field in fields)
    return " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE LOWER({ph})" for field in fields)


def load_taxonomy_options(db_path: str | Path, table: str) -> list[dict[str, Any]]:
    allowed = {"categories", "brands", "keywords"}
    if table not in allowed:
        raise ValueError(f"Unsupported taxonomy table: {table}")
    conn, _backend = _open(db_path)
    try:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY name").fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def _target_matches(row: dict[str, Any], allowed_terms: set[str]) -> bool:
    haystack = " ".join(
        str(row.get(field) or "")
        for field in ("slug", "name", "name_ar", "href")
    ).casefold()
    return any(term.casefold() in haystack for term in allowed_terms)


def _limited_targets(rows: list[dict[str, Any]], allowed_terms: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if _target_matches(row, allowed_terms)]


def load_facet_options(
    db_path: str | Path,
    facet_type: str,
    parent_slug: str | None = None,
) -> list[dict[str, Any]]:
    table_by_type = {
        "category": "categories",
        "brand": "brands",
        "keyword": "keywords",
        "city": "locations",
        "area": "locations",
        "district": "locations",
    }
    if facet_type not in table_by_type:
        raise ValueError(f"Unsupported facet type: {facet_type}")

    conn, backend = _open(db_path)
    ph = placeholder(backend)
    try:
        table = table_by_type[facet_type]
        if table == "locations":
            query = (
                "SELECT bf.slug, COALESCE(l.name, bf.name, bf.slug) AS name, "
                "COALESCE(bf.name_ar, '') AS name_ar, "
                "COUNT(DISTINCT bf.source_url) AS count "
                "FROM business_facets bf "
                "LEFT JOIN locations l ON l.slug=bf.slug AND l.type=bf.facet_type "
                f"WHERE bf.facet_type={ph}"
            )
            params: list[Any] = [facet_type]
            if parent_slug is not None:
                query += f" AND l.parent_slug={ph}"
                params.append(parent_slug)
            query += (
                " GROUP BY bf.slug, COALESCE(l.name, bf.name, bf.slug), "
                "COALESCE(bf.name_ar, '') ORDER BY name"
            )
        else:
            query = (
                f"SELECT bf.slug, COALESCE(t.name, bf.name, bf.slug) AS name, "
                "COALESCE(bf.name_ar, '') AS name_ar, "
                "COUNT(DISTINCT bf.source_url) AS count "
                "FROM business_facets bf "
                f"LEFT JOIN {table} t ON t.slug=bf.slug "
                f"WHERE bf.facet_type={ph} "
                "GROUP BY bf.slug, COALESCE(t.name, bf.name, bf.slug), "
                "COALESCE(bf.name_ar, '') ORDER BY name"
            )
            params = [facet_type]
        rows = conn.execute(query, params).fetchall()
        items = _rows_to_dicts(rows)
        for item in items:
            if not item.get("name_ar"):
                item.pop("name_ar", None)
        return items
    finally:
        conn.close()


def load_filter_options(db_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "categories": load_facet_options(db_path, "category"),
        "brands": load_facet_options(db_path, "brand"),
        "keywords": load_facet_options(db_path, "keyword"),
        "cities": load_facet_options(db_path, "city"),
    }


def search_facet_suggestions(
    db_path: str | Path,
    query: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Return saved facet suggestions matching user search text."""
    search_text = query.strip()
    if not search_text:
        return []

    conn, backend = _open(db_path)
    ph = placeholder(backend)
    pattern = _like_pattern(search_text)
    try:
        where_clause = _facet_search_clause("bf", ph, backend)
        rows = conn.execute(
            f"""SELECT
                bf.facet_type,
                bf.slug,
                COALESCE(NULLIF(MAX(bf.name), ''), bf.slug) AS name,
                COALESCE(NULLIF(MAX(bf.name_ar), ''), '') AS name_ar,
                COUNT(DISTINCT bf.source_url) AS count
            FROM business_facets bf
            WHERE bf.facet_type IN ('keyword','category','city','area','district','brand')
              AND ({where_clause})
            GROUP BY bf.facet_type, bf.slug
            ORDER BY
                COUNT(DISTINCT bf.source_url) DESC,
                CASE bf.facet_type
                    WHEN 'keyword' THEN 0
                    WHEN 'category' THEN 1
                    WHEN 'city' THEN 2
                    WHEN 'area' THEN 3
                    WHEN 'district' THEN 4
                    ELSE 5
                END,
                name
            LIMIT {ph}""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        suggestions = _rows_to_dicts(rows)
        for suggestion in suggestions:
            if not suggestion.get("name_ar"):
                suggestion.pop("name_ar", None)
        return suggestions
    finally:
        conn.close()


def load_crawl_target_options(db_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    keywords_raw = load_taxonomy_options(db_path, "keywords")
    categories_raw = load_taxonomy_options(db_path, "categories")
    return {
        "categories": _canonical_category_targets(
            _limited_targets(categories_raw, RELATED_CATEGORY_TARGETS),
        ),
        "brands": [],
        "keywords": _limited_targets(
            keywords_raw,
            RELATED_KEYWORD_TARGETS,
        ),
        "cities": load_locations(db_path, "city"),
    }


def _populate_seed_postgres(conn: Any, seed: dict[str, Any]) -> None:
    for category in seed.get("categories", []):
        conn.execute(
            """INSERT INTO categories (slug, name, parent_slug, result_count, href, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name=EXCLUDED.name,
                parent_slug=EXCLUDED.parent_slug,
                result_count=EXCLUDED.result_count,
                href=EXCLUDED.href,
                scraped_at=EXCLUDED.scraped_at""",
            (
                category["slug"],
                category["name"],
                category.get("parent_slug", ""),
                category.get("result_count", 0),
                category.get("href", ""),
                "",
            ),
        )
    for brand in seed.get("brands", []):
        conn.execute(
            """INSERT INTO brands (slug, name, result_count, href, scraped_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name=EXCLUDED.name,
                result_count=EXCLUDED.result_count,
                href=EXCLUDED.href,
                scraped_at=EXCLUDED.scraped_at""",
            (
                brand["slug"],
                brand["name"],
                brand.get("result_count", 0),
                brand.get("href", ""),
                "",
            ),
        )
    for keyword in seed.get("keywords", []):
        conn.execute(
            """INSERT INTO keywords (slug, name, href, scraped_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name=EXCLUDED.name,
                href=EXCLUDED.href,
                scraped_at=EXCLUDED.scraped_at""",
            (
                keyword["slug"],
                keyword["name"],
                keyword.get("href", ""),
                "",
            ),
        )
    location_order = {"city": 0, "area": 1, "district": 2}
    locations = sorted(
        seed.get("locations", []),
        key=lambda location: location_order.get(location.get("type", "city"), 99),
    )
    for location in locations:
        conn.execute(
            """INSERT INTO locations
            (slug, name, type, external_id, parent_slug, result_count, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                name=EXCLUDED.name,
                type=EXCLUDED.type,
                external_id=EXCLUDED.external_id,
                parent_slug=EXCLUDED.parent_slug,
                result_count=EXCLUDED.result_count,
                scraped_at=EXCLUDED.scraped_at""",
            (
                location["slug"],
                location["name"],
                location.get("type", "city"),
                location.get("external_id", ""),
                location.get("parent_slug") or None,
                location.get("result_count", 0),
                "",
            ),
        )
    conn.commit()


def ensure_seed_taxonomy(db_path: str | Path, seed_path: str | Path) -> bool:
    """Populate bundled taxonomy when a fresh deployment starts with an empty DB."""
    conn, backend = _open(db_path)
    try:
        category_count = _scalar(
            conn.execute("SELECT COUNT(*) AS value FROM categories").fetchone(),
            "value",
        )
        city_count = _scalar(
            conn.execute("SELECT COUNT(*) AS value FROM locations WHERE type='city'").fetchone(),
            "value",
        )
        if category_count and city_count:
            return False
        seed = load_seed(seed_path)
        if backend == "postgres":
            _populate_seed_postgres(conn, seed)
        else:
            populate_from_seed(conn, seed)
        return bool(seed.get("categories") or seed.get("locations"))
    finally:
        conn.close()


def load_locations(
    db_path: str | Path,
    loc_type: str = "city",
    parent_slug: str | None = None,
) -> list[dict[str, Any]]:
    conn, backend = _open(db_path)
    ph = placeholder(backend)
    try:
        if parent_slug is None:
            rows = conn.execute(
                f"SELECT slug, name FROM locations WHERE type={ph} ORDER BY name",
                (loc_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT slug, name FROM locations
                WHERE type={ph} AND parent_slug={ph} ORDER BY name""",
                (loc_type, parent_slug),
            ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def load_job_summary(db_path: str | Path) -> list[dict[str, Any]]:
    conn, _backend = _open(db_path)
    try:
        rows = conn.execute(
            """SELECT target_type, status, COUNT(*) AS jobs,
            SUM(pages_scraped) AS pages_scraped,
            SUM(rows_written) AS rows_written
            FROM scrape_jobs
            GROUP BY target_type, status
            ORDER BY target_type, status"""
        ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def load_crawl_progress(db_path: str | Path) -> dict[str, Any]:
    conn, backend = _open(db_path)
    try:
        status_rows = conn.execute(
            """SELECT status, COUNT(*) AS jobs
            FROM scrape_jobs
            GROUP BY status"""
        ).fetchall()
        statuses = {_scalar(row, "status", 0): _scalar(row, "jobs", 1) for row in status_rows}
        total_jobs = sum(statuses.values())
        done_jobs = statuses.get("done", 0)
        running_jobs = statuses.get("running", 0)
        pending_jobs = statuses.get("pending", 0)
        failed_jobs = statuses.get("failed", 0)
        rows_written = _scalar(
            conn.execute("SELECT COALESCE(SUM(rows_written), 0) AS value FROM scrape_jobs")
            .fetchone(),
            "value",
        )
        pages_checked = _scalar(
            conn.execute("SELECT COALESCE(SUM(pages_scraped), 0) AS value FROM scrape_jobs")
            .fetchone(),
            "value",
        )
        business_count = _scalar(
            conn.execute("SELECT COUNT(*) AS value FROM businesses").fetchone(),
            "value",
        )
        if backend == "postgres":
            recent_sql = """SELECT COUNT(*) AS value FROM businesses
            WHERE NULLIF(scraped_at, '')::timestamptz >= now() - interval '10 minutes'"""
        else:
            recent_sql = """SELECT COUNT(*) AS value FROM businesses
            WHERE datetime(scraped_at) >= datetime('now', '-10 minutes')"""
        recent_business_count = _scalar(conn.execute(recent_sql).fetchone(), "value")
        current_jobs = conn.execute(
            """SELECT target_type, target_slug, city_slug, started_at
            FROM scrape_jobs
            WHERE status='running'
            ORDER BY started_at DESC
            LIMIT 3"""
        ).fetchall()
        current_job_items: list[dict[str, Any]] = []
        for row in current_jobs:
            item = dict(row)
            item["matching_saved_businesses"] = _matching_saved_business_count(
                conn,
                item["target_type"],
                item["target_slug"],
                item["city_slug"],
                backend,
            )
            current_job_items.append(item)
        return {
            "total_jobs": total_jobs,
            "done_jobs": done_jobs,
            "running_jobs": running_jobs,
            "pending_jobs": pending_jobs,
            "failed_jobs": failed_jobs,
            "rows_written": rows_written,
            "pages_checked": pages_checked,
            "business_count": business_count,
            "recent_business_count": recent_business_count,
            "current_jobs": current_job_items,
        }
    finally:
        conn.close()


def _matching_saved_business_count(
    conn: Any,
    target_type: str,
    target_slug: str,
    city_slug: str | None,
    backend: Backend = "sqlite",
) -> int:
    ph = placeholder(backend)
    query = (
        "SELECT COUNT(DISTINCT bf.source_url) "
        "FROM business_facets bf "
        f"WHERE bf.facet_type={ph} AND bf.slug={ph}"
    )
    params: list[Any] = [target_type, target_slug]
    if city_slug:
        query += (
            " AND EXISTS ("
            "SELECT 1 FROM business_facets city "
            "WHERE city.source_url=bf.source_url "
            f"AND city.facet_type='city' AND city.slug={ph}"
            ")"
        )
        params.append(city_slug)
    return _scalar(conn.execute(query, params).fetchone(), "count")


def load_matching_jobs(
    db_path: str | Path,
    target_slugs_by_type: dict[str, list[str]] | None = None,
    city_slugs: list[str] | None = None,
) -> list[dict[str, Any]]:
    target_slugs_by_type = {
        target_type: slugs
        for target_type, slugs in (target_slugs_by_type or {}).items()
        if slugs
    }
    city_slugs = city_slugs or []
    if not target_slugs_by_type and not city_slugs:
        return []

    conn, backend = _open(db_path)
    ph = placeholder(backend)
    try:
        query = (
            "SELECT target_type, target_slug, city_slug, status, rows_written "
            "FROM scrape_jobs WHERE 1=1"
        )
        params: list[Any] = []
        target_clauses: list[str] = []
        for target_type, target_slugs in target_slugs_by_type.items():
            placeholders = ",".join(ph for _ in target_slugs)
            target_clauses.append(
                f"(target_type={ph} AND target_slug IN ({placeholders}))"
            )
            params.extend([target_type, *target_slugs])
        if target_clauses:
            query += f" AND ({' OR '.join(target_clauses)})"
        if city_slugs:
            placeholders = ",".join(ph for _ in city_slugs)
            query += f" AND city_slug IN ({placeholders})"
            params.extend(city_slugs)
        query += " ORDER BY target_type, target_slug, city_slug"
        rows = conn.execute(query, params).fetchall()
        jobs = _rows_to_dicts(rows)
        for job in jobs:
            job["matching_saved_businesses"] = _matching_saved_business_count(
                conn,
                job["target_type"],
                job["target_slug"],
                job["city_slug"],
                backend,
            )
        return jobs
    finally:
        conn.close()


def _facet_text(conn: Any, source_url: str, backend: Backend = "sqlite") -> str:
    ph = placeholder(backend)
    facets = conn.execute(
        f"""SELECT facet_type, name, name_ar, slug
        FROM business_facets
        WHERE source_url={ph}
        ORDER BY facet_type, name, slug""",
        (source_url,),
    ).fetchall()
    parts = []
    for row in facets:
        primary = row["name"] or row["slug"]
        arabic = row["name_ar"] or ""
        if arabic and arabic != primary:
            parts.append(f"{row['facet_type']}: {primary} / {arabic}")
        else:
            parts.append(f"{row['facet_type']}: {primary}")
    return ", ".join(parts)


def load_database_stats(db_path: str | Path) -> dict[str, Any]:
    """Load database statistics for dashboard display."""
    conn, _backend = _open(db_path)
    try:
        total = _scalar(
            conn.execute("SELECT COUNT(*) AS value FROM businesses").fetchone(),
            "value",
        )
        with_arabic = _scalar(
            conn.execute(
                "SELECT COUNT(*) AS value FROM businesses "
                "WHERE business_name_ar IS NOT NULL AND business_name_ar != ''"
            ).fetchone(),
            "value",
        )
        with_email = _scalar(
            conn.execute(
                "SELECT COUNT(*) AS value FROM businesses "
                "WHERE email IS NOT NULL AND email != ''"
            ).fetchone(),
            "value",
        )
        with_phone = _scalar(
            conn.execute(
                "SELECT COUNT(*) AS value FROM businesses "
                "WHERE phone IS NOT NULL AND phone != ''"
            ).fetchone(),
            "value",
        )
        unique_categories = _scalar(
            conn.execute(
                "SELECT COUNT(DISTINCT category_slug) AS value FROM businesses"
            ).fetchone(),
            "value",
        )
        unique_cities = _scalar(
            conn.execute(
                "SELECT COUNT(DISTINCT city_slug) AS value FROM businesses"
            ).fetchone(),
            "value",
        )
        return {
            "total_businesses": total,
            "arabic_businesses": with_arabic,
            "businesses_with_email": with_email,
            "businesses_with_phone": with_phone,
            "unique_categories": unique_categories,
            "unique_cities": unique_cities,
        }
    finally:
        conn.close()


def get_last_crawl_time(db_path: str | Path) -> str | None:
    """Get the timestamp of the most recent crawl."""
    conn, backend = _open(db_path)
    try:
        if backend == "postgres":
            query = """SELECT MAX(NULLIF(scraped_at, '')::timestamptz) AS last_time 
                      FROM businesses"""
        else:
            query = """SELECT MAX(scraped_at) AS last_time FROM businesses"""
        
        row = conn.execute(query).fetchone()
        last_time = _scalar(row, "last_time", 0)
        return str(last_time) if last_time else None
    finally:
        conn.close()


def load_businesses(
    db_path: str | Path,
    filters: dict[str, list[str]] | None = None,
    search_query: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    filters = {key: value for key, value in (filters or {}).items() if value}
    search_text = search_query.strip()
    conn, backend = _open(db_path)
    ph = placeholder(backend)
    try:
        # Use COALESCE to fallback to English fields if Arabic fields are empty
        query = """SELECT 
            b.source_url,
            b.business_name,
            COALESCE(NULLIF(b.business_name_ar, ''), b.business_name) AS business_name_ar,
            COALESCE(NULLIF(b.category_ar, ''), b.category_slug) AS category_ar,
            COALESCE(NULLIF(b.city_slug, ''), '') AS governorate,
            COALESCE(NULLIF(b.governorate_ar, ''), b.city_slug) AS governorate_ar,
            COALESCE(NULLIF(b.address_ar, ''), b.address) AS address_ar,
            b.phone,
            b.email,
            b.website,
            b.facebook_url,
            b.category_slug,
            b.city_slug,
            b.scraped_at,
            b.source_tier,
            b.raw_html_hash
        FROM businesses b WHERE 1=1"""
        params: list[Any] = []
        for facet_type, slugs in filters.items():
            slugs = list(slugs)
            placeholders = ",".join(ph for _ in slugs)
            facet_types = [facet_type]
            if facet_type == "keyword" and any(slug in ARABIC_ROLE_TERMS for slug in slugs):
                facet_types.append("category")
                expanded_slugs: list[str] = []
                for slug in slugs:
                    expanded_slugs.extend(ROLE_KEYWORD_EXPANSIONS.get(slug, []))
                slugs.extend(expanded_slugs)
                placeholders = ",".join(ph for _ in slugs)
            type_placeholders = ",".join(ph for _ in facet_types)
            query += (
                " AND EXISTS ("
                "SELECT 1 FROM business_facets bf "
                "WHERE bf.source_url=b.source_url "
                f"AND bf.facet_type IN ({type_placeholders}) "
                f"AND bf.slug IN ({placeholders})"
                ")"
            )
            params.extend([*facet_types, *slugs])
        order_params: list[Any] = []
        if search_text:
            pattern = _like_pattern(search_text)
            facet_clause = _facet_search_clause("bf", ph, backend)
            business_clause = _business_search_clause(ph, backend)
            query += (
                " AND ("
                "EXISTS ("
                "SELECT 1 FROM business_facets bf "
                "WHERE bf.source_url=b.source_url "
                f"AND ({facet_clause})"
                ") "
                f"OR {business_clause}"
                ")"
            )
            params.extend([pattern, pattern, pattern])
            params.extend([pattern] * 13)
            order_params.extend([pattern, pattern, pattern])
            query += (
                " ORDER BY CASE WHEN EXISTS ("
                "SELECT 1 FROM business_facets bf "
                "WHERE bf.source_url=b.source_url "
                f"AND ({facet_clause})"
                ") THEN 0 ELSE 1 END, "
                "b.scraped_at DESC, b.business_name"
            )
        else:
            query += " ORDER BY b.scraped_at DESC, b.business_name"
        query += f" LIMIT {ph}"
        params.extend(order_params)
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        
        # Batch load facets to avoid N+1 queries
        businesses: list[dict[str, Any]] = []
        source_urls = [dict(row)["source_url"] for row in rows]
        
        facets_by_url: dict[str, list[str]] = {}
        facet_slugs_by_url: dict[str, dict[str, list[str]]] = {}
        facet_names_by_url: dict[str, dict[str, list[str]]] = {}
        if source_urls:
            # Load all facets in one query
            facets_ph = ",".join(placeholder(backend) for _ in source_urls)
            facet_rows = conn.execute(
                f"""SELECT source_url, facet_type, name, name_ar, slug
                FROM business_facets
                WHERE source_url IN ({facets_ph})
                ORDER BY source_url, facet_type, name, slug""",
                source_urls,
            ).fetchall()
            
            # Group facets by source_url
            for facet_row in facet_rows:
                url = facet_row["source_url"]
                primary = facet_row["name"] or facet_row["slug"]
                arabic = facet_row["name_ar"] or ""
                facet_type = facet_row["facet_type"]
                slug = facet_row["slug"]
                if arabic and arabic != primary:
                    facet_text = f"{facet_type}: {arabic}"
                else:
                    facet_text = f"{facet_type}: {primary}"
                facets_by_url.setdefault(url, []).append(facet_text)
                facet_slugs_by_url.setdefault(url, {}).setdefault(facet_type, []).append(slug)
                facet_names_by_url.setdefault(url, {}).setdefault(facet_type, []).append(str(primary))
        
        for row in rows:
            item = dict(row)
            item["matched_facets"] = ", ".join(facets_by_url.get(item["source_url"], []))
            grouped_slugs = facet_slugs_by_url.get(item["source_url"], {})
            grouped_names = facet_names_by_url.get(item["source_url"], {})
            item["facet_categories"] = " | ".join(grouped_slugs.get("category", []))
            item["facet_keywords"] = " | ".join(grouped_slugs.get("keyword", []))
            item["facet_brands"] = " | ".join(grouped_slugs.get("brand", []))
            item["facet_cities"] = " | ".join(grouped_slugs.get("city", []))
            item["facet_names"] = " | ".join(
                name
                for facet_type in ("category", "keyword", "brand", "city", "area", "district")
                for name in grouped_names.get(facet_type, [])
            )
            businesses.append(item)
        return businesses
    finally:
        conn.close()
