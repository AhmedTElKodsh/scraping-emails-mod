from pydantic import BaseModel, Field


class FingerprintProfile(BaseModel):
    impersonate: str
    user_agent: str
    accept_language: str
    sec_ch_ua: str
    viewport_width: int
    viewport_height: int


class Facet(BaseModel):
    type: str
    slug: str
    name: str = ""
    name_ar: str = ""


class ScrapeResult(BaseModel):
    url: str
    business_name: str = ""
    business_name_ar: str = ""
    category: str = ""
    category_ar: str = ""
    governorate: str = ""
    governorate_ar: str = ""
    phone: str = ""
    emails: list[str] = Field(default_factory=list)
    website: str = ""
    facebook_url: str = ""
    address: str = ""
    address_ar: str = ""
    source_tier: int = 0
    scraped_at: str = ""
    raw_html_hash: str = ""
    facets: list[Facet] = Field(default_factory=list)
