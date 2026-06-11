from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def test_workspace() -> Path:
    """Return a unique workspace-local directory without relying on OS temp ACLs."""
    root = Path(".test-artifacts") / uuid4().hex
    root.mkdir(parents=True)
    return root


@pytest.fixture
def data_root(test_workspace: Path) -> Path:
    """Return an isolated data root for ingestion and provenance tests."""
    root = test_workspace / "data"
    root.mkdir()
    return root
