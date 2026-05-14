"""Tests for CSV export with Arabic data."""

import csv
from pathlib import Path

import pytest


def test_csv_writer_handles_arabic_text(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter
    from scraper.models import ScrapeResult

    path = tmp_path / "arabic_test.csv"
    writer = CSVWriter(path)
    
    result = ScrapeResult(
        url="https://example.com/biz/1",
        business_name="مطعم القاهرة",
        category="مطاعم",
        governorate="القاهرة",
        address="شارع التحرير",
        phone="0123456789",
        emails=["info@cairo-restaurant.com"],
    )
    
    written = writer.write(result)
    assert written == 1
    
    # Read back and verify Arabic text is preserved
    content = path.read_text(encoding="utf-8-sig")
    assert "مطعم القاهرة" in content
    assert "مطاعم" in content
    assert "القاهرة" in content
    assert "شارع التحرير" in content


def test_csv_writer_utf8_sig_encoding(tmp_path: Path) -> None:
    """Verify UTF-8-SIG encoding for Excel compatibility."""
    from scraper.csv_writer import CSVWriter
    from scraper.models import ScrapeResult

    path = tmp_path / "encoding_test.csv"
    writer = CSVWriter(path)
    
    result = ScrapeResult(
        url="https://example.com/biz/1",
        business_name="مطعم",
        emails=["test@example.com"],
    )
    
    writer.write(result)
    
    # Check for BOM (UTF-8-SIG marker)
    raw_bytes = path.read_bytes()
    assert raw_bytes[:3] == b'\xef\xbb\xbf'  # UTF-8 BOM


def test_csv_writer_mixed_arabic_english(tmp_path: Path) -> None:
    """Test CSV with mixed Arabic and English content."""
    from scraper.csv_writer import CSVWriter
    from scraper.models import ScrapeResult

    path = tmp_path / "mixed_test.csv"
    writer = CSVWriter(path)
    
    # Arabic business
    writer.write(ScrapeResult(
        url="https://example.com/biz/1",
        business_name="مطعم القاهرة",
        emails=["arabic@example.com"],
    ))
    
    # English business
    writer.write(ScrapeResult(
        url="https://example.com/biz/2",
        business_name="Cairo Restaurant",
        emails=["english@example.com"],
    ))
    
    rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    assert len(rows) == 2
    assert rows[0]["business_name"] == "مطعم القاهرة"
    assert rows[1]["business_name"] == "Cairo Restaurant"


def test_csv_writer_no_duplicate_headers_on_concurrent_writes(tmp_path: Path) -> None:
    """Test that concurrent writes don't create duplicate headers."""
    from scraper.csv_writer import CSVWriter
    from scraper.models import ScrapeResult

    path = tmp_path / "concurrent_test.csv"
    
    # First writer creates file
    writer1 = CSVWriter(path)
    writer1.write(ScrapeResult(
        url="https://example.com/biz/1",
        business_name="Business 1",
        emails=["test1@example.com"],
    ))
    
    # Second writer appends (simulating concurrent access)
    writer2 = CSVWriter(path)
    writer2.write(ScrapeResult(
        url="https://example.com/biz/2",
        business_name="Business 2",
        emails=["test2@example.com"],
    ))
    
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_count = sum(1 for line in lines if line.startswith("business_name"))
    assert header_count == 1, "Should have exactly one header row"
