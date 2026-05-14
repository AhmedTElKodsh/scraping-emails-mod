from datetime import UTC, datetime, timedelta

import pytest


def test_response_ok_property() -> None:
    from scraper.http_client import Response

    assert Response(200, "", {}, 1).ok is True
    assert Response(299, "", {}, 1).ok is True
    assert Response(199, "", {}, 1).ok is False
    assert Response(300, "", {}, 1).ok is False
    assert Response(404, "", {}, 1).ok is False


def test_response_is_challenge_by_status() -> None:
    from scraper.http_client import Response

    assert Response(0, "", {}, 1).is_challenge() is True
    assert Response(403, "", {}, 1).is_challenge() is True
    assert Response(429, "", {}, 1).is_challenge() is True
    # 503 without challenge markers should NOT be a challenge
    assert Response(503, "Internal Server Error", {}, 1).is_challenge() is False
    # 503 with challenge markers should be a challenge
    assert Response(503, "cf-challenge", {}, 1).is_challenge() is True
    assert Response(200, "", {}, 1).is_challenge() is False


def test_response_is_challenge_by_body() -> None:
    from scraper.http_client import Response

    assert Response(200, "cf-challenge", {}, 1).is_challenge() is True
    assert Response(200, "_cf_chl", {}, 1).is_challenge() is True
    assert Response(200, "cf_browser", {}, 1).is_challenge() is True
    assert Response(200, "just a moment cloudflare", {}, 1).is_challenge() is True
    assert Response(200, "attention required verify", {}, 1).is_challenge() is True
    assert Response(200, "just a moment", {}, 1).is_challenge() is False
    assert Response(200, "attention required", {}, 1).is_challenge() is False
    assert Response(200, "normal content", {}, 1).is_challenge() is False


def test_response_is_challenge_limits_scan_size() -> None:
    from scraper.http_client import Response

    # Large body with trigger at the end (beyond 100KB) should not be detected
    large_body = "x" * 200000 + "cf-challenge"
    resp = Response(200, large_body, {}, 1)
    # Should not find the trigger because it's beyond the scan limit
    assert resp.is_challenge() is False

    # Trigger within first 100KB should be detected
    body_with_early_trigger = "cf-challenge" + "x" * 200000
    resp2 = Response(200, body_with_early_trigger, {}, 1)
    assert resp2.is_challenge() is True


def test_tier2_clearance_valid_when_fresh() -> None:
    from scraper.http_client import Tier2Client

    client = Tier2Client()
    client._clearance_cookie = "test_cookie"
    client._clearance_at = datetime.now(UTC)
    assert client.is_clearance_valid() is True


def test_tier2_clearance_invalid_when_expired() -> None:
    from scraper.http_client import Tier2Client

    client = Tier2Client()
    client._clearance_cookie = "test_cookie"
    client._clearance_at = datetime.now(UTC) - timedelta(seconds=2000)
    assert client.is_clearance_valid() is False


def test_tier2_clearance_invalid_when_none() -> None:
    from scraper.http_client import Tier2Client

    client = Tier2Client()
    assert client.is_clearance_valid() is False


def test_tier2_clearance_invalid_with_clock_skew() -> None:
    from scraper.http_client import Tier2Client

    client = Tier2Client()
    client._clearance_cookie = "test_cookie"
    # Future timestamp (clock skew) - should now be invalid due to negative age
    client._clearance_at = datetime.now(UTC) + timedelta(seconds=100)
    assert client.is_clearance_valid() is False


def test_tier2_clearance_valid_at_zero_age() -> None:
    """Test that freshly obtained clearance (age=0) is valid."""
    from scraper.http_client import Tier2Client

    client = Tier2Client()
    client._clearance_cookie = "test_cookie"
    client._clearance_at = datetime.now(UTC)
    # Should be valid immediately (age >= 0)
    assert client.is_clearance_valid() is True


def test_tier1_returns_response_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from scraper.http_client import Tier1Client

    class MockResponse:
        status_code = 200
        text = "<html>content</html>"
        headers = {"Content-Type": "text/html"}

    def mock_get(*args, **kwargs):  # type: ignore[no-untyped-def]
        return MockResponse()

    monkeypatch.setattr("curl_cffi.requests.get", mock_get)

    client = Tier1Client()
    resp = client.get("https://example.com")
    assert resp.status_code == 200
    assert resp.tier == 1
    assert "content" in resp.text


def test_tier1_returns_error_response_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    from scraper.http_client import Tier1Client

    def mock_get(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ConnectionError("Network error")

    monkeypatch.setattr("curl_cffi.requests.get", mock_get)

    client = Tier1Client()
    resp = client.get("https://example.com")
    assert resp.status_code == 0
    assert resp.tier == 1
    assert resp.text == ""
