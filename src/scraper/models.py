from pydantic import BaseModel


class FingerprintProfile(BaseModel):
    impersonate: str
    user_agent: str
    accept_language: str
    sec_ch_ua: str
    viewport_width: int
    viewport_height: int


class ScrapeResult(BaseModel):
    url: str
    business_name: str = ""
    category: str = ""
    governorate: str = ""
    phone: str = ""
    emails: list[str] = []
    website: str = ""
    address: str = ""
    source_tier: int = 0
    scraped_at: str = ""
    raw_html_hash: str = ""
