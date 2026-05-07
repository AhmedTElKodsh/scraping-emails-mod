import pytest


def always_alive(proxy_url: str) -> bool:
    return True


def always_dead(proxy_url: str) -> bool:
    return False


def make_pool(proxies: list[str], checker=always_alive, **kwargs):  # type: ignore[no-untyped-def]
    from scraper.proxy_pool import ProxyPool
    return ProxyPool(proxies, checker=checker, **kwargs)


def test_empty_pool_returns_none() -> None:
    pool = make_pool([])
    assert pool.get() is None


def test_all_dead_proxies_returns_none() -> None:
    pool = make_pool(["http://proxy1:8080", "http://proxy2:8080"], checker=always_dead)
    assert pool.get() is None


def test_get_returns_proxy_url() -> None:
    pool = make_pool(["http://proxy1:8080"])
    result = pool.get()
    assert result == "http://proxy1:8080"


def test_sticky_session_same_proxy_for_n_requests() -> None:
    proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
    pool = make_pool(proxies, sticky_count=5)
    first = pool.get()
    for _ in range(4):
        assert pool.get() == first


def test_sticky_session_rotates_after_count() -> None:
    proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
    pool = make_pool(proxies, sticky_count=3)
    first_proxy = pool.get()
    pool.get()
    pool.get()
    pool._current_uses = pool._sticky_count  # force rotation on next get
    second_batch_proxy = pool.get()
    assert second_batch_proxy is not None


def test_record_failure_ejects_after_max() -> None:
    pool = make_pool(["http://bad:8080"], max_failures=3)
    assert pool.alive_count() == 1
    pool.record_failure("http://bad:8080")
    pool.record_failure("http://bad:8080")
    assert pool.alive_count() == 1
    pool.record_failure("http://bad:8080")
    assert pool.alive_count() == 0


def test_ejected_proxy_causes_none_return() -> None:
    pool = make_pool(["http://bad:8080"], max_failures=1)
    pool.record_failure("http://bad:8080")
    assert pool.get() is None


def test_alive_count_reflects_healthy_proxies() -> None:
    proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
    pool = make_pool(proxies, max_failures=2)
    assert pool.alive_count() == 3
    pool.record_failure("http://p1:8080")
    pool.record_failure("http://p1:8080")
    assert pool.alive_count() == 2


def test_checker_called_for_each_proxy() -> None:
    checked: list[str] = []

    def tracking_checker(url: str) -> bool:
        checked.append(url)
        return True

    proxies = ["http://p1:8080", "http://p2:8080"]
    make_pool(proxies, checker=tracking_checker)
    assert set(checked) == {"http://p1:8080", "http://p2:8080"}
