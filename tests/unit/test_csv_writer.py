import csv
from pathlib import Path

from scraper.models import ScrapeResult


def make_result(**kwargs: object) -> ScrapeResult:
    defaults = {
        "url": "https://example.com/biz",
        "business_name": "Test Biz",
        "category": "Food",
        "governorate": "Cairo",
        "phone": "+20221234567",
        "emails": ["info@testbiz.com"],
        "website": "https://testbiz.com",
        "address": "123 Test St",
    }
    defaults.update(kwargs)
    return ScrapeResult(**defaults)  # type: ignore[arg-type]


def test_creates_file_with_header(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    writer.write(make_result())

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 1
    assert "email" in rows[0]
    assert "business_name" in rows[0]


def test_dedup_same_url_same_run(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    writer.write(make_result(url="https://example.com/biz/1", emails=["a@a.com"]))
    writer.write(make_result(url="https://example.com/biz/1", emails=["b@b.com"]))

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 1


def test_dedup_email_across_urls_case_insensitive(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    writer.write(make_result(url="https://example.com/biz/1", emails=["Info@Example.COM"]))
    written = writer.write(
        make_result(url="https://example.com/biz/2", emails=["info@example.com"])
    )
    assert written == 1
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 2
    assert rows[1]["email"] == ""


def test_resume_dedups_url(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    w1 = CSVWriter(path)
    w1.write(make_result(url="https://example.com/biz/1", emails=["first@example.com"]))

    w2 = CSVWriter(path)
    written = w2.write(make_result(url="https://example.com/biz/1", emails=["first@example.com"]))
    assert written == 0

    new_written = w2.write(
        make_result(url="https://example.com/biz/2", emails=["second@example.com"])
    )
    assert new_written == 1


def test_no_duplicate_header_on_append(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    CSVWriter(path).write(make_result(url="https://example.com/biz/1", emails=["a@a.com"]))
    CSVWriter(path).write(make_result(url="https://example.com/biz/2", emails=["b@b.com"]))

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    header_count = sum(1 for line in lines if line.startswith("business_name"))
    assert header_count == 1


def test_arabic_business_name_utf8(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    writer.write(make_result(business_name="مطعم القاهرة", emails=["cairo@example.com"]))

    content = path.read_text(encoding="utf-8")
    assert "مطعم القاهرة" in content


def test_result_with_no_email_writes_empty_row(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    written = writer.write(make_result(emails=[]))
    assert written == 1

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["email"] == ""


def test_multiple_emails_write_multiple_rows(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    written = writer.write(make_result(emails=["a@a.com", "b@b.com"]))
    assert written == 2

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 2


def test_seen_count_reflects_total(tmp_path: Path) -> None:
    from scraper.csv_writer import CSVWriter

    path = tmp_path / "out.csv"
    writer = CSVWriter(path)
    writer.write(make_result(emails=["a@a.com", "b@b.com"]))
    assert writer.seen_count == 2
