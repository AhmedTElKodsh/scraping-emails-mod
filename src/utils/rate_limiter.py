"""
Rate limiting with randomized human-like delays.

Implements per-domain rate limiting (1-2 req/sec for protected sites)
and randomized delays (2-8 seconds) to mimic human behavior.
"""

import random
import time
from typing import Optional


class RateLimiter:
    """
    Rate limiter with randomized delays and per-domain tracking.
    Research doc recommendation: 1-2 req/sec for protected sites,
    randomized 2-8 second delays between requests.
    """

    def __init__(self, min_delay: float = 2.0, max_delay: float = 8.0,
                 per_domain_rate: dict[str, float] | None = None):
        """
        Args:
            min_delay: Minimum delay in seconds (default 2.0)
            max_delay: Maximum delay in seconds (default 8.0)
            per_domain_rate: Dict of domain -> max requests per second
                          e.g. {"yellowpages.com.eg": 1.5, "app.apollo.io": 0.5}
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.per_domain_rate = per_domain_rate or {
            "yellowpages.com.eg": 1.0,   # 1 req/sec (research doc: 1-2 req/sec)
            "app.apollo.io": 0.5,      # 0.5 req/sec (more aggressive anti-bot)
            "default": 2.0,            # 2 req/sec for unprotected
        }
        self.last_request: dict[str, float] = {}  # domain -> timestamp

    def human_delay(self, domain: Optional[str] = None) -> float:
        """
        Sleep for a random delay between min_delay and max_delay.
        Returns actual delay used.
        """
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
        return delay

    def wait_for_rate_limit(self, domain: str) -> None:
        """
        Wait if needed to respect per-domain rate limit.
        Call this before making a request to `domain`.
        """
        rate = self.per_domain_rate.get(domain, self.per_domain_rate.get("default", 2.0))
        interval = 1.0 / rate  # seconds between requests

        if domain in self.last_request:
            elapsed = time.time() - self.last_request[domain]
            if elapsed < interval:
                time.sleep(interval - elapsed)

    def request_delay(self, domain: str) -> float:
        """
        Complete delay: rate limit + random human delay.
        Call this before each request.
        Returns total delay used.
        """
        self.wait_for_rate_limit(domain)
        human = self.human_delay(domain)
        self.last_request[domain] = time.time()
        return human

    def jitter(self, base: float, variance: float = 0.3) -> float:
        """Add bounded random jitter to a base delay."""
        return base + random.uniform(-variance * base, variance * base)


class BoundedRandomizer:
    """
    Generate bounded random delays for specific anti-bot evasion scenarios.
    Research doc: "Network Timing -> Bounded randomization" layer.
    """

    @staticmethod
    def short() -> float:
        """Short delay for intra-page actions (0.5-2s)."""
        return random.uniform(0.5, 2.0)

    @staticmethod
    def medium() -> float:
        """Medium delay for between-page navigation (2-5s)."""
        return random.uniform(2.0, 5.0)

    @staticmethod
    def long() -> float:
        """Long delay for session resets or after errors (5-15s)."""
        return random.uniform(5.0, 15.0)

    @staticmethod
    def scroll_pause() -> float:
        """Simulate time spent reading/scrolling a page (3-8s)."""
        return random.uniform(3.0, 8.0)

    @staticmethod
    def between_actions() -> float:
        """Delay between individual actions (clicks, keystrokes) - 0.3-1.5s."""
        return random.uniform(0.3, 1.5)


if __name__ == "__main__":
    limiter = RateLimiter(min_delay=2.0, max_delay=8.0)
    print("Testing rate limiter...")
    domain = "yellowpages.com.eg"
    for i in range(3):
        delay = limiter.request_delay(domain)
        print(f"  Request {i+1}: delayed {delay:.2f}s")
    print(f"Short action delay: {BoundedRandomizer.short():.2f}s")
    print(f"Scroll pause: {BoundedRandomizer.scroll_pause():.2f}s")
