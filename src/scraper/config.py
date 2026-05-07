from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rate_limit_min_delay: float = Field(2.0, ge=0.5)
    rate_limit_max_delay: float = Field(8.0, ge=1.0)
    max_retries_per_tier: int = Field(3, ge=1)

    use_proxies: bool = False
    proxy_timeout: float = Field(3.0, ge=0.5)
    proxy_sticky_count: int = Field(15, ge=5)
    proxy_max_failures: int = Field(3, ge=1)

    output_dir: str = "output"

    max_pages_per_category: int = Field(50, ge=1)
    consecutive_empty_halt: int = Field(5, ge=1)

    browser_timeout_ms: int = Field(30000, ge=5000)
    browser_headless: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
