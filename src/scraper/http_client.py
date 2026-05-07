from abc import ABC, abstractmethod
from datetime import datetime, timezone

import structlog

from scraper.fingerprint import get_profile

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
        triggers = ["cf-challenge", "just a moment", "attention required", "_cf_chl"]
        body_lower = self.text.lower()
        return self.status_code in (403, 429, 503) or any(t in body_lower for t in triggers)


class BaseClient(ABC):
    tier: int = 0

    @abstractmethod
    def get(self, url: str, proxy: str | None = None) -> Response: ...


class Tier1Client(BaseClient):
    tier = 1

    def get(self, url: str, proxy: str | None = None) -> Response:
        from curl_cffi import requests as cffi_requests  # type: ignore[import-untyped]

        profile = get_profile()
        proxies = {"https": proxy, "http": proxy} if proxy else None
        try:
            resp = cffi_requests.get(
                url,
                impersonate=profile.impersonate,
                headers={
                    "Accept-Language": profile.accept_language,
                    "Sec-CH-UA": profile.sec_ch_ua,
                    "User-Agent": profile.user_agent,
                },
                proxies=proxies,
                timeout=15,
            )
            log.info("tier1_request", url=url, status=resp.status_code, proxy=proxy)
            return Response(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                tier=1,
            )
        except Exception as exc:
            log.warning("tier1_error", url=url, error=str(exc))
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
        age = (datetime.now(timezone.utc) - self._clearance_at).total_seconds()
        return age < self._CLEARANCE_TTL

    def get(self, url: str, proxy: str | None = None) -> Response:
        import cloudscraper  # type: ignore[import-untyped]

        proxies = {"https": proxy, "http": proxy} if proxy else None
        scraper = cloudscraper.create_scraper()
        if proxies:
            scraper.proxies.update(proxies)
        try:
            resp = scraper.get(url, timeout=20)
            cf_cookie = scraper.cookies.get("cf_clearance")
            if cf_cookie:
                self._clearance_cookie = cf_cookie
                self._clearance_at = datetime.now(timezone.utc)
            log.info(
                "tier2_request",
                url=url,
                status=resp.status_code,
                has_clearance=bool(cf_cookie),
            )
            return Response(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                tier=2,
            )
        except Exception as exc:
            log.warning("tier2_error", url=url, error=str(exc))
            return Response(status_code=0, text="", headers={}, tier=2)
