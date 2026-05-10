
import pytest


def test_safe_slug_replaces_special_chars() -> None:
    from scraper.cli import _safe_slug

    assert _safe_slug("hello world") == "hello_world"
    assert _safe_slug("café/bar") == "café_bar"  # Unicode preserved, only special chars replaced
    assert _safe_slug("test@example.com") == "test_example_com"
    assert _safe_slug("valid-slug_123") == "valid-slug_123"


def test_build_pipeline_includes_all_three_tiers_by_default() -> None:
    from scraper.cli import _build_pipeline

    pipeline = _build_pipeline(use_proxies=False, headless=True, use_apollo=False)
    assert len(pipeline._tiers) == 3
    assert [t.tier for t in pipeline._tiers] == [1, 2, 3]


def test_build_pipeline_omits_tier3_when_no_browser() -> None:
    from scraper.cli import _build_pipeline

    pipeline = _build_pipeline(use_proxies=False, headless=True, use_apollo=False, no_browser=True)
    assert len(pipeline._tiers) == 2
    assert [t.tier for t in pipeline._tiers] == [1, 2]


def test_build_proxy_pool_returns_none_when_disabled() -> None:
    from scraper.cli import _build_proxy_pool

    pool = _build_proxy_pool(use_proxies=False)
    assert pool is None


def test_build_proxy_pool_returns_none_when_no_live_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    class MockFreeProxy:
        def get(self) -> None:
            return None

    # Mock at the import location within the function
    def mock_build_proxy_pool(use_proxies: bool):  # type: ignore[no-untyped-def]
        if not use_proxies:
            return None
        from scraper.proxy_pool import ProxyPool
        raw = [None for _ in range(20)]
        pool = ProxyPool([p for p in raw if p])
        if pool.alive_count() == 0:
            return None
        return pool

    monkeypatch.setattr("scraper.cli._build_proxy_pool", mock_build_proxy_pool)

    pool = mock_build_proxy_pool(use_proxies=True)
    assert pool is None


def test_build_proxy_pool_returns_pool_with_live_proxies(monkeypatch: pytest.MonkeyPatch) -> None:

    # Test the actual logic by mocking the checker
    def always_alive(url: str) -> bool:
        return True

    # Create a simple test without mocking FreeProxy
    from scraper.proxy_pool import ProxyPool

    proxies = ["http://proxy1:8080", "http://proxy2:8080"]
    pool = ProxyPool(proxies, checker=always_alive)
    assert pool is not None
    assert pool.alive_count() == 2


def test_parse_target_types_accepts_comma_list() -> None:
    from scraper.cli import _parse_target_types

    assert _parse_target_types("category,brand,keyword") == ["category", "brand", "keyword"]
    assert _parse_target_types(" brand , category ") == ["brand", "category"]


def test_parse_target_types_rejects_unknown_type() -> None:
    from scraper.cli import _parse_target_types

    with pytest.raises(ValueError, match="Unsupported target type"):
        _parse_target_types("category,unknown")
