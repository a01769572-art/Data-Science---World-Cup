"""Tests for the live calibration tracker and frozen market benchmark (LIVE-04, DOC-02).

These tests freeze the resolved research design:

* the primary benchmark per match is the **median** de-margined probability
  triplet across valid bookmakers, with the simple **mean** retained only as an
  auxiliary diagnostic (D-19/D-20);
* the benchmark is frozen at publication time and never re-reads fresher odds
  (D-21, T-04-10);
* a single top-level append-only ledger holds one canonical row per
  match/publication pair, from which cumulative model-vs-market metrics and time
  series are derived (D-18/D-22, T-04-11);
* cumulative metrics reuse the Phase 2 helpers (`rps`, `brier_multiclass`,
  `log_loss`) so live-eval math matches validation (T-04-12).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cdd_mundial.live import calibration
from cdd_mundial.live.contracts import (
    CalibrationLedgerSchema,
    FrozenBenchmarkSchema,
)
from cdd_mundial.live.snapshots import SnapshotWriter


def _quote_row(match_id: str, ph: float, pdr: float, pa: float, bookmaker: str) -> dict:
    """A single de-margined bookmaker quote row (already normalized)."""
    return {
        "match_id": match_id,
        "bookmaker": bookmaker,
        "prob_home": ph,
        "prob_draw": pdr,
        "prob_away": pa,
    }


def _three_bookmaker_quotes() -> pd.DataFrame:
    # Median of [0.5, 0.6, 0.7] is 0.6; mean is 0.6 too only when symmetric, so
    # we choose asymmetric numbers below to keep median != mean.
    rows = [
        _quote_row("WC26-010", 0.50, 0.30, 0.20, "bookA"),
        _quote_row("WC26-010", 0.60, 0.25, 0.15, "bookB"),
        _quote_row("WC26-010", 0.90, 0.05, 0.05, "bookC"),
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Task 1: frozen market benchmark                                             #
# --------------------------------------------------------------------------- #


def test_benchmark_primary_is_median_not_mean() -> None:
    captured_at = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    frozen = calibration.freeze_market_benchmark(
        _three_bookmaker_quotes(), captured_at_utc=captured_at
    )

    assert len(frozen) == 1
    row = frozen.iloc[0]
    # Column-wise median across bookmakers, then renormalized.
    raw_med = np.array([0.60, 0.25, 0.15])
    expected = raw_med / raw_med.sum()
    assert row["prob_home"] == pytest.approx(expected[0])
    assert row["prob_draw"] == pytest.approx(expected[1])
    assert row["prob_away"] == pytest.approx(expected[2])
    # Median must differ from the mean here (mean home = 2.0/3 ≈ 0.667).
    assert row["prob_home"] != pytest.approx(2.0 / 3)


def test_benchmark_retains_mean_as_auxiliary_diagnostic() -> None:
    captured_at = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    frozen = calibration.freeze_market_benchmark(
        _three_bookmaker_quotes(), captured_at_utc=captured_at
    )
    row = frozen.iloc[0]
    raw_mean = np.array([(0.50 + 0.60 + 0.90) / 3, (0.30 + 0.25 + 0.05) / 3, (0.20 + 0.15 + 0.05) / 3])
    expected_mean = raw_mean / raw_mean.sum()
    assert row["prob_home_mean"] == pytest.approx(expected_mean[0])
    assert row["prob_draw_mean"] == pytest.approx(expected_mean[1])
    assert row["prob_away_mean"] == pytest.approx(expected_mean[2])
    assert int(row["n_bookmakers"]) == 3


def test_frozen_benchmark_passes_contract() -> None:
    captured_at = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    frozen = calibration.freeze_market_benchmark(
        _three_bookmaker_quotes(), captured_at_utc=captured_at
    )
    # Primary columns must satisfy the frozen contract.
    contract_slice = frozen[
        ["match_id", "captured_at_utc", "prob_home", "prob_draw", "prob_away"]
    ]
    FrozenBenchmarkSchema.validate(contract_slice)
    assert frozen.iloc[0]["captured_at_utc"].endswith("Z")


def test_benchmark_capture_time_is_recorded_and_stable(tmp_path: Path) -> None:
    captured_at = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    frozen = calibration.freeze_market_benchmark(
        _three_bookmaker_quotes(), captured_at_utc=captured_at
    )
    # The frozen slice carries the freeze instant and is independent of later input.
    assert (frozen["captured_at_utc"] == "2026-06-13T12:00:00Z").all()


def test_register_frozen_benchmark_returns_checksum_and_row_ids(tmp_path: Path) -> None:
    captured_at = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    frozen = calibration.freeze_market_benchmark(
        _three_bookmaker_quotes(), captured_at_utc=captured_at
    )
    writer = SnapshotWriter(snapshots_root=tmp_path, snapshot_id="snap-1")
    ref = calibration.register_frozen_benchmark(writer, frozen)

    assert ref["filename"] == "frozen_benchmark.parquet"
    assert isinstance(ref["row_ids"], list) and len(ref["row_ids"]) == 1
    # row_id is deterministic SHA-256 derived; same input → same id.
    again = calibration.freeze_market_benchmark(
        _three_bookmaker_quotes(), captured_at_utc=captured_at
    )
    assert calibration.benchmark_row_ids(again) == ref["row_ids"]
    # Checksum available for one-shot metadata finalization.
    writer.finalize_metadata({"order": []})
    writer.publish()
    assert (tmp_path / "snap-1" / "frozen_benchmark.parquet").exists()


# --------------------------------------------------------------------------- #
# Task 2: append-only per-match calibration ledger                            #
# --------------------------------------------------------------------------- #


def _model_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"match_id": "WC26-010", "team_a": "mexico", "team_b": "south-africa",
             "prob_a": 0.6, "prob_draw": 0.25, "prob_b": 0.15},
            {"match_id": "WC26-011", "team_a": "canada", "team_b": "bosnia-and-herzegovina",
             "prob_a": 0.5, "prob_draw": 0.3, "prob_b": 0.2},
        ]
    )


def _frozen_benchmark_for_ledger() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"match_id": "WC26-010", "captured_at_utc": "2026-06-13T12:00:00Z",
             "prob_home": 0.55, "prob_draw": 0.28, "prob_away": 0.17},
            {"match_id": "WC26-011", "captured_at_utc": "2026-06-13T12:00:00Z",
             "prob_home": 0.48, "prob_draw": 0.32, "prob_away": 0.20},
        ]
    )


def _results() -> pd.DataFrame:
    # WC26-010: team_a wins (2-1) → outcome 0; WC26-011: draw (1-1) → outcome 1.
    return pd.DataFrame(
        [
            {"match_id": "WC26-010", "goals_a": 2, "goals_b": 1},
            {"match_id": "WC26-011", "goals_a": 1, "goals_b": 1},
        ]
    )


def test_derive_realized_outcomes_from_goals() -> None:
    outcomes = calibration.derive_realized_outcomes(_results())
    assert outcomes == {"WC26-010": 0, "WC26-011": 1}


def test_build_ledger_rows_one_canonical_row_per_match() -> None:
    rows = calibration.build_ledger_rows(
        predictions=_model_predictions(),
        frozen_benchmark=_frozen_benchmark_for_ledger(),
        outcomes=calibration.derive_realized_outcomes(_results()),
        snapshot_id="snap-1",
        model_version="baseline-v1-2026-06-13-abc1234",
    )
    assert len(rows) == 2
    assert list(rows["match_id"]) == ["WC26-010", "WC26-011"]
    # Model probabilities are frozen into the ledger.
    CalibrationLedgerSchema.validate(
        rows[["match_id", "snapshot_id", "model_version",
              "prob_a", "prob_draw", "prob_b", "outcome_idx"]]
    )
    # Market benchmark is carried for model-vs-market comparison.
    assert "market_prob_a" in rows.columns
    assert rows.iloc[0]["outcome_idx"] == 0


def test_append_ledger_is_append_only(tmp_path: Path) -> None:
    ledger_path = tmp_path / "calibration_matches.parquet"
    rows1 = calibration.build_ledger_rows(
        predictions=_model_predictions().iloc[[0]],
        frozen_benchmark=_frozen_benchmark_for_ledger().iloc[[0]],
        outcomes={"WC26-010": 0},
        snapshot_id="snap-1",
        model_version="baseline-v1-2026-06-13-abc1234",
    )
    calibration.append_ledger(ledger_path, rows1)
    first = pd.read_parquet(ledger_path)

    rows2 = calibration.build_ledger_rows(
        predictions=_model_predictions().iloc[[1]],
        frozen_benchmark=_frozen_benchmark_for_ledger().iloc[[1]],
        outcomes={"WC26-011": 1},
        snapshot_id="snap-2",
        model_version="baseline-v1-2026-06-14-def5678",
    )
    appended_ids = calibration.append_ledger(ledger_path, rows2)
    full = pd.read_parquet(ledger_path)

    # Existing rows are untouched; only new rows appended.
    assert len(full) == len(first) + 1
    pd.testing.assert_frame_equal(full.iloc[: len(first)].reset_index(drop=True), first)
    assert appended_ids == calibration.ledger_row_ids(rows2)


def test_append_ledger_rejects_duplicate_match_snapshot(tmp_path: Path) -> None:
    ledger_path = tmp_path / "calibration_matches.parquet"
    rows = calibration.build_ledger_rows(
        predictions=_model_predictions().iloc[[0]],
        frozen_benchmark=_frozen_benchmark_for_ledger().iloc[[0]],
        outcomes={"WC26-010": 0},
        snapshot_id="snap-1",
        model_version="baseline-v1-2026-06-13-abc1234",
    )
    calibration.append_ledger(ledger_path, rows)
    with pytest.raises(ValueError):
        calibration.append_ledger(ledger_path, rows)


def test_cumulative_metrics_match_phase2_helpers() -> None:
    from sklearn.metrics import log_loss

    from cdd_mundial.models.metrics import brier_multiclass, rps

    rows = calibration.build_ledger_rows(
        predictions=_model_predictions(),
        frozen_benchmark=_frozen_benchmark_for_ledger(),
        outcomes=calibration.derive_realized_outcomes(_results()),
        snapshot_id="snap-1",
        model_version="baseline-v1-2026-06-13-abc1234",
    )
    metrics = calibration.cumulative_metrics(rows)

    probs = rows[["prob_a", "prob_draw", "prob_b"]].to_numpy(dtype=float)
    market = rows[["market_prob_a", "market_prob_draw", "market_prob_b"]].to_numpy(dtype=float)
    outcomes = rows["outcome_idx"].to_numpy(dtype=int)

    assert metrics["model"]["rps"] == pytest.approx(rps(probs, outcomes))
    assert metrics["model"]["brier"] == pytest.approx(brier_multiclass(probs, outcomes))
    assert metrics["model"]["log_loss"] == pytest.approx(
        log_loss(outcomes, probs, labels=[0, 1, 2])
    )
    assert metrics["market"]["rps"] == pytest.approx(rps(market, outcomes))
    assert metrics["n_matches"] == 2


def test_cumulative_metrics_ignore_unresolved_matches() -> None:
    # A row with no realized outcome (outcome_idx is NA) must be excluded.
    rows = calibration.build_ledger_rows(
        predictions=_model_predictions(),
        frozen_benchmark=_frozen_benchmark_for_ledger(),
        outcomes={"WC26-010": 0},  # WC26-011 unresolved
        snapshot_id="snap-1",
        model_version="baseline-v1-2026-06-13-abc1234",
    )
    metrics = calibration.cumulative_metrics(rows)
    assert metrics["n_matches"] == 1


def test_publication_slice_written_and_referenced(tmp_path: Path) -> None:
    ledger_path = tmp_path / "calibration_matches.parquet"
    writer = SnapshotWriter(snapshots_root=tmp_path, snapshot_id="snap-1")
    rows = calibration.build_ledger_rows(
        predictions=_model_predictions(),
        frozen_benchmark=_frozen_benchmark_for_ledger(),
        outcomes=calibration.derive_realized_outcomes(_results()),
        snapshot_id="snap-1",
        model_version="baseline-v1-2026-06-13-abc1234",
    )
    ref = calibration.publish_calibration(writer, ledger_path, rows)

    assert ref["ledger_row_ids"] == calibration.ledger_row_ids(rows)
    assert ref["publication_slice"] == "report_inputs/calibration_publication_slice.parquet"
    writer.finalize_metadata({"order": []})
    published = writer.publish()
    slice_path = published / "report_inputs" / "calibration_publication_slice.parquet"
    assert slice_path.exists()
    # Top-level append-only ledger received the rows too.
    assert len(pd.read_parquet(ledger_path)) == 2
