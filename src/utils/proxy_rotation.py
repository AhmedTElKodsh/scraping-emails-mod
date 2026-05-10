"""
Proxy rotation module.

Supports residential, datacenter, and mobile proxy pools.
Implements sticky sessions (same IP for N requests).
"""

import json
import os
import random
import time


class ProxyPool:
    """Manage proxy pools with sticky session support."""

    def __init__(self, proxies: dict[str, list[str]] | None = None):
        self.pools = proxies or {
            "datacenter": [],
            "residential": [],
            "mobile": [],
        }
        self.sticky_map: dict[str, tuple[str, int, float]] = {}
        self.sticky_requests = 10  # requests per sticky session
        self.sticky_ttl = 300  # seconds

    @classmethod
    def from_file(cls, filepath: str) -> "ProxyPool":
        """Load proxies from a JSON file grouped by pool type."""
        with open(filepath) as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def from_env(cls, env_var: str = "PROXIES") -> "ProxyPool":
        """Load proxies from environment variable (JSON string)."""
        raw = os.environ.get(env_var, "{}")
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        return cls(data)

    def add_proxy(self, proxy: str, pool_type: str = "datacenter") -> None:
        if pool_type not in self.pools:
            self.pools[pool_type] = []
        self.pools[pool_type].append(proxy)

    def get_proxy(
        self,
        pool_type: str = "residential",
        sticky_key: str | None = None,
    ) -> str | None:
        """
        Get proxy from pool. If sticky_key provided, reuse same proxy for N requests.
        sticky_key can be a domain, session ID, etc.
        """
        # Check sticky session
        if sticky_key and sticky_key in self.sticky_map:
            proxy, used, expiry = self.sticky_map[sticky_key]
            if used < self.sticky_requests and time.time() < expiry:
                self.sticky_map[sticky_key] = (proxy, used + 1, expiry)
                return proxy
            else:
                del self.sticky_map[sticky_key]  # expired or used up

        pool = self.pools.get(pool_type, [])
        if not pool:
            return None

        proxy = random.choice(pool)
        if sticky_key:
            self.sticky_map[sticky_key] = (proxy, 1, time.time() + self.sticky_ttl)
        return proxy

    def format_proxy(self, proxy: str) -> dict[str, str] | None:
        """Convert proxy string to requests/curl_cffi format."""
        if not proxy:
            return None
        return {"http": proxy, "https": proxy}

    def get_for_target(self, target: str) -> str | None:
        """
        Get appropriate proxy based on target site.
        yellowpages.com.eg -> residential (US-based)
        app.apollo.io -> mobile or residential
        """
        if "yellowpages.com.eg" in target or "yellowpages" in target:
            return self.get_proxy("residential", sticky_key=target)
        elif "apollo.io" in target:
            return self.get_proxy("mobile", sticky_key=target)
        return self.get_proxy("datacenter")


def load_proxies_from_file(filepath: str) -> ProxyPool:
    """Helper to load proxy pool from JSON file."""
    return ProxyPool.from_file(filepath)


if __name__ == "__main__":
    pool = ProxyPool.from_env()
    pool.add_proxy("http://user:pass@192.168.1.1:8080", "residential")
    pool.add_proxy("http://user:pass@mobile.proxy:8080", "mobile")
    proxy = pool.get_for_target("https://yellowpages.com.eg/")
    print(f"Selected proxy: {proxy}")
    # Sticky test
    key = "yellowpages.com.eg"
    p1 = pool.get_proxy("residential", sticky_key=key)
    p2 = pool.get_proxy("residential", sticky_key=key)
    print(f"Sticky works: {p1 == p2} (p1={p1}, p2={p2})")
