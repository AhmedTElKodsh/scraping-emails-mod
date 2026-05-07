import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_decode_cfemail_known_vectors() -> None:
    from scraper.email_extract import decode_cfemail

    samples = json.loads((FIXTURES / "cfemail_samples.json").read_text())
    for sample in samples:
        result = decode_cfemail(sample["encoded"])
        assert result == sample["expected"], (
            f"encoded={sample['encoded']!r} → got {result!r}, expected {sample['expected']!r}"
        )


def test_decode_cfemail_invalid_hex_raises() -> None:
    from scraper.email_extract import decode_cfemail

    with pytest.raises(ValueError):
        decode_cfemail("zzzz")


def test_decode_cfemail_empty_raises() -> None:
    from scraper.email_extract import decode_cfemail

    with pytest.raises((ValueError, IndexError)):
        decode_cfemail("")


def test_extract_emails_standard_regex() -> None:
    from scraper.email_extract import extract_emails

    html = '<p>Contact us at info@example.com or support@example.org</p>'
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert "info@example.com" in result
    assert "support@example.org" in result
    assert len(result) == 2


def test_extract_emails_deduplication() -> None:
    from scraper.email_extract import extract_emails

    html = '<p>info@example.com and INFO@EXAMPLE.COM and info@example.com</p>'
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert result == ["info@example.com"]


def test_extract_emails_global_seen_set() -> None:
    from scraper.email_extract import extract_emails

    seen: set[str] = {"info@example.com"}
    html = '<p>info@example.com and other@example.com</p>'
    result = extract_emails(html, seen)
    assert result == ["other@example.com"]
    assert "info@example.com" in seen
    assert "other@example.com" in seen


def test_extract_emails_cfemail_attribute() -> None:
    from scraper.email_extract import extract_emails

    encoded = "007465737440746573742e636f6d"  # test@test.com with key=0x00
    html = f'<span class="__cf_email__" data-cfemail="{encoded}">...</span>'
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert "test@test.com" in result


def test_extract_emails_obfuscated_at() -> None:
    from scraper.email_extract import extract_emails

    html = "contact us at info [at] example.com or sales(at)store.eg"
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert "info@example.com" in result
    assert "sales@store.eg" in result


def test_extract_emails_mailto_href() -> None:
    from scraper.email_extract import extract_emails

    html = '<a href="mailto:booking@hotel.eg">Email us</a>'
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert "booking@hotel.eg" in result


def test_extract_emails_rejects_junk_prefixes() -> None:
    from scraper.email_extract import extract_emails

    html = "noreply@example.com and no-reply@example.com and donotreply@example.com"
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert result == []


def test_extract_emails_rejects_malformed() -> None:
    from scraper.email_extract import extract_emails

    html = "not_an_email and @nodomain and noatsign.com"
    seen: set[str] = set()
    result = extract_emails(html, seen)
    assert result == []
