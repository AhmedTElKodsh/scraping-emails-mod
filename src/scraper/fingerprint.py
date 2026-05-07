from scraper.models import FingerprintProfile

_CHROME_136 = FingerprintProfile(
    impersonate="chrome136",
    user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    accept_language="en-US,en;q=0.9,ar;q=0.8",
    sec_ch_ua='"Chromium";v="136", "Google Chrome";v="136", "Not-A.Brand";v="99"',
    viewport_width=1920,
    viewport_height=1080,
)


def get_profile() -> FingerprintProfile:
    return _CHROME_136
