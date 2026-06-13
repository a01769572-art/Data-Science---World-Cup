"""Reproducibility + full-publication-chain invariants for the official run (LIVE-01..04, DOC-02).

These tests prove the *first official publication chain* end to end on an isolated
data root, then prove it is reproducible under a fixed seed and append-only after
publication:

1. One official command runs the full chain in order -- results validation ->
   immutable live-training materialization -> model fingerprint + reuse/refit ->
   conditioned simulation -> snapshot staging -> frozen market benchmark ->
   authoritative ledger append + snapshot-local calibration slice -> report
   render/assets -> checksum aggregation -> one-shot metadata finalization ->
   atomic publish.
2. The published ``metadata.json`` carries the nested provenance + boundary fields
   the operator interface depends on (``generated_at_utc``, ``kickoff_boundary_utc``,
   ``git_commit``, ``git_dirty``, ``live_training_provenance``, ``model_provenance``,
   ``seed``, ``preflight``, ``publication_row_ids``, ``checksums``).
3. The same canonical inputs + seed reproduce identical materialized live-training
   fingerprints, identical critical snapshot tables, and stable deterministic row
   ids/checksums for the calibration slice; only the allowed timestamps differ.
4. ``--verify-only`` never writes a published snapshot.
5. No file inside a published snapshot is mutated after publication.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

from cdd_mundial.live.pipeline import run_official, verify_official

REAL_HISTORY = Path("data/processed/historical_matches.parquet")
REAL_FIXTURE = Path("data/external/fixture_2026.csv")
REAL_RESULTS = Path("data/external/results_2026.csv")


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #


def _isolated_data_root(test_workspace: Path) -> Path:
    data_root = test_workspace / "data"
    dst = data_root / "processed" / "historical_matches.parquet"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL_HISTORY, dst)
    return data_root


def _manual_odds_csv(workspace: Path) -> Path:
    """A tiny valid manual-odds slice for the next-block future fixtures.

    Covers a couple of unresolved future group matches so the frozen benchmark
    and the calibration ledger are non-empty (publication_row_ids >= 1). Team
    display names follow the ``odds`` source aliases.
    """
    path = workspace / "manual_odds.csv"
    rows = [
        # WC26-007 brazil vs morocco (future kickoff in the canonical fixture)
        {
            "provider": "manual",
            "bookmaker": "book-a",
            "event_id": "EVT-007-A",
            "match_id": "WC26-007",
            "commence_time_utc": "2026-06-13T22:00:00Z",
            "provider_update_utc": "",
            "home_team": "Brazil",
            "away_team": "Morocco",
            "price_home": "1.55",
            "price_draw": "4.10",
            "price_away": "6.20",
        },
        {
            "provider": "manual",
            "bookmaker": "book-b",
            "event_id": "EVT-007-B",
            "match_id": "WC26-007",
            "commence_time_utc": "2026-06-13T22:00:00Z",
            "provider_update_utc": "",
            "home_team": "Brazil",
            "away_team": "Morocco",
            "price_home": "1.60",
            "price_draw": "4.00",
            "price_away": "6.00",
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _run(
    data_root: Path,
    snapshots_root: Path,
    *,
    seed: int,
    manual_odds: Path,
    snapshot_id: str = "snap",
) -> dict:
    # Short snapshot id keeps nested staging paths under the Windows MAX_PATH (260)
    # limit given the deep test-workspace prefix; the real run uses dated ids.
    return run_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=snapshots_root,
        manual_odds_path=manual_odds,
        n_sims=48,
        seed=seed,
        as_of=None,
        allow_dirty=True,
        _snapshot_id=snapshot_id,
    )


# --------------------------------------------------------------------------- #
# Full publication chain + metadata surface                                   #
# --------------------------------------------------------------------------- #


def test_official_run_publishes_full_chain_with_nested_metadata(test_workspace: Path) -> None:
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "s"
    odds = _manual_odds_csv(test_workspace)

    summary = _run(data_root, snapshots_root, seed=20260613, manual_odds=odds)
    snapshot_dir = Path(summary["snapshot_dir"])
    assert snapshot_dir.exists()

    # Required frozen artifacts + report bundle exist.
    for name in (
        "team_probabilities.parquet",
        "upcoming_match_predictions.parquet",
        "frozen_benchmark.parquet",
        "report.html",
    ):
        assert (snapshot_dir / name).exists(), name
    assert (snapshot_dir / "report_inputs" / "calibration_publication_slice.parquet").exists()
    assert (snapshot_dir / "assets").is_dir()

    # The authoritative ledger was appended under the isolated data root.
    ledger = data_root / "processed" / "live" / "calibration" / "calibration_matches.parquet"
    assert ledger.exists()
    ledger_df = pd.read_parquet(ledger)
    assert int(ledger_df.duplicated(subset=["snapshot_id", "match_id"]).sum()) == 0
    assert len(ledger_df) >= 1

    meta = json.loads((snapshot_dir / "metadata.json").read_text(encoding="utf-8"))
    # Nested provenance + boundary fields the operator interface depends on.
    assert meta["generated_at_utc"].endswith("Z")
    assert meta["kickoff_boundary_utc"].endswith("Z")
    assert meta["git_commit"]
    assert isinstance(meta["git_dirty"], bool)
    assert len(meta["live_training_provenance"]["artifact_sha256"]) == 64
    assert meta["live_training_provenance"]["artifact_path"]
    assert len(meta["model_provenance"]["input_fingerprint"]) == 64
    assert len(meta["model_provenance"]["artifact_sha256"]) == 64
    assert meta["seed"] == 20260613
    assert meta["preflight"]
    assert len(meta["publication_row_ids"]) >= 1
    assert "team_probabilities.parquet" in meta["checksums"]
    # Pre-kickoff invariant: snapshot generated before the boundary it races.
    assert meta["generated_at_utc"] < meta["kickoff_boundary_utc"]


def test_materialize_runs_before_simulation_and_report(test_workspace: Path) -> None:
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "s"
    odds = _manual_odds_csv(test_workspace)
    summary = _run(data_root, snapshots_root, seed=7, manual_odds=odds)
    meta = json.loads((Path(summary["snapshot_dir"]) / "metadata.json").read_text(encoding="utf-8"))
    assert meta["order"] == ["materialize", "select_model", "simulate", "publish"]
    # Live-training artifact + fingerprint are recorded, proving materialize-before-decide.
    assert meta["live_training_provenance"]["artifact_path"]
    assert meta["model_provenance"]["input_fingerprint"]


# --------------------------------------------------------------------------- #
# Reproducibility under a fixed seed                                           #
# --------------------------------------------------------------------------- #


def test_same_seed_reproduces_tables_and_fingerprints(test_workspace: Path) -> None:
    odds = _manual_odds_csv(test_workspace)
    root_a = _isolated_data_root(test_workspace / "a")
    root_b = _isolated_data_root(test_workspace / "b")
    snaps_a = test_workspace / "a" / "s"
    snaps_b = test_workspace / "b" / "s"

    sum_a = _run(root_a, snaps_a, seed=20260613, manual_odds=odds)
    sum_b = _run(root_b, snaps_b, seed=20260613, manual_odds=odds)

    dir_a = Path(sum_a["snapshot_dir"])
    dir_b = Path(sum_b["snapshot_dir"])
    meta_a = json.loads((dir_a / "metadata.json").read_text(encoding="utf-8"))
    meta_b = json.loads((dir_b / "metadata.json").read_text(encoding="utf-8"))

    # Identical materialized live-training fingerprints (same canonical inputs).
    assert (
        meta_a["live_training_provenance"]["artifact_sha256"]
        == meta_b["live_training_provenance"]["artifact_sha256"]
    )
    assert meta_a["model_provenance"]["input_fingerprint"] == meta_b["model_provenance"]["input_fingerprint"]

    # Identical critical snapshot tables under a fixed seed.
    tp_a = pd.read_parquet(dir_a / "team_probabilities.parquet")
    tp_b = pd.read_parquet(dir_b / "team_probabilities.parquet")
    pd.testing.assert_frame_equal(tp_a, tp_b)

    # Stable deterministic row ids for the calibration slice.
    assert sorted(meta_a["publication_row_ids"]) == sorted(meta_b["publication_row_ids"])


def test_verify_only_writes_no_snapshot(test_workspace: Path) -> None:
    data_root = _isolated_data_root(test_workspace)
    snaps = test_workspace / "s"
    summary = verify_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=snaps,
        as_of=None,
        allow_dirty=True,
    )
    assert summary["published"] is False
    assert not snaps.exists() or not any(p.is_dir() for p in snaps.iterdir())


# --------------------------------------------------------------------------- #
# Append-only: no post-publication mutation                                   #
# --------------------------------------------------------------------------- #


def test_published_snapshot_is_not_mutated_on_rerun(test_workspace: Path) -> None:
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "s"
    odds = _manual_odds_csv(test_workspace)
    summary = _run(data_root, snapshots_root, seed=99, manual_odds=odds)
    snapshot_dir = Path(summary["snapshot_dir"])

    before = {
        p.name: p.read_bytes()
        for p in snapshot_dir.iterdir()
        if p.is_file()
    }

    # Re-publishing the exact same snapshot id is append-only -> fails loud,
    # either at the ledger append (duplicate snapshot/match key) or the snapshot
    # rename (destination already exists). Both prove append-only discipline.
    with pytest.raises((FileExistsError, ValueError)):
        run_official(
            results_path=REAL_RESULTS,
            fixture_path=REAL_FIXTURE,
            data_root=data_root,
            snapshots_root=snapshots_root,
            manual_odds_path=odds,
            n_sims=48,
            seed=99,
            as_of=None,
            allow_dirty=True,
            _snapshot_id=summary["snapshot_id"],
        )

    after = {
        p.name: p.read_bytes()
        for p in snapshot_dir.iterdir()
        if p.is_file()
    }
    assert before == after
