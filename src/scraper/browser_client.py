from typing import Any, cast

import structlog

from scraper.fingerprint import get_profile
from scraper.http_client import BaseClient, Response

log = structlog.get_logger()


class Tier3Client(BaseClient):
    tier = 3

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
    ) -> None:
        self._headless = headless
        self._timeout = timeout_ms

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        profile = get_profile()
        proxy_settings = {"server": proxy} if proxy else None

        browser = None
        ctx = None
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(
                    headless=self._headless,
                    proxy=cast(Any, proxy_settings),
                )
                ctx = browser.new_context(
                    user_agent=profile.user_agent,
                    viewport={"width": profile.viewport_width, "height": profile.viewport_height},
                    locale="en-US",
                )
                page = ctx.new_page()
                Stealth().apply_stealth_sync(page)
                if referer:
                    page.set_extra_http_headers({"Referer": referer})
                resp = page.goto(url, timeout=self._timeout, wait_until="domcontentloaded")
                status = resp.status if resp else 0
                headers = dict(resp.headers) if resp else {}
                text = page.content()
                # Limit content size to prevent memory exhaustion
                if len(text) > 10_000_000:
                    log.warning("tier3_content_truncated", url=url, original_size=len(text))
                    text = text[:10_000_000]
                log.info("tier3_request", url=url, status=status)
                return Response(status_code=status, text=text, headers=headers, tier=3)
            except Exception as exc:
                log.warning("tier3_error", url=url, error=str(exc), exc_type=type(exc).__name__)
                return Response(status_code=0, text="", headers={}, tier=3)
            finally:
                if ctx:
                    ctx.close()
                if browser:
                    browser.close()
