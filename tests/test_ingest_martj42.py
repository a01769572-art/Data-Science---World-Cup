from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from cdd_mundial.data.contracts import HistoricalMatchesSchema
from cdd_mundial.data.identities import TeamResolver
from cdd_mundial.data.ingest_martj42 import (
    DATASET_HANDLE,
    build_historical_matches,
    download_martj42,
)
from cdd_mundial.data.provenance import file_sha256


FIXTURE_ROOT = Path("tests/fixtures/martj42")


def test_download_captures_source_files_and_cc0_manifests(
    test_workspace: Path,
    monkeypatch,
) -> None:
    download_root = test_workspace / "kaggle-cache"
    download_root.mkdir()
    for filename in ("results.csv", "shootouts.csv", "former_names.csv"):
        (download_root / filename).write_text(f"name\n{filename}\n", encoding="utf-8")

    calls: list[str] = []

    def fake_dataset_download(handle: str) -> str:
        calls.append(handle)
        return str(download_root)

    monkeypatch.setattr(
        "cdd_mundial.data.ingest_martj42.kagglehub.dataset_download",
        fake_dataset_download,
    )
    raw_root = test_workspace / "data" / "raw" / "martj42"
    metadata_root = test_workspace / "data" / "metadata"

    captured = download_martj42(
        "fixture-v1",
        raw_root=raw_root,
        metadata_root=metadata_root,
        retrieved_at_utc=datetime(2026, 6, 11, 12, tzinfo=timezone.utc),
    )

    assert calls == [DATASET_HANDLE]
    assert set(captured) == {"results.csv", "shootouts.csv", "former_names.csv"}
    for filename, path in captured.items():
        assert path == raw_root / "fixture-v1" / filename
        assert path.read_bytes() == (download_root / filename).read_bytes()
        manifest = metadata_root / f"{filename}.provenance.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["license"] == "CC0-1.0"
        assert payload["sha256"] == file_sha256(path)


def test_build_historical_matches_preserves_source_semantics(test_workspace: Path) -> None:
    output_path = test_workspace / "historical_matches.parquet"

    built = build_historical_matches(
        FIXTURE_ROOT / "results.csv",
        FIXTURE_ROOT / "shootouts.csv",
        output_path=output_path,
        source_version="fixture-v1",
        resolver=TeamResolver.from_csv(),
    )
    reloaded = pd.read_parquet(output_path)
    HistoricalMatchesSchema.validate(reloaded)

    assert built["match_id"].is_unique
    assert built["home_team_source_name"].tolist() == ["Argentina", "Mexico", "Argentina"]
    assert built["away_team_source_name"].tolist() == ["Canada", "Brazil", "France"]
    assert built["neutral"].tolist() == [False, True, True]

    shootout = built.loc[built["shootout_winner_team_id"].notna()].iloc[0]
    assert (shootout["home_score"], shootout["away_score"]) == (3, 3)
    assert shootout["shootout_winner_team_id"] == "argentina"
    assert bool(shootout["result_after_extra_time"]) is True

    ordinary = built.loc[built["home_team_source_name"] == "Argentina"].iloc[0]
    assert pd.isna(ordinary["shootout_winner_team_id"])
    assert bool(ordinary["result_after_extra_time"]) is False


def test_collision_suffixes_are_deterministic(test_workspace: Path) -> None:
    duplicated_results = test_workspace / "results.csv"
    rows = pd.read_csv(FIXTURE_ROOT / "results.csv")
    pd.concat([rows.iloc[[0]], rows.iloc[[0]]], ignore_index=True).to_csv(
        duplicated_results,
        index=False,
    )

    built = build_historical_matches(
        duplicated_results,
        FIXTURE_ROOT / "shootouts.csv",
        output_path=test_workspace / "historical_matches.parquet",
        source_version="fixture-v1",
    )

    assert built["match_id"].tolist() == [
        "2022-11-22-argentina-canada",
        "2022-11-22-argentina-canada-2",
    ]
