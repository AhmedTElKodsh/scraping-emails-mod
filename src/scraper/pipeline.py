import time

import structlog

from scraper.http_client import BaseClient, Response

log = structlog.get_logger()

_BACKOFF = [5, 15, 45]


class BlockedError(Exception):
    pass


class Pipeline:
    def __init__(self, tiers: list[BaseClient], max_retries: int = 3) -> None:
        self._tiers = tiers
        self._max_retries = max_retries

    def fetch(self, url: str, proxy: str | None = None) -> Response:
        for client in self._tiers:
            tier_n = client.tier
            for attempt in range(self._max_retries):
                log.info("fetch_attempt", url=url, tier=tier_n, attempt=attempt + 1)
                resp = client.get(url, proxy=proxy)
                if not resp.is_challenge():
                    log.info("fetch_success", url=url, tier=tier_n)
                    return resp
                backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                log.warning(
                    "fetch_failed",
                    url=url,
                    tier=tier_n,
                    attempt=attempt + 1,
                    status=resp.status_code,
                    backoff=backoff,
                )
                time.sleep(backoff)
            log.error("tier_exhausted", url=url, tier=tier_n)

        log.error("fetch_blocked", url=url)
        raise BlockedError(f"All tiers exhausted for {url}")
