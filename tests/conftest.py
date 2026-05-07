import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration: mark test as integration (requires live network or services)"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end (live network, slow, non-deterministic)"
    )