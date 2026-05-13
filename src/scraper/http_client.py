from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, cast

import structlog

from scraper.fingerprint import get_profile
from scraper.models import FingerprintProfile

log = structlog.get_logger()


class Response:
    def __init__(self, status_code: int, text: str, headers: dict[str, str], tier: int) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self.tier = tier

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def is_challenge(self) -> bool:
        if self.status_code in (0, 403, 429, 500, 503):
            return True
        # Check Cloudflare-specific markers before scanning generic text.
        body_sample = ((self.text or "") or "")[:100000]
        for marker in ("cf-challenge", "_cf_chl", "cf_browser"):
            if marker in body_sample:
                return True
        body_lower = body_sample.lower()
        if "just a moment" in body_lower and "cloudflare" in body_lower:
            return True
        if "attention required" in body_lower and "verify" in body_lower:
            return True
        return False


class BaseClient(ABC):
    tier: int = 0

    @abstractmethod
    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response: ...


def _browser_headers(profile: FingerprintProfile, referer: str | None = None) -> dict[str, str]:
    h = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": profile.accept_language,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-CH-UA": profile.sec_ch_ua,
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": profile.user_agent,
    }
    if referer:
        h["Referer"] = referer
    return h


class Tier1Client(BaseClient):
    tier = 1

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        from curl_cffi import requests as cffi_requests

        profile = get_profile()
        proxies = {"https": proxy, "http": proxy} if proxy else None
        try:
            cffi_get = cast(Any, cffi_requests.get)
            resp = cffi_get(
                url,
                impersonate=profile.impersonate,
                headers=_browser_headers(profile, referer=referer),
                proxies=cast(Any, proxies),
                timeout=20,
                allow_redirects=True,
            )
            log.info("tier1_request", url=url, status=resp.status_code, proxy=proxy)
            return Response(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(cast(Any, resp.headers)),
                tier=1,
            )
        except Exception as exc:
            log.warning("tier1_error", url=url, error=str(exc), exc_type=type(exc).__name__)
            return Response(status_code=0, text="", headers={}, tier=1)


class Tier2Client(BaseClient):
    tier = 2
    _CLEARANCE_TTL = 1800  # 30 minutes

    def __init__(self) -> None:
        self._clearance_cookie: str | None = None
        self._clearance_at: datetime | None = None

    def is_clearance_valid(self) -> bool:
        if self._clearance_cookie is None or self._clearance_at is None:
            return False
        age = (datetime.now(UTC) - self._clearance_at).total_seconds()
        return 0 < age < self._CLEARANCE_TTL

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        import cloudscraper

        profile = get_profile()
        proxies = {"https": proxy, "http": proxy} if proxy else None
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True},
            delay=5,
        )
        scraper.headers.update(_browser_headers(profile, referer=referer))
        
        # Inject stored clearance cookie if valid
        if self.is_clearance_valid() and self._clearance_cookie:
            scraper.cookies.set("cf_clearance", self._clearance_cookie)
            log.debug("tier2_reusing_clearance", url=url)
        
        if proxies:
            scraper.proxies.update(proxies)
        try:
            resp = scraper.get(url, timeout=20)
            cf_cookie = scraper.cookies.get("cf_clearance")
            if cf_cookie:
                self._clearance_cookie = cf_cookie
                self._clearance_at = datetime.now(UTC)
            log.info(
                "tier2_request",
                url=url,
                status=resp.status_code,
                has_clearance=bool(cf_cookie),
                reused_clearance=self.is_clearance_valid(),
            )
            return Response(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                tier=2,
            )
        except Exception as exc:
            log.warning("tier2_error", url=url, error=str(exc), exc_type=type(exc).__name__)
            return Response(status_code=0, text="", headers={}, tier=2)
