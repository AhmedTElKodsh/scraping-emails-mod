import time


def test_wait_calls_delay_fn() -> None:
    from scraper.rate_limiter import RateLimiter

    calls: list[float] = []

    def fake_delay() -> float:
        calls.append(0.0)
        return 0.0

    rl = RateLimiter(delay_fn=fake_delay)
    rl.wait()
    assert len(calls) == 1


def test_wait_returns_delay_used() -> None:
    from scraper.rate_limiter import RateLimiter

    rl = RateLimiter(delay_fn=lambda: 0.0)
    result = rl.wait()
    assert result == 0.0


def test_default_delay_within_bounds() -> None:
    from scraper.rate_limiter import RateLimiter

    rl = RateLimiter(min_delay=0.001, max_delay=0.002)
    delay = rl.wait()
    assert 0.001 <= delay <= 0.002


def test_injected_delay_fn_skips_sleep() -> None:
    from scraper.rate_limiter import RateLimiter

    start = time.monotonic()
    rl = RateLimiter(delay_fn=lambda: 0.0)
    for _ in range(10):
        rl.wait()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_jitter_distribution() -> None:
    from scraper.rate_limiter import RateLimiter

    rl = RateLimiter(min_delay=2.0, max_delay=8.0)
    delays = [rl._delay_fn() for _ in range(100)]
    assert all(2.0 <= d <= 8.0 for d in delays)
    assert min(delays) < 4.0
    assert max(delays) > 5.0
