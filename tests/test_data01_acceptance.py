from pathlib import Path

import pytest

from cdd_mundial.data.ingest_martj42 import verify_martj42_materialization


@pytest.mark.data_acceptance
def test_data01_real_martj42_materialization() -> None:
    summary = verify_martj42_materialization(data_root=Path("data"))

    assert summary["row_count"] > 49_000
    assert summary["team_count"] > 300
    assert summary["source_version"]
