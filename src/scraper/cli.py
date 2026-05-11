from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import typer

if TYPE_CHECKING:
    from scraper.pipeline import Pipeline
    from scraper.proxy_pool import ProxyPool

app = typer.Typer(
    help="Email + contact scraper for YellowPages Egypt and permitted acquisition sources",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Email + contact scraper. Use subcommands to run."""
    pass


# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)


def _safe_slug(value: str) -> str:
    return re.sub(r"[^\w-]", "_", value)


def _parse_target_types(value: str) -> list[str]:
    allowed = {"category", "brand", "keyword"}
    target_types = [part.strip() for part in value.split(",") if part.strip()]
    for target_type in target_types:
        if target_type not in allowed:
            raise ValueError(f"Unsupported target type: {target_type}")
    return target_types or ["category"]


def _build_pipeline(
    use_proxies: bool,
    headless: bool,
    no_browser: bool = False,
) -> Pipeline:
    from scraper.browser_client import Tier3Client
    from scraper.http_client import Tier1Client, Tier2Client
    from scraper.pipeline import Pipeline

    tiers = [Tier1Client(), Tier2Client()]
    if not no_browser:
        tiers.append(Tier3Client(headless=headless))
    return Pipeline(tiers=tiers)


def _build_proxy_pool(use_proxies: bool) -> ProxyPool | None:
    if not use_proxies:
        return None
    from free_proxy import FreeProxy

    from scraper.proxy_pool import ProxyPool

    typer.echo("Building proxy pool...", err=True)
    raw = [FreeProxy().get() for _ in range(20)]
    pool = ProxyPool([p for p in raw if p])
    if pool.alive_count() == 0:
        typer.echo("Warning: no live proxies found; proceeding without proxy.", err=True)
        return None
    typer.echo(f"Proxy pool ready: {pool.alive_count()} proxies available", err=True)
    return pool


@app.command()
def scrape(
    target: str = typer.Argument(..., help="YellowPages target slug"),
    limit: int = typer.Option(50, help="Max pages per category (YP only)"),
    output_dir: str = typer.Option("output", help="Output directory"),
    use_proxies: bool = typer.Option(False, "--use-proxies", help="Enable free proxy pool"),
    target_type: str = typer.Option("category", help="YP target type: category, brand, or keyword"),
    city: str = typer.Option("", "--city", help="Optional YP city slug or external id"),
    headless: bool = typer.Option(True, help="Browser headless mode (Tier 3)"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Disable Tier 3 browser fallback"),
) -> None:
    """Scrape business contacts from YellowPages Egypt."""
    from scraper.config import Settings
    from scraper.csv_writer import CSVWriter
    from scraper.rate_limiter import RateLimiter

    log = structlog.get_logger()

    cfg = Settings()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    pipeline = _build_pipeline(use_proxies, headless, no_browser=no_browser)
    proxy_pool = _build_proxy_pool(use_proxies)

    from scraper.sites.yellowpages_eg import build_target_url, scrape_target

    if target_type not in {"category", "brand", "keyword"}:
        typer.echo(f"Error: unsupported target type {target_type}", err=True)
        raise typer.Exit(code=1)
    if "/" in target and target_type == "category" and not city:
        parts = target.split("/")
        if len(parts) != 2:
            typer.echo(
                "Error: legacy YP target must be 'category/governorate' format",
                err=True,
            )
            raise typer.Exit(code=1)
        target, city = parts
    safe_target = _safe_slug(target)
    safe_city = _safe_slug(city) if city else "all"
    csv_path = out / f"yellowpages_eg_{target_type}_{safe_target}_{safe_city}_{ts}.csv"

    rate_limiter = RateLimiter(
        min_delay=cfg.rate_limit_min_delay,
        max_delay=cfg.rate_limit_max_delay,
    )
    csv_writer = CSVWriter(csv_path)

    start_url = build_target_url(target_type, target, page=1, city_slug=city or None)
    log.info("starting_yp_scrape", url=start_url, output=str(csv_path), use_proxies=use_proxies)
    try:
        total = scrape_target(
            target_type,
            target,
            city or None,
            pipeline,
            csv_writer,
            rate_limiter,
            proxy_pool=proxy_pool,
            max_pages=limit,
            consecutive_empty_halt=cfg.consecutive_empty_halt,
        )
    except Exception as exc:
        log.error("scrape_failed", error=str(exc), exc_type=type(exc).__name__)
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Done. {total} rows written to {csv_path}")


@app.command()
def taxonomy(
    db_path: str = typer.Option(None, help="SQLite DB path (default: from Settings)"),
    seed_only: bool = typer.Option(
        False,
        "--seed-only",
        help="Load from seed JSON only, no HTTP refresh",
    ),
) -> None:
    """Initialize taxonomy (categories + locations) from seed JSON."""
    from scraper.config import Settings
    from scraper.taxonomy import init_taxonomy

    cfg = Settings()
    typer.echo(f"Initializing taxonomy (seed-only={seed_only})...")
    init_taxonomy(
        db_path=db_path or cfg.db_path,
        seed_path=cfg.taxonomy_seed_path,
        live_refresh=not seed_only,
    )
    typer.echo("Taxonomy initialized.")


@app.command()
def crawl_all(
    max_pages: int = typer.Option(
        None,
        help="Max pages per category/city (default: from Settings)",
    ),
    db_path: str = typer.Option(None, help="SQLite DB path (default: from Settings)"),
    use_proxies: bool = typer.Option(False, "--use-proxies", help="Enable proxy pool"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Disable Tier 3 browser fallback"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print job summary, no crawl"),
    target_types: str = typer.Option("category", help="Comma list: category,brand,keyword"),
    cities: str = typer.Option("all", help="City mode: all, top, or none"),
) -> None:
    """Mass crawl all (category, city) combos into SQLite."""
    from scraper.config import Settings
    from scraper.mass_crawl import run_mass_crawl

    cfg = Settings()
    typer.echo(f"Starting mass crawl (dry-run={dry_run})...")
    try:
        parsed_target_types = _parse_target_types(target_types)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    total = run_mass_crawl(
        db_path=db_path or cfg.db_path,
        max_pages=max_pages or cfg.mass_crawl_max_pages,
        use_proxies=use_proxies,
        headless=not no_browser,
        dry_run=dry_run,
        target_types=parsed_target_types,
        cities=cities,
    )
    if not dry_run:
        typer.echo(f"Done. {total} total rows written.")


@app.command()
def ui() -> None:
    """Launch the Streamlit web UI."""
    import subprocess
    from pathlib import Path

    app_path = Path(__file__).parent.parent.parent / "app" / "streamlit_app.py"
    if not app_path.exists():
        typer.echo(f"Error: Streamlit app not found at {app_path}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Launching Streamlit UI: {app_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])


@app.command("acquisition-ui")
def acquisition_ui() -> None:
    """Launch the separate compliant acquisition workbench."""
    import subprocess
    from pathlib import Path

    app_path = Path(__file__).parent.parent.parent / "app" / "acquisition_app.py"
    if not app_path.exists():
        typer.echo(f"Error: Acquisition app not found at {app_path}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Launching acquisition UI: {app_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])


@app.command("acquisition-import-csv")
def acquisition_import_csv(
    csv_path: str = typer.Argument(..., help="User-owned CSV path to import"),
    db_path: str = typer.Option(None, help="Acquisition SQLite DB path"),
    source_note: str = typer.Option("User-owned CSV import", help="Provenance note"),
) -> None:
    """Import a user-owned CSV into the separate acquisition database."""
    from scraper.acquisition_csv import import_csv
    from scraper.config import Settings

    cfg = Settings()
    result = import_csv(
        csv_path,
        db_path=db_path or cfg.acquisition_db_path,
        source_name="csv_import",
        provenance_note=source_note,
    )
    typer.echo(
        f"Imported {result.businesses_written} businesses, "
        f"{result.people_written} people, and {result.contacts_written} contacts "
        f"from {result.rows_seen} CSV rows."
    )


if __name__ == "__main__":
    app()
