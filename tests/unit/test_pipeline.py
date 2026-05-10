import pytest

from scraper.http_client import BaseClient, Response


class OkClient(BaseClient):
    tier = 1

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        return Response(status_code=200, text="<html>content</html>", headers={}, tier=self.tier)


class FailClient(BaseClient):
    tier = 1

    def __init__(self, status: int = 403, body: str = "just a moment") -> None:
        self._status = status
        self._body = body

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        return Response(status_code=self._status, text=self._body, headers={}, tier=1)


class CountClient(BaseClient):
    tier = 1

    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        self.calls += 1
        return Response(status_code=403, text="just a moment", headers={}, tier=1)


def test_tier1_success_returns_response() -> None:
    from scraper.pipeline import Pipeline

    p = Pipeline(tiers=[OkClient()])
    resp = p.fetch("https://example.com")
    assert resp.status_code == 200
    assert resp.tier == 1


def test_tier1_fail_escalates_to_tier2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import Pipeline

    tier2 = OkClient()
    tier2.tier = 2
    p = Pipeline(tiers=[FailClient(), tier2], max_retries=1)
    resp = p.fetch("https://example.com")
    assert resp.tier == 2


def test_all_tiers_fail_raises_blocked_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import BlockedError, Pipeline

    p = Pipeline(tiers=[FailClient(), FailClient()], max_retries=1)
    with pytest.raises(BlockedError):
        p.fetch("https://example.com")


def test_max_retries_per_tier_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import BlockedError, Pipeline

    counter = CountClient()
    p = Pipeline(tiers=[counter], max_retries=3)
    with pytest.raises(BlockedError):
        p.fetch("https://example.com")
    assert counter.calls == 3


def test_404_does_not_escalate() -> None:
    from scraper.pipeline import Pipeline

    not_found = FailClient(status=404, body="not found page")
    tier2 = OkClient()
    tier2.tier = 2
    p = Pipeline(tiers=[not_found, tier2], max_retries=1)
    resp = p.fetch("https://example.com")
    assert resp.status_code == 404
    assert resp.tier == 1


def test_backoff_delays_are_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda s: sleeps.append(s))

    from scraper.pipeline import BlockedError, Pipeline

    p = Pipeline(tiers=[FailClient()], max_retries=3)
    with pytest.raises(BlockedError):
        p.fetch("https://example.com")

    assert sleeps == [5, 15, 45]
