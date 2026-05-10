"""
TLS fingerprint impersonation wrapper.

Provides curl_cffi-based HTTP client with browser TLS fingerprint spoofing.
Impersonates Chrome, Firefox, Safari, Edge TLS stacks.
"""

import random
from typing import Any, cast

# Try to import curl_cffi; fall back gracefully
try:
    from curl_cffi import requests as curl_requests

    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    curl_requests = None  # type: ignore[assignment]

# Supported browsers and versions (update as curl-impersonate updates)
SUPPORTED_BROWSERS = {
    "chrome": [
        "chrome100",
        "chrome101",
        "chrome104",
        "chrome107",
        "chrome110",
        "chrome116",
        "chrome120",
        "chrome131",
        "chrome136",
    ],
    "firefox": [
        "firefox100",
        "firefox102",
        "firefox104",
        "firefox110",
        "firefox115",
        "firefox133",
    ],
    "safari": ["safari15.5", "safari16.5", "safari17.0", "safari18.4"],
    "edge": ["edge101", "edge122", "edge136"],
}

DEFAULT_BROWSER = "chrome136"  # Research doc recommends chrome136 for 2025-2026
CHROME_136_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


def create_session(browser: str = DEFAULT_BROWSER, use_curl_cffi: bool = True) -> Any:
    """
    Create an HTTP session with browser TLS impersonation.
    Falls back to standard requests if curl_cffi not available.
    """
    if browser and use_curl_cffi and CURL_CFFI_AVAILABLE:
        cffi_requests = cast(Any, curl_requests)
        return cffi_requests.Session()
    import requests

    return requests.Session()


def get(url: str, impersonate: str = DEFAULT_BROWSER, **kwargs: Any) -> Any:
    """
    Make a GET request with TLS impersonation.
    Matches curl_cffi API: get(url, impersonate="chrome136", ...)
    """
    if CURL_CFFI_AVAILABLE:
        cffi_requests = cast(Any, curl_requests)
        return cffi_requests.get(url, impersonate=impersonate, **kwargs)
    import requests

    return requests.get(url, **kwargs)


def post(url: str, impersonate: str = DEFAULT_BROWSER, **kwargs: Any) -> Any:
    """Make a POST request with TLS impersonation."""
    if CURL_CFFI_AVAILABLE:
        cffi_requests = cast(Any, curl_requests)
        return cffi_requests.post(url, impersonate=impersonate, **kwargs)
    import requests

    return requests.post(url, **kwargs)


def random_browser() -> str:
    """Pick a random browser+version from supported list."""
    all_browsers = []
    for versions in SUPPORTED_BROWSERS.values():
        all_browsers.extend(versions)
    return random.choice(all_browsers)


def get_for_target(target: str) -> tuple[str, str]:
    """
    Get recommended (browser, user_agent_hint) for target site.
    Based on research doc findings:
    - yellowpages.com.eg: chrome136 (best success rate)
    - app.apollo.io: chrome136 (modern TLS fingerprint)
    """
    if "yellowpages" in target:
        return "chrome136", CHROME_136_UA
    if "apollo" in target:
        return "chrome136", CHROME_136_UA
    return (
        DEFAULT_BROWSER,
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )


if __name__ == "__main__":
    if CURL_CFFI_AVAILABLE:
        print("curl_cffi available. Testing TLS impersonation...")
        try:
            resp = get("https://example.com", impersonate="chrome136")
            print(f"Status: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("curl_cffi not installed. pip install curl-cffi")
    print(f"Random browser: {random_browser()}")
    print(f"For yellowpages: {get_for_target('yellowpages.com.eg')}")
