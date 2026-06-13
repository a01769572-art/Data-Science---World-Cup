"""Live calibration tracker and frozen market benchmark (LIVE-04, DOC-02).

This module closes the live-evaluation layer with two coupled responsibilities,
both resolved during planning to avoid duplicating sources of truth:

1. **Freeze the market benchmark at publication time** (D-19/D-20/D-21,
   T-04-10). Given per-bookmaker de-margined three-way probabilities for the
   matches a snapshot is about to publish, aggregate the *valid bookmaker* rows
   into a canonical per-match probability triplet whose **primary** benchmark is
   the column-wise **median** (robust to a single mispriced book) and whose
   **auxiliary** diagnostic retains the simple **mean**. The frozen slice is
   stamped with the capture instant and registered into the staged snapshot so
   the evaluation path never reads "latest odds" after snapshot time.

2. **Maintain one canonical append-only per-match ledger** (D-18/D-22,
   T-04-11). A single top-level parquet
   (``data/processed/live/calibration/calibration_matches.parquet``) stores one
   row per (match, publication/snapshot) pair: frozen model probabilities,
   frozen market benchmark, the realized outcome when known, and everything
   needed to recompute cumulative metrics. Jornada / time-series views are
   *derived* aggregations over these base rows -- never a second mutable
   summary. During the same publication transaction the module also writes a
   snapshot-local ``report_inputs/calibration_publication_slice.parquet`` for
   report consumption and hands appended-row ids + slice checksums back to the
   snapshot finalizer.

Cumulative model-vs-market metrics reuse the Phase 2 helpers (``rps`` /
``brier_multiclass`` from :mod:`cdd_mundial.models.metrics` and scikit-learn
``log_loss`` exactly as :mod:`cdd_mundial.models.validation` uses it) so live
evaluation stays numerically consistent with phase-2 validation (T-04-12).
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from cdd_mundial.data.provenance import file_sha256
from cdd_mundial.models.metrics import brier_multiclass, rps

# Top-level canonical source of truth for live calibration (research resolution).
CANONICAL_LEDGER_PATH = Path("data/processed/live/calibration/calibration_matches.parquet")

FROZEN_BENCHMARK_NAME = "frozen_benchmark.parquet"
PUBLICATION_SLICE_NAME = "report_inputs/calibration_publication_slice.parquet"

_FROZEN_QUOTE_COLUMNS = ("prob_home", "prob_draw", "prob_away")
_LEDGER_KEY = ("match_id", "snapshot_id")


# --------------------------------------------------------------------------- #
# Shared helpers                                                               #
# --------------------------------------------------------------------------- #


def _format_utc(moment: datetime) -> str:
    """Render a timezone-aware datetime as an ISO-8601 ``...Z`` string."""
    if moment.tzinfo is None:
        raise ValueError("captured_at_utc must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize(triplet: np.ndarray) -> np.ndarray:
    """Renormalize a non-negative probability triplet to sum exactly to one."""
    total = float(triplet.sum())
    if total <= 0.0:
        raise ValueError(f"cannot normalize a non-positive probability vector: {triplet!r}")
    return triplet / total


def _row_id(*parts: Any) -> str:
    """Deterministic SHA-256 row identifier over canonical JSON of ``parts``."""
    payload = json.dumps(list(parts), sort_keys=True, ensure_ascii=True, default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _stage_nested_parquet(writer, relative_name: str, frame: pd.DataFrame) -> Path:
    """Stage a parquet under a possibly-nested path inside the snapshot staging dir.

    ``SnapshotWriter.add_table`` only handles flat names; calibration needs a
    ``report_inputs/`` subdirectory, so we write into the staging dir directly
    and register the nested filename for one-shot checksum finalization.
    """
    writer._guard_open()  # noqa: SLF001 - intentional staging extension point
    path = writer.staging_dir / relative_name
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    writer._register(relative_name, path)  # noqa: SLF001
    return path


# --------------------------------------------------------------------------- #
# Task 1: freeze the market benchmark                                         #
# --------------------------------------------------------------------------- #


def freeze_market_benchmark(
    quotes: pd.DataFrame,
    *,
    captured_at_utc: datetime,
) -> pd.DataFrame:
    """Aggregate valid per-bookmaker de-margined quotes into a frozen per-match slice.

    ``quotes`` carries one row per ``(match_id, bookmaker)`` with already
    de-margined ``prob_home``/``prob_draw``/``prob_away`` (the canonical
    benchmark probabilities produced by
    :func:`cdd_mundial.data.ingest_odds.build_odds_benchmark`). For each match
    the **primary** benchmark is the column-wise **median** across bookmakers,
    renormalized; the **mean** is carried as an auxiliary diagnostic. The
    capture instant is stamped on every row (D-21) so the slice is immune to
    later line movement.

    Returns a deterministically match-ordered frame whose primary columns
    satisfy ``FrozenBenchmarkSchema``.
    """
    required = {"match_id", "bookmaker", *_FROZEN_QUOTE_COLUMNS}
    missing = required - set(quotes.columns)
    if missing:
        raise ValueError(f"benchmark quotes are missing required columns: {sorted(missing)}")
    if quotes.empty:
        raise ValueError("refusing to freeze an empty market benchmark")

    captured = _format_utc(captured_at_utc)
    rows: list[dict[str, Any]] = []
    for match_id, group in quotes.groupby("match_id", sort=True):
        values = group[list(_FROZEN_QUOTE_COLUMNS)].to_numpy(dtype=float)
        median = _normalize(np.median(values, axis=0))
        mean = _normalize(np.mean(values, axis=0))
        rows.append(
            {
                "match_id": str(match_id),
                "captured_at_utc": captured,
                "prob_home": float(median[0]),
                "prob_draw": float(median[1]),
                "prob_away": float(median[2]),
                "prob_home_mean": float(mean[0]),
                "prob_draw_mean": float(mean[1]),
                "prob_away_mean": float(mean[2]),
                "n_bookmakers": int(len(group)),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "match_id",
            "captured_at_utc",
            "prob_home",
            "prob_draw",
            "prob_away",
            "prob_home_mean",
            "prob_draw_mean",
            "prob_away_mean",
            "n_bookmakers",
        ],
    ).reset_index(drop=True)


def benchmark_row_ids(frozen: pd.DataFrame) -> list[str]:
    """Deterministic per-row identifiers for a frozen benchmark slice."""
    return [
        _row_id(
            "frozen_benchmark",
            row["match_id"],
            row["captured_at_utc"],
            round(float(row["prob_home"]), 12),
            round(float(row["prob_draw"]), 12),
            round(float(row["prob_away"]), 12),
        )
        for _, row in frozen.iterrows()
    ]


def register_frozen_benchmark(writer, frozen: pd.DataFrame) -> dict[str, Any]:
    """Stage the frozen benchmark slice and return its filename, row ids, checksum.

    The returned reference lets the snapshot finalizer record the slice in
    ``metadata.json`` in one shot before publication (T-04-10).
    """
    path = writer.add_table("frozen_benchmark", frozen)
    return {
        "filename": FROZEN_BENCHMARK_NAME,
        "row_ids": benchmark_row_ids(frozen),
        "sha256": file_sha256(path),
    }


# --------------------------------------------------------------------------- #
# Task 2: append-only per-match calibration ledger                            #
# --------------------------------------------------------------------------- #


def derive_realized_outcomes(results: pd.DataFrame) -> dict[str, int]:
    """Map played results to ``outcome_idx`` (0=team_a win, 1=draw, 2=team_b win).

    Mirrors the project convention used by the Phase 2 metrics: the outcome is
    derived purely from 90-minute goals, consistent with the canonical results
    contract (``goals_a``/``goals_b``).
    """
    required = {"match_id", "goals_a", "goals_b"}
    missing = required - set(results.columns)
    if missing:
        raise ValueError(f"results are missing required columns: {sorted(missing)}")

    outcomes: dict[str, int] = {}
    for row in results.itertuples(index=False):
        goals_a = int(row.goals_a)
        goals_b = int(row.goals_b)
        if goals_a > goals_b:
            outcomes[str(row.match_id)] = 0
        elif goals_a == goals_b:
            outcomes[str(row.match_id)] = 1
        else:
            outcomes[str(row.match_id)] = 2
    return outcomes


def build_ledger_rows(
    *,
    predictions: pd.DataFrame,
    frozen_benchmark: pd.DataFrame,
    outcomes: dict[str, int],
    snapshot_id: str,
    model_version: str,
) -> pd.DataFrame:
    """Build one canonical ledger row per match for a single publication.

    Each row freezes the model 1/X/2 probabilities, the frozen market benchmark
    (``market_prob_*``), the realized ``outcome_idx`` when known (``<NA>``
    otherwise so unresolved matches stay derivable), and the publication keys
    ``snapshot_id`` / ``model_version``. No existing data is mutated -- callers
    append these rows to the canonical ledger.
    """
    pred_required = {"match_id", "team_a", "team_b", "prob_a", "prob_draw", "prob_b"}
    missing = pred_required - set(predictions.columns)
    if missing:
        raise ValueError(f"predictions are missing required columns: {sorted(missing)}")

    bench = frozen_benchmark.set_index("match_id")
    rows: list[dict[str, Any]] = []
    for pred in predictions.itertuples(index=False):
        match_id = str(pred.match_id)
        if match_id not in bench.index:
            raise ValueError(
                f"no frozen benchmark for predicted match {match_id!r}; benchmark must "
                "be frozen for every published prediction"
            )
        market = bench.loc[match_id]
        outcome = outcomes.get(match_id)
        rows.append(
            {
                "match_id": match_id,
                "snapshot_id": snapshot_id,
                "model_version": model_version,
                "team_a": str(pred.team_a),
                "team_b": str(pred.team_b),
                "prob_a": float(pred.prob_a),
                "prob_draw": float(pred.prob_draw),
                "prob_b": float(pred.prob_b),
                "market_prob_a": float(market["prob_home"]),
                "market_prob_draw": float(market["prob_draw"]),
                "market_prob_b": float(market["prob_away"]),
                "outcome_idx": pd.NA if outcome is None else int(outcome),
            }
        )

    frame = pd.DataFrame(
        rows,
        columns=[
            "match_id",
            "snapshot_id",
            "model_version",
            "team_a",
            "team_b",
            "prob_a",
            "prob_draw",
            "prob_b",
            "market_prob_a",
            "market_prob_draw",
            "market_prob_b",
            "outcome_idx",
        ],
    )
    # Nullable integer so unresolved matches carry <NA> rather than a float NaN.
    frame["outcome_idx"] = frame["outcome_idx"].astype("Int64")
    return frame.reset_index(drop=True)


def ledger_row_ids(rows: pd.DataFrame) -> list[str]:
    """Deterministic per-row identifiers keyed by the canonical ledger key."""
    return [
        _row_id("calibration_ledger", row["match_id"], row["snapshot_id"])
        for _, row in rows.iterrows()
    ]


def append_ledger(ledger_path: Path, rows: pd.DataFrame) -> list[str]:
    """Append new rows to the canonical append-only ledger and return their ids.

    Append-only discipline (D-18, T-04-11): existing rows are never rewritten,
    and re-appending a ``(match_id, snapshot_id)`` already present fails loud so
    the canonical history stays a single source of truth.
    """
    ledger_path = Path(ledger_path)
    new_keys = set(zip(rows["match_id"], rows["snapshot_id"], strict=True))
    if len(new_keys) != len(rows):
        raise ValueError("ledger rows contain duplicate (match_id, snapshot_id) keys")

    if ledger_path.exists():
        existing = pd.read_parquet(ledger_path)
        existing_keys = set(zip(existing["match_id"], existing["snapshot_id"], strict=True))
        clash = existing_keys & new_keys
        if clash:
            raise ValueError(
                f"refusing to mutate append-only ledger: rows already present for "
                f"{sorted(clash)}"
            )
        combined = pd.concat([existing, rows], ignore_index=True)
    else:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        combined = rows.reset_index(drop=True)

    combined.to_parquet(ledger_path, index=False)
    return ledger_row_ids(rows)


def cumulative_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    """Cumulative model-vs-market metrics over resolved rows of the ledger.

    Only rows with a realized ``outcome_idx`` contribute. Metrics reuse the
    Phase 2 helpers exactly (``rps``, ``brier_multiclass`` and scikit-learn
    ``log_loss`` with ``labels=[0, 1, 2]``) so live evaluation matches
    validation (T-04-12). Time-series / jornada views are derivable by the
    caller from the same base rows -- this is a pure aggregation, not a second
    stored dataset.
    """
    resolved = rows[rows["outcome_idx"].notna()].copy()
    n = int(len(resolved))
    if n == 0:
        return {"n_matches": 0, "model": None, "market": None}

    outcomes = resolved["outcome_idx"].to_numpy(dtype=int)
    model_probs = resolved[["prob_a", "prob_draw", "prob_b"]].to_numpy(dtype=float)
    market_probs = resolved[
        ["market_prob_a", "market_prob_draw", "market_prob_b"]
    ].to_numpy(dtype=float)

    def _block(probs: np.ndarray) -> dict[str, float]:
        return {
            "rps": float(rps(probs, outcomes)),
            "brier": float(brier_multiclass(probs, outcomes)),
            "log_loss": float(log_loss(outcomes, probs, labels=[0, 1, 2])),
        }

    return {
        "n_matches": n,
        "model": _block(model_probs),
        "market": _block(market_probs),
    }


def publish_calibration(
    writer,
    ledger_path: Path,
    rows: pd.DataFrame,
) -> dict[str, Any]:
    """Append rows to the canonical ledger and stage the report slice in one transaction.

    Returns a reference the snapshot finalizer can embed in ``metadata.json``:
    the appended ledger-row ids and the snapshot-local publication slice path,
    tracing the publication back to exact authoritative records (T-04-11).
    """
    appended_ids = append_ledger(ledger_path, rows)
    slice_path = _stage_nested_parquet(writer, PUBLICATION_SLICE_NAME, rows)
    return {
        "ledger_path": Path(ledger_path).as_posix(),
        "ledger_row_ids": appended_ids,
        "publication_slice": PUBLICATION_SLICE_NAME,
        "publication_slice_sha256": file_sha256(slice_path),
    }


__all__ = [
    "CANONICAL_LEDGER_PATH",
    "FROZEN_BENCHMARK_NAME",
    "PUBLICATION_SLICE_NAME",
    "append_ledger",
    "benchmark_row_ids",
    "build_ledger_rows",
    "cumulative_metrics",
    "derive_realized_outcomes",
    "freeze_market_benchmark",
    "ledger_row_ids",
    "publish_calibration",
    "register_frozen_benchmark",
]
