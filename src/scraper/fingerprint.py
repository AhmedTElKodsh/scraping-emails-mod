import random

from scraper.models import FingerprintProfile

# Randomize viewport to reduce fingerprinting
_VIEWPORTS = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
]

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
    """Get fingerprint profile with randomized viewport to reduce bot detection."""
    width, height = random.choice(_VIEWPORTS)
    return FingerprintProfile(
        impersonate=_CHROME_136.impersonate,
        user_agent=_CHROME_136.user_agent,
        accept_language=_CHROME_136.accept_language,
        sec_ch_ua=_CHROME_136.sec_ch_ua,
        viewport_width=width,
        viewport_height=height,
    )
