from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Email + contact scraper for yellowpages.com.eg and app.apollo.io")


def _build_pipeline(use_proxies: bool, headless: bool) -> object:
    from scraper.browser_client import Tier3Client
    from scraper.http_client import Tier1Client, Tier2Client
    from scraper.pipeline import Pipeline

    tiers = [Tier1Client(), Tier2Client()]
    if use_proxies:
        tiers.append(Tier3Client(headless=headless))
    return Pipeline(tiers=tiers)


def _build_proxy(use_proxies: bool) -> str | None:
    if not use_proxies:
        return None
    from free_proxy import FreeProxy  # type: ignore[import-untyped]
    from scraper.proxy_pool import ProxyPool

    raw = [FreeProxy().get() for _ in range(20)]
    pool = ProxyPool([p for p in raw if p])
    return pool.get()


@app.command()
def run_yp(
    category: str = typer.Option(..., help="YP category slug, e.g. 'restaurants'"),
    governorate: str = typer.Option("cairo", help="Governorate name"),
    limit: int = typer.Option(50, help="Max pages per category"),
    output_dir: str = typer.Option("output", help="Output directory"),
    use_proxies: bool = typer.Option(False, "--use-proxies", help="Enable free proxy pool"),
    headless: bool = typer.Option(True, help="Browser headless mode (Tier 3)"),
) -> None:
    """Scrape yellowpages.com.eg for a given category and governorate."""
    import structlog

    from scraper.config import Settings
    from scraper.csv_writer import CSVWriter
    from scraper.pipeline import Pipeline
    from scraper.rate_limiter import RateLimiter
    from scraper.sites.yellowpages_eg import scrape_category

    log = structlog.get_logger()
    cfg = Settings()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = out / f"yellowpages_eg_{category}_{governorate}_{ts}.csv"

    pipeline = _build_pipeline(use_proxies, headless)
    proxy = _build_proxy(use_proxies)
    rate_limiter = RateLimiter(
        min_delay=cfg.rate_limit_min_delay,
        max_delay=cfg.rate_limit_max_delay,
    )
    csv_writer = CSVWriter(csv_path)

    assert isinstance(pipeline, Pipeline)
    url = f"https://www.yellowpages.com.eg/{category}/{governorate}"
    log.info("starting_yp_scrape", url=url, output=str(csv_path))
    total = scrape_category(
        url,
        pipeline,
        csv_writer,
        rate_limiter,
        proxy=proxy,
        max_pages=limit,
        consecutive_empty_halt=cfg.consecutive_empty_halt,
    )
    typer.echo(f"Done. {total} rows written to {csv_path}")


@app.command()
def run_apollo(
    slug: str = typer.Argument(..., help="Apollo company slug"),
    output_dir: str = typer.Option("output", help="Output directory"),
    headless: bool = typer.Option(True, help="Browser headless mode"),
) -> None:
    """Scrape a single Apollo.io company page (POC, low yield)."""
    import structlog

    from scraper.browser_client import Tier3Client
    from scraper.csv_writer import CSVWriter
    from scraper.pipeline import Pipeline
    from scraper.sites.apollo_public import scrape_company

    log = structlog.get_logger()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = out / f"apollo_{slug}_{ts}.csv"

    pipeline = Pipeline(tiers=[Tier3Client(headless=headless)])
    csv_writer = CSVWriter(csv_path)

    log.info("starting_apollo_scrape", slug=slug)
    total = scrape_company(slug, pipeline, csv_writer)
    typer.echo(f"Done. {total} rows written to {csv_path}")


if __name__ == "__main__":
    app()
