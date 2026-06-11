from pathlib import Path

import pytest


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """Return an isolated data root for ingestion and provenance tests."""
    root = tmp_path / "data"
    root.mkdir()
    return root

