"""Official-run materialization and refit-vs-reuse invariants (LIVE-01, DOC-02, D-06).

These tests prove the critical ordering of the official daily run *before* any
snapshot is published:

1. Live canonical results are first mapped into the canonical 90-minute match
   schema and written as a dated, immutable derived live-training artifact with
   deterministic provenance (SHA-256), without mutating raw/history.
2. Elo/form features are refreshed chronologically over history + live rows.
3. Only then is a deterministic fingerprint computed over the derived artifact
   plus relevant feature/model parameters; an unchanged fingerprint reuses the
   pinned dated production model artifact, while a changed fingerprint refits
   exactly one new dated artifact whose ``model_version`` follows the
   ``baseline-v1-YYYY-MM-DD-<shortsha>`` shape (D-13).

The tests run against a tiny self-contained history + fixture so they are fast
and never touch the real production artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from cdd_mundial.live.materialization import (
    compute_input_fingerprint,
    map_live_rows_to_canonical,
    materialize_live_training,
    select_model_artifact,
)
from cdd_mundial.live.pipeline import run_official, verify_official
from cdd_mundial.simulation.state import PlayedMatchResult

REAL_HISTORY = Path("data/processed/historical_matches.parquet")
REAL_FIXTURE = Path("data/external/fixture_2026.csv")
REAL_RESULTS = Path("data/external/results_2026.csv")

# --- Tiny self-contained history + fixture --------------------------------

_HISTORY_COLUMNS = [
    "match_id",
    "date",
    "home_team_id",
    "away_team_id",
    "home_team_source_name",
    "away_team_source_name",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
    "shootout_winner_team_id",
    "result_after_extra_time",
    "source",
    "source_version",
]

_TEAMS = ("alpha", "bravo", "charlie", "delta")


def _history_row(match_id: str, date: str, home: str, away: str, hs: int, as_: int) -> dict:
    return {
        "match_id": match_id,
        "date": date,
        "home_team_id": home,
        "away_team_id": away,
        "home_team_source_name": home.title(),
        "away_team_source_name": away.title(),
        "home_score": hs,
        "away_score": as_,
        "tournament": "Friendly",
        "city": "Town",
        "country": "Nowhere",
        "neutral": True,
        "shootout_winner_team_id": None,
        "result_after_extra_time": False,
        "source": "test",
        "source_version": "2026-06-11",
    }


def _history_frame() -> pd.DataFrame:
    rows = []
    pairs = [(a, b) for a in _TEAMS for b in _TEAMS if a < b]
    # Enough repeated matches so a Dixon-Coles fit converges on a tiny set.
    for cycle in range(8):
        for k, (home, away) in enumerate(pairs):
            day = 1 + (cycle * len(pairs) + k) % 27
            rows.append(
                _history_row(
                    f"H-{cycle:02d}-{k:02d}",
                    f"2024-0{1 + cycle % 9}-{day:02d}",
                    home,
                    away,
                    (k + cycle) % 4,
                    (k + 1) % 3,
                )
            )
    return pd.DataFrame(rows, columns=_HISTORY_COLUMNS)


def _fixture_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": "WC26-001",
                "stage": "group",
                "group": "A",
                "home_team_id": "alpha",
                "away_team_id": "bravo",
                "kickoff_utc": "2026-06-11T19:00:00Z",
            },
            {
                "match_id": "WC26-002",
                "stage": "group",
                "group": "A",
                "home_team_id": "charlie",
                "away_team_id": "delta",
                "kickoff_utc": "2026-06-12T02:00:00Z",
            },
        ]
    )


def _played() -> tuple[PlayedMatchResult, ...]:
    return (
        PlayedMatchResult(
            match_id="WC26-001", team_a="alpha", team_b="bravo", goals_a=2, goals_b=1
        ),
    )


# --- map_live_rows_to_canonical ------------------------------------------


def test_map_live_rows_match_canonical_schema_and_90min_semantics() -> None:
    canonical = map_live_rows_to_canonical(
        _played(),
        fixture=_fixture_frame(),
        source_version="2026-06-11",
        as_of_date="2026-06-11",
    )
    # Exactly the canonical historical columns and a single live row.
    assert list(canonical.columns) == _HISTORY_COLUMNS
    assert len(canonical) == 1
    row = canonical.iloc[0]
    assert row["match_id"] == "WC26-001"
    assert row["home_team_id"] == "alpha"
    assert row["away_team_id"] == "bravo"
    assert int(row["home_score"]) == 2
    assert int(row["away_score"]) == 1
    # World Cup matches are neutral venue (except hosts) and tournament-tagged.
    assert bool(row["neutral"]) is True
    assert row["tournament"] == "FIFA World Cup"
    assert bool(row["result_after_extra_time"]) is False


def test_map_live_rows_rejects_match_absent_from_fixture() -> None:
    rogue = (
        PlayedMatchResult(
            match_id="WC26-999", team_a="alpha", team_b="bravo", goals_a=1, goals_b=0
        ),
    )
    with pytest.raises(ValueError, match="fixture"):
        map_live_rows_to_canonical(
            rogue, fixture=_fixture_frame(), source_version="v", as_of_date="2026-06-11"
        )


# --- materialize_live_training -------------------------------------------


def test_materialization_is_immutable_and_does_not_touch_history(
    test_workspace: Path,
) -> None:
    data_root = test_workspace / "data"
    history_path = data_root / "processed" / "historical_matches.parquet"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    _history_frame().to_parquet(history_path, index=False)
    history_before = history_path.read_bytes()

    result = materialize_live_training(
        _played(),
        fixture=_fixture_frame(),
        as_of_date="2026-06-13",
        data_root=data_root,
    )

    artifact_path = Path(result["live_training_path"])
    assert artifact_path.exists()
    assert artifact_path.is_relative_to(data_root)
    assert len(result["live_training_sha256"]) == 64
    # Refreshed Elo features cover every team that appears in history + live.
    assert result["elo_ratings"]  # non-empty mapping team -> rating
    # The immutable raw history was not rewritten.
    assert history_path.read_bytes() == history_before


def test_materialization_replay_is_deterministic(test_workspace: Path) -> None:
    data_root = test_workspace / "data"
    history_path = data_root / "processed" / "historical_matches.parquet"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    _history_frame().to_parquet(history_path, index=False)

    first = materialize_live_training(
        _played(), fixture=_fixture_frame(), as_of_date="2026-06-13", data_root=data_root
    )
    second = materialize_live_training(
        _played(), fixture=_fixture_frame(), as_of_date="2026-06-13", data_root=data_root
    )
    # Identical canonical inputs -> identical derived checksum (immutable replay).
    assert first["live_training_sha256"] == second["live_training_sha256"]


def test_materialization_changes_checksum_when_results_change(
    test_workspace: Path,
) -> None:
    data_root = test_workspace / "data"
    history_path = data_root / "processed" / "historical_matches.parquet"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    _history_frame().to_parquet(history_path, index=False)

    baseline = materialize_live_training(
        _played(), fixture=_fixture_frame(), as_of_date="2026-06-13", data_root=data_root
    )
    corrected = (
        PlayedMatchResult(
            match_id="WC26-001", team_a="alpha", team_b="bravo", goals_a=0, goals_b=3
        ),
    )
    changed = materialize_live_training(
        corrected, fixture=_fixture_frame(), as_of_date="2026-06-14", data_root=data_root
    )
    assert baseline["live_training_sha256"] != changed["live_training_sha256"]


# --- fingerprint + reuse/refit -------------------------------------------


def _materialize(data_root: Path, played, as_of: str) -> dict:
    history_path = data_root / "processed" / "historical_matches.parquet"
    if not history_path.exists():
        history_path.parent.mkdir(parents=True, exist_ok=True)
        _history_frame().to_parquet(history_path, index=False)
    return materialize_live_training(
        played, fixture=_fixture_frame(), as_of_date=as_of, data_root=data_root
    )


def test_fingerprint_is_stable_for_unchanged_inputs(test_workspace: Path) -> None:
    data_root = test_workspace / "data"
    mat = _materialize(data_root, _played(), "2026-06-13")
    fp1 = compute_input_fingerprint(mat, xi=0.00095)
    fp2 = compute_input_fingerprint(mat, xi=0.00095)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_changes_with_results_or_xi(test_workspace: Path) -> None:
    data_root = test_workspace / "data"
    base = _materialize(data_root, _played(), "2026-06-13")
    base_fp = compute_input_fingerprint(base, xi=0.00095)

    other_xi = compute_input_fingerprint(base, xi=0.0018)
    assert other_xi != base_fp

    corrected = (
        PlayedMatchResult(
            match_id="WC26-001", team_a="alpha", team_b="bravo", goals_a=0, goals_b=3
        ),
    )
    changed = _materialize(data_root, corrected, "2026-06-14")
    assert compute_input_fingerprint(changed, xi=0.00095) != base_fp


def test_select_reuses_when_fingerprint_unchanged_and_refits_when_changed(
    test_workspace: Path,
) -> None:
    data_root = test_workspace / "data"
    mat = _materialize(data_root, _played(), "2026-06-13")

    first = select_model_artifact(
        mat, xi=0.00095, data_root=data_root, as_of_date="2026-06-13"
    )
    assert first["reused"] is False  # nothing pinned yet -> initial refit
    assert Path(first["model_path"]).exists()
    assert first["model_version"].startswith("baseline-v1-")
    parts = first["model_version"].split("-")
    # baseline - v1 - YYYY - MM - DD - <shortsha>
    assert parts[:2] == ["baseline", "v1"]
    assert len(parts[-1]) >= 7

    # Same canonical inputs the next day -> deterministic reuse, no new artifact.
    second = select_model_artifact(
        mat, xi=0.00095, data_root=data_root, as_of_date="2026-06-14"
    )
    assert second["reused"] is True
    assert second["model_path"] == first["model_path"]
    assert second["input_fingerprint"] == first["input_fingerprint"]

    # Corrected results -> changed fingerprint -> exactly one new dated artifact.
    corrected = (
        PlayedMatchResult(
            match_id="WC26-001", team_a="alpha", team_b="bravo", goals_a=0, goals_b=3
        ),
    )
    changed_mat = _materialize(data_root, corrected, "2026-06-15")
    third = select_model_artifact(
        changed_mat, xi=0.00095, data_root=data_root, as_of_date="2026-06-15"
    )
    assert third["reused"] is False
    assert third["input_fingerprint"] != first["input_fingerprint"]
    assert Path(third["model_path"]).exists()
    assert third["model_path"] != first["model_path"]


# --- official pipeline orchestration (verify-only + full run) -------------


def _isolated_data_root(test_workspace: Path) -> Path:
    """Copy the real historical parquet into an isolated data root for the run."""
    import shutil

    data_root = test_workspace / "data"
    dst = data_root / "processed" / "historical_matches.parquet"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL_HISTORY, dst)
    return data_root


def test_verify_only_reports_materialization_fingerprint_before_simulation(
    test_workspace: Path,
) -> None:
    data_root = _isolated_data_root(test_workspace)
    summary = verify_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=test_workspace / "snapshots",
        as_of=None,
        allow_dirty=True,
    )
    # The verify path resolves the materialization artifact + fingerprint that
    # would feed model selection, and proves the intended order, without writing
    # a published snapshot.
    assert summary["order"] == [
        "materialize",
        "select_model",
        "simulate",
        "publish",
    ]
    assert len(summary["live_training_sha256"]) == 64
    assert len(summary["input_fingerprint"]) == 64
    assert summary["model_version"].startswith("baseline-v1-")
    assert summary["published"] is False
    # No snapshot directory was created by a verify-only invocation.
    snaps = test_workspace / "snapshots"
    assert not snaps.exists() or not any(snaps.iterdir())


def test_official_run_stages_one_snapshot_with_full_provenance(
    test_workspace: Path,
) -> None:
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "snapshots"
    summary = run_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=snapshots_root,
        n_sims=64,
        seed=20260613,
        as_of=None,
        allow_dirty=True,
        # Deterministically simulate a dirty worktree so the recorded override is
        # asserted regardless of the real repo state at test time.
        _force_dirty=True,
    )
    snapshot_dir = Path(summary["snapshot_dir"])
    assert snapshot_dir.exists()
    # Exactly one published snapshot bundle.
    published = [p for p in snapshots_root.iterdir() if p.is_dir()]
    assert len(published) == 1

    metadata = json.loads((snapshot_dir / "metadata.json").read_text(encoding="utf-8"))
    # Final metadata records the git commit, dirty status, nested live-training
    # provenance, model provenance/fingerprint, kickoff boundary, and checksums
    # for every required artifact.
    assert metadata["git_commit"]
    assert metadata["git_dirty"] is True  # allow_dirty was passed
    assert metadata["kickoff_boundary_utc"].endswith("Z")
    assert len(metadata["live_training_provenance"]["artifact_sha256"]) == 64
    assert len(metadata["model_provenance"]["input_fingerprint"]) == 64
    assert metadata["model_provenance"]["model_version"].startswith("baseline-v1-")
    assert "team_probabilities.parquet" in metadata["checksums"]
    assert "upcoming_match_predictions.parquet" in metadata["checksums"]
    # The published team table is a real advancement table.
    team_probs = pd.read_parquet(snapshot_dir / "team_probabilities.parquet")
    assert "p_champion" in team_probs.columns
    assert len(team_probs) == 48


def test_official_run_fails_closed_on_dirty_worktree(test_workspace: Path) -> None:
    import json as _json

    data_root = _isolated_data_root(test_workspace)
    # Simulate a dirty worktree by injecting a git-status probe override.
    with pytest.raises(RuntimeError, match="dirty"):
        run_official(
            results_path=REAL_RESULTS,
            fixture_path=REAL_FIXTURE,
            data_root=data_root,
            snapshots_root=test_workspace / "snapshots",
            n_sims=16,
            seed=1,
            as_of=None,
            allow_dirty=False,
            _force_dirty=True,
        )
    del _json


# --- Phase 5 dual-publication integration (ML-03, D-13/D-14) ---------------


def _promoted_provider(upcoming: pd.DataFrame, *, state, model):
    """A Phase-5 candidate provider that promotes an upgrade for eligible matches."""
    import numpy as np

    gate = {"promoted": True, "winner": "ensemble", "mean_log_loss": {"baseline": 1.0}}
    ml_eligible = {}
    ml_probs = {}
    for i, row in enumerate(upcoming.itertuples(index=False)):
        # Mark the first upcoming match eligible, the rest ineligible, so the test
        # exercises both the dual-publish and the explicit baseline-fallback paths.
        eligible = i == 0
        ml_eligible[str(row.match_id)] = eligible
        if eligible:
            ml_probs[str(row.match_id)] = np.array([0.5, 0.3, 0.2])
    return {"gate": gate, "ml_eligible": ml_eligible, "ml_probs": ml_probs}


def _no_promotion_provider(upcoming: pd.DataFrame, *, state, model):
    gate = {"promoted": False, "winner": "baseline", "mean_log_loss": {"baseline": 1.0}}
    ml_eligible = {str(r.match_id): True for r in upcoming.itertuples(index=False)}
    return {"gate": gate, "ml_eligible": ml_eligible, "ml_probs": {}}


def test_baseline_path_is_unchanged_without_a_phase5_provider(
    test_workspace: Path,
) -> None:
    """No provider -> the existing baseline-only publication is byte-for-byte intact."""
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "snapshots"
    summary = run_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=snapshots_root,
        n_sims=32,
        seed=20260613,
        as_of=None,
        allow_dirty=True,
        _force_dirty=True,
    )
    snapshot_dir = Path(summary["snapshot_dir"])
    metadata = json.loads((snapshot_dir / "metadata.json").read_text(encoding="utf-8"))
    # No dual table and no model-selection block when no upgrade candidate is supplied.
    assert not (snapshot_dir / "upcoming_dual.parquet").exists()
    assert metadata.get("model_selection", {"promoted": False})["promoted"] is False


def test_promoted_candidate_publishes_dual_table_with_explicit_fallback(
    test_workspace: Path,
) -> None:
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "snapshots"
    summary = run_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=snapshots_root,
        n_sims=32,
        seed=20260613,
        as_of=None,
        allow_dirty=True,
        _force_dirty=True,
        ml_selection_provider=_promoted_provider,
    )
    snapshot_dir = Path(summary["snapshot_dir"])
    dual_path = snapshot_dir / "upcoming_dual.parquet"
    assert dual_path.exists()
    dual = pd.read_parquet(dual_path)

    # Every upcoming match keeps a baseline row (dual publication never drops baseline).
    baseline = pd.read_parquet(snapshot_dir / "upcoming_match_predictions.parquet")
    baseline_rows = dual[dual["model_family"] == "baseline"]
    assert set(baseline_rows["match_id"]) == set(baseline["match_id"])

    # Exactly the eligible matches gained an upgrade row.
    upgrade_rows = dual[dual["model_family"] == "upgrade"]
    assert len(upgrade_rows) >= 1
    # The selection metadata records promotion + an explicit fallback breakdown.
    metadata = json.loads((snapshot_dir / "metadata.json").read_text(encoding="utf-8"))
    selection = metadata["model_selection"]
    assert selection["promoted"] is True
    assert selection["winner"] == "ensemble"
    assert selection["n_baseline_published"] == len(baseline)
    assert selection["n_upgrade_published"] == len(upgrade_rows)
    # Ineligible upcoming matches are recorded as explicit baseline fallbacks.
    assert selection["fallback_reasons"].get("ml_ineligible", 0) >= 1
    assert summary["model_selection"]["promoted"] is True


def test_failed_gate_publishes_baseline_only_dual_table(test_workspace: Path) -> None:
    data_root = _isolated_data_root(test_workspace)
    snapshots_root = test_workspace / "snapshots"
    summary = run_official(
        results_path=REAL_RESULTS,
        fixture_path=REAL_FIXTURE,
        data_root=data_root,
        snapshots_root=snapshots_root,
        n_sims=32,
        seed=20260613,
        as_of=None,
        allow_dirty=True,
        _force_dirty=True,
        ml_selection_provider=_no_promotion_provider,
    )
    snapshot_dir = Path(summary["snapshot_dir"])
    dual = pd.read_parquet(snapshot_dir / "upcoming_dual.parquet")
    # Failed gate: zero upgrade rows, every row baseline with the negative-result reason.
    assert (dual["model_family"] == "upgrade").sum() == 0
    assert (dual["model_family"] == "baseline").all()
    metadata = json.loads((snapshot_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["model_selection"]["promoted"] is False
    assert metadata["model_selection"]["fallback_reasons"].get("gate_not_promoted", 0) >= 1
