import csv
from pathlib import Path


def _write_existing_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "business_name",
        "target_type",
        "target_slug",
        "city_slug",
        "source_url",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_existing_csv_page_resume_starts_after_full_pages(tmp_path: Path) -> None:
    import run_local_scrape

    path = tmp_path / "existing.csv"
    _write_existing_csv(
        path,
        [
            {
                "business_name": f"Biz {index}",
                "target_type": "keyword",
                "target_slug": "استيراد",
                "city_slug": "",
                "source_url": f"https://example.com/{index}",
            }
            for index in range(40)
        ],
    )

    assert run_local_scrape._existing_page_resume(path, "keyword", "استيراد", "") == 3


def test_existing_csv_page_resume_starts_at_one_for_missing_category(tmp_path: Path) -> None:
    import run_local_scrape

    path = tmp_path / "existing.csv"
    _write_existing_csv(
        path,
        [
            {
                "business_name": "Import Biz",
                "target_type": "keyword",
                "target_slug": "استيراد",
                "city_slug": "",
                "source_url": "https://example.com/import",
            }
        ],
    )

    assert (
        run_local_scrape._existing_page_resume(
            path,
            "category",
            "factory-equipment-and-supplies",
            "",
        )
        == 1
    )
