import pytest

from scraper.http_client import BaseClient, Response

pytestmark = pytest.mark.integration


class MockTier1Blocked(BaseClient):
    tier = 1

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        return Response(status_code=403, text="just a moment", headers={}, tier=1)


class MockTier2Blocked(BaseClient):
    tier = 2

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        return Response(status_code=403, text="just a moment", headers={}, tier=2)


class MockTier2Success(BaseClient):
    tier = 2

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        return Response(status_code=200, text="<html>success from tier2</html>", headers={}, tier=2)


class MockTier3Success(BaseClient):
    tier = 3

    def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
        return Response(status_code=200, text="<html>success from tier3</html>", headers={}, tier=3)


def test_tier1_blocked_escalates_to_tier2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import Pipeline

    p = Pipeline(tiers=[MockTier1Blocked(), MockTier2Success()], max_retries=1)
    resp = p.fetch("https://example.com")
    assert resp.tier == 2
    assert "tier2" in resp.text


def test_tier1_and_tier2_blocked_escalates_to_tier3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import Pipeline

    p = Pipeline(
        tiers=[MockTier1Blocked(), MockTier2Blocked(), MockTier3Success()], max_retries=1
    )
    resp = p.fetch("https://example.com")
    assert resp.tier == 3


def test_cf_200_with_challenge_body_triggers_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 status with CF challenge HTML must still escalate — not treated as success."""
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import Pipeline

    class Tier1CF200(BaseClient):
        tier = 1

        def get(self, url: str, proxy: str | None = None, referer: str | None = None) -> Response:
            return Response(
                status_code=200,
                text="<html>_cf_chl</html>",
                headers={},
                tier=1,
            )

    p = Pipeline(tiers=[Tier1CF200(), MockTier2Success()], max_retries=1)
    resp = p.fetch("https://example.com")
    assert resp.tier == 2


def test_all_three_tiers_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scraper.pipeline.time.sleep", lambda _: None)
    from scraper.pipeline import BlockedError, Pipeline

    p = Pipeline(
        tiers=[MockTier1Blocked(), MockTier2Blocked(), MockTier1Blocked()], max_retries=1
    )
    with pytest.raises(BlockedError):
        p.fetch("https://example.com")
