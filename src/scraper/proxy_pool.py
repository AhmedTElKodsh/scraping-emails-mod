import random
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _ProxyEntry:
    url: str
    failures: int = 0


class ProxyPool:
    def __init__(
        self,
        proxies: list[str],
        checker: Callable[[str], bool] | None = None,
        max_failures: int = 3,
        sticky_count: int = 15,
    ) -> None:
        self._checker = checker or self._default_check
        self._max_failures = max_failures
        self._sticky_count = sticky_count
        # Filter out empty, whitespace-only, and invalid proxy URLs
        self._pool: list[_ProxyEntry] = [
            _ProxyEntry(url=p.strip()) 
            for p in proxies 
            if p and p.strip() and self._is_valid_proxy_format(p.strip()) and self._checker(p.strip())
        ]
        self._current: _ProxyEntry | None = None
        self._current_uses: int = 0

    @staticmethod
    def _is_valid_proxy_format(proxy_url: str) -> bool:
        """Basic validation of proxy URL format."""
        return proxy_url.startswith(("http://", "https://", "socks4://", "socks5://"))

    @staticmethod
    def _default_check(proxy_url: str) -> bool:
        import urllib.error
        import urllib.request

        try:
            req = urllib.request.Request(
                "https://httpbin.org/ip",
                headers={"User-Agent": "curl/7.88.1"},
            )
            handler = urllib.request.ProxyHandler({"https": proxy_url, "http": proxy_url})
            opener = urllib.request.build_opener(handler)
            opener.open(req, timeout=3)
            return True
        except (urllib.error.URLError, OSError):
            return False

    def get(self) -> str | None:
        if not self._pool:
            return None
        if self._current is None or self._current_uses >= self._sticky_count:
            self._rotate()
        if self._current is None:
            return None
        self._current_uses += 1
        return self._current.url

    def _rotate(self) -> None:
        alive = [p for p in self._pool if p.failures < self._max_failures]
        if not alive:
            self._current = None
            return
        self._current = random.choice(alive)
        self._current_uses = 0

    def record_failure(self, proxy_url: str) -> None:
        for p in self._pool:
            if p.url == proxy_url:
                p.failures += 1
                if (
                    p.failures >= self._max_failures
                    and self._current
                    and self._current.url == proxy_url
                ):
                    self._current = None
                break

    def alive_count(self) -> int:
        return sum(1 for p in self._pool if p.failures < self._max_failures)
