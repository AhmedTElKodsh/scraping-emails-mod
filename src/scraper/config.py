import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


class Settings(BaseModel):
    rate_limit_min_delay: float = Field(2.0, ge=0.5)
    rate_limit_max_delay: float = Field(8.0, ge=1.0)
    max_retries_per_tier: int = Field(3, ge=1)

    use_proxies: bool = False
    proxy_timeout: float = Field(3.0, ge=0.5)
    proxy_sticky_count: int = Field(15, ge=5)
    proxy_max_failures: int = Field(3, ge=1)

    # HTTP client timeouts
    tier1_timeout: int = Field(15, ge=5)
    tier2_timeout: int = Field(20, ge=5)

    output_dir: str = "output"

    max_pages_per_category: int = Field(50, ge=1)
    consecutive_empty_halt: int = Field(5, ge=1)

    browser_timeout_ms: int = Field(30000, ge=5000)
    browser_headless: bool = True

    # Storage + mass crawl
    database_url: str = ""
    db_path: str = "data/scraper.sqlite"
    acquisition_db_path: str = "data/acquisition.sqlite"
    mass_crawl_max_pages: int = Field(20, ge=1)
    taxonomy_seed_path: str = "data/taxonomy_seed.json"

    def __init__(self, **data: Any) -> None:
        env_file_values = _read_env_file(Path(".env"))
        env_values = {
            name: os.environ[env_name]
            for name in type(self).model_fields
            if (env_name := name.upper()) in os.environ
        }
        file_values = {
            name: env_file_values[env_name]
            for name in type(self).model_fields
            if (env_name := name.upper()) in env_file_values
        }

        super().__init__(**file_values, **env_values, **data)
