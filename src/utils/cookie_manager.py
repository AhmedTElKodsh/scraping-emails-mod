"""
Cookie management utilities.

Extract, save, and load cookies from cloudscraper sessions.
Convert between cloudscraper cookie dict and curl_cffi cookie formats.
"""

import json
import os
from typing import Any, cast


def extract_cookies_from_cloudscraper(scraper: Any) -> dict[str, Any]:
    """
    Extract cookies from a cloudscraper session.
    Returns dict suitable for curl_cffi or requests.
    """
    return cast(dict[str, Any], scraper.cookies.get_dict())


def get_cookie_string(scraper: Any) -> tuple[str, str]:
    """
    Get (cookie_string, user_agent) from cloudscraper, ready for HTTP headers.
    Matches cloudscraper's built-in get_cookie_string() and get_tokens().
    """
    try:
        # Try using cloudscraper's built-in method
        cookie_str = scraper.get_cookie_string()
        ua = scraper.headers.get("User-Agent", "")
        return cookie_str, ua
    except AttributeError:
        # Fallback: build manually
        cookies = scraper.cookies.get_dict()
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        ua = scraper.headers.get("User-Agent", "")
        return cookie_str, ua


def get_tokens(scraper: Any) -> dict[str, Any]:
    """
    Get Cloudflare tokens (cf_clearance, __cfduid) from cloudscraper session.
    Returns dict with token values.
    """
    try:
        return cast(dict[str, Any], scraper.get_tokens())
    except AttributeError:
        cookies = scraper.cookies.get_dict()
        return {k: v for k, v in cookies.items() if k in ("cf_clearance", "__cfduid", "__cf_bm")}


def save_cookies(cookies: dict[str, Any], filepath: str) -> None:
    """Save cookies dict to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(cookies, f, indent=2)


def load_cookies(filepath: str) -> dict[str, Any]:
    """Load cookies dict from JSON file."""
    try:
        with open(filepath) as f:
            return cast(dict[str, Any], json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def cookies_to_header(cookies: dict[str, Any]) -> str:
    """Convert cookies dict to Cookie header string."""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def inject_cookies_to_curl_cffi(curl_session: Any, cookies: dict[str, Any]) -> None:
    """
    Inject cookies into a curl_cffi session.
    Usage: create a curl_cffi session, then call this with a cookies dict.
    """
    for name, value in cookies.items():
        curl_session.cookies.set(name, value)


def save_session(scraper: Any, filepath: str) -> None:
    """
    Save a cloudscraper session (cookies + user-agent) to file.
    Format: {"cookies": {...}, "user_agent": "..."}
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    tokens = get_tokens(scraper)
    ua = scraper.headers.get("User-Agent", "")
    data = {"cookies": tokens, "user_agent": ua}
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_session(filepath: str) -> dict[str, Any]:
    """Load session data from file."""
    try:
        with open(filepath) as f:
            return cast(dict[str, Any], json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


if __name__ == "__main__":
    # Test save/load
    test_cookies = {"cf_clearance": "test123", "__cfduid": "abc456"}
    save_cookies(test_cookies, "/tmp/test_cookies.json")
    loaded = load_cookies("/tmp/test_cookies.json")
    print(f"Cookies round-trip: {loaded == test_cookies}")
    print(f"Header: {cookies_to_header(loaded)}")
