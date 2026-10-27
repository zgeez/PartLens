from datetime import UTC, datetime
from pathlib import Path

import pytest

from partlens.core.bom import import_bom_csv
from partlens.sources.catalog import LocalCatalog

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def catalog() -> LocalCatalog:
    return LocalCatalog.from_json(FIXTURES / "catalog.json")


@pytest.fixture
def bom():
    return import_bom_csv(FIXTURES / "bom_kicad.csv")


@pytest.fixture
def now() -> datetime:
    return NOW
