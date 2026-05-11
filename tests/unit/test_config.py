import subprocess
import sys

import pytest
from pydantic import ValidationError


def test_defaults_load_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_MIN_DELAY", raising=False)
    from scraper.config import Settings
    s = Settings()
    assert s.rate_limit_min_delay == 2.0
    assert s.rate_limit_max_delay == 8.0
    assert s.max_retries_per_tier == 3
    assert s.use_proxies is False
    assert s.output_dir == "output"
    assert s.db_path == "data/scraper.sqlite"
    assert s.acquisition_db_path == "data/acquisition.sqlite"
    assert s.consecutive_empty_halt == 5


def test_settings_import_is_fast() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import time; "
                "start = time.perf_counter(); "
                "from scraper.config import Settings; "
                "print(time.perf_counter() - start)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert float(result.stdout.strip()) < 2.5


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_MIN_DELAY", "1.5")
    monkeypatch.setenv("MAX_RETRIES_PER_TIER", "5")
    from importlib import reload

    import scraper.config as cfg_module
    reload(cfg_module)
    s = cfg_module.Settings()
    assert s.rate_limit_min_delay == 1.5
    assert s.max_retries_per_tier == 5


def test_dotenv_override(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath(".env").write_text(
        "RATE_LIMIT_MAX_DELAY=3.5\nBROWSER_HEADLESS=false\n",
        encoding="utf-8",
    )

    from scraper.config import Settings

    s = Settings()

    assert s.rate_limit_max_delay == 3.5
    assert s.browser_headless is False


def test_invalid_delay_raises() -> None:
    from scraper.config import Settings
    with pytest.raises(ValidationError):
        Settings(rate_limit_min_delay=0.1)  # below ge=0.5


def test_invalid_retries_raises() -> None:
    from scraper.config import Settings
    with pytest.raises(ValidationError):
        Settings(max_retries_per_tier=0)  # below ge=1
