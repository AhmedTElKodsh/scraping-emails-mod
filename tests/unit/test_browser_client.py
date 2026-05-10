"""Unit tests for Tier3Client — all Playwright interactions mocked."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from scraper.browser_client import Tier3Client


def _make_pw_stack(
    status: int = 200,
    content: str = "<html>ok</html>",
    resp_headers: dict | None = None,
):
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.headers = resp_headers or {"content-type": "text/html"}

    mock_page = MagicMock()
    mock_page.goto.return_value = mock_resp
    mock_page.content.return_value = content

    mock_ctx = MagicMock()
    mock_ctx.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_ctx

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_sync_pw = MagicMock()
    mock_sync_pw.return_value.__enter__.return_value = mock_pw
    mock_sync_pw.return_value.__exit__.return_value = False

    return mock_sync_pw, mock_page, mock_ctx, mock_browser, mock_pw


def test_stealth_applied_before_goto() -> None:
    mock_sync_pw, mock_page, mock_ctx, mock_browser, _ = _make_pw_stack()
    call_order: list[str] = []
    original_goto_rv = mock_page.goto.return_value

    def track_goto(*a: object, **kw: object) -> object:
        call_order.append("goto")
        return original_goto_rv

    mock_page.goto.side_effect = track_goto

    mock_stealth_instance = MagicMock()
    mock_stealth_instance.apply_stealth_sync.side_effect = lambda _: call_order.append("stealth")
    mock_stealth_cls = MagicMock(return_value=mock_stealth_instance)

    with patch("playwright.sync_api.sync_playwright", mock_sync_pw), patch(
        "playwright_stealth.Stealth", mock_stealth_cls
    ):
        Tier3Client().get("https://example.com")

    assert call_order == ["stealth", "goto"]


def test_ctx_and_browser_closed_on_success() -> None:
    mock_sync_pw, mock_page, mock_ctx, mock_browser, _ = _make_pw_stack()

    with patch("playwright.sync_api.sync_playwright", mock_sync_pw), patch(
        "playwright_stealth.Stealth"
    ):
        Tier3Client().get("https://example.com")

    mock_ctx.close.assert_called_once()
    mock_browser.close.assert_called_once()


def test_ctx_and_browser_closed_on_exception() -> None:
    mock_sync_pw, mock_page, mock_ctx, mock_browser, _ = _make_pw_stack()
    mock_page.goto.side_effect = Exception("network error")

    with patch("playwright.sync_api.sync_playwright", mock_sync_pw), patch(
        "playwright_stealth.Stealth"
    ):
        resp = Tier3Client().get("https://example.com")

    assert resp.status_code == 0
    assert resp.text == ""
    mock_ctx.close.assert_called_once()
    mock_browser.close.assert_called_once()


def test_headers_populated_from_response() -> None:
    headers = {"content-type": "text/html", "x-custom": "value"}
    mock_sync_pw, _, _, _, _ = _make_pw_stack(resp_headers=headers)

    with patch("playwright.sync_api.sync_playwright", mock_sync_pw), patch(
        "playwright_stealth.Stealth"
    ):
        resp = Tier3Client().get("https://example.com")

    assert resp.headers == headers


def test_proxy_passed_to_launch() -> None:
    mock_sync_pw, _, _, _, mock_pw = _make_pw_stack()

    with patch("playwright.sync_api.sync_playwright", mock_sync_pw), patch(
        "playwright_stealth.Stealth"
    ):
        Tier3Client().get("https://example.com", proxy="http://proxy:8080")

    mock_pw.chromium.launch.assert_called_once_with(
        headless=True, proxy={"server": "http://proxy:8080"}
    )


def test_no_proxy_when_none() -> None:
    mock_sync_pw, _, _, _, mock_pw = _make_pw_stack()

    with patch("playwright.sync_api.sync_playwright", mock_sync_pw), patch(
        "playwright_stealth.Stealth"
    ):
        Tier3Client().get("https://example.com", proxy=None)

    mock_pw.chromium.launch.assert_called_once_with(headless=True, proxy=None)


def test_tier_is_3() -> None:
    assert Tier3Client.tier == 3
