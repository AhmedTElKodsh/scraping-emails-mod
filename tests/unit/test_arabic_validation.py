"""Tests for Arabic text validation in scraping."""


def test_contains_arabic_detects_arabic_text() -> None:
    from scraper.sites.yellowpages_eg import _contains_arabic

    assert _contains_arabic("مطعم القاهرة") is True
    assert _contains_arabic("Cairo Restaurant") is False
    assert _contains_arabic("مطعم Cairo") is True  # Mixed
    assert _contains_arabic("") is False
    assert _contains_arabic("123") is False


def test_parse_detail_validates_arabic_fields() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    # Arabic page with Arabic text
    arabic_html = """
    <html>
        <h1 class="companyName">مطعم القاهرة</h1>
        <div class="companyName-category">مطاعم</div>
        <div class="company-address"><span>شارع التحرير، القاهرة</span></div>
    </html>
    """
    result = parse_detail(arabic_html, "https://yellowpages.com.eg/ar/profile/test/123")
    
    assert result.business_name == "مطعم القاهرة"
    assert result.business_name_ar == "مطعم القاهرة"
    assert result.category_ar == "مطاعم"
    assert result.address_ar == "شارع التحرير، القاهرة"


def test_parse_detail_rejects_english_on_arabic_page() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    # Arabic page URL but English content (edge case)
    english_html = """
    <html>
        <h1 class="companyName">Cairo Restaurant</h1>
        <div class="companyName-category">Restaurants</div>
        <div class="company-address"><span>Tahrir Street, Cairo</span></div>
    </html>
    """
    result = parse_detail(english_html, "https://yellowpages.com.eg/ar/profile/test/123")
    
    assert result.business_name == "Cairo Restaurant"
    # Should NOT populate Arabic fields since text is English
    assert result.business_name_ar == ""
    assert result.category_ar == ""
    assert result.address_ar == ""


def test_parse_detail_english_page() -> None:
    from scraper.sites.yellowpages_eg import parse_detail

    english_html = """
    <html>
        <h1 class="companyName">Cairo Restaurant</h1>
        <div class="companyName-category">Restaurants</div>
        <div class="company-address"><span>Tahrir Street, Cairo</span></div>
    </html>
    """
    result = parse_detail(english_html, "https://yellowpages.com.eg/en/profile/test/123")
    
    assert result.business_name == "Cairo Restaurant"
    # English page should not populate Arabic fields
    assert result.business_name_ar == ""
    assert result.category_ar == ""
    assert result.address_ar == ""
