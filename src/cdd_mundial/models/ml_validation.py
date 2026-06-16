"""ML-only temporal validation harness for the upgrade candidate (Phase 5, ML-02).

This mirrors the Phase-2 baseline harness (:mod:`cdd_mundial.models.validation`)
verbatim where it matters and changes only what the ML candidate genuinely needs:

* the **same four holdouts** (``HOLDOUTS``) and the **same metric family**
  (``log_loss`` / ``brier`` / ``rps``) imported from the baseline module — so later
  candidate comparisons are legitimate rather than apples-to-oranges (T-05-04);
* **fit-at-cutoff** semantics: for each holdout the model is trained strictly on rows
  with ``date < cutoff`` and scored on that holdout's matches only;
* **D-04 exclusion is hard, not advisory** (T-05-06): ineligible rows
  (``ml_eligible == False``) never enter either the training fit or the scoring set;
  the report records how many were excluded per holdout so the omission is auditable;
* **dated, reviewable artifacts** parallel to the baseline: a report JSON plus a
  holdout prediction table, written under ``data/processed/models``.

The harness consumes a pre-built ML-feature dataset (the canonical output of
:func:`cdd_mundial.models.ml_features.build_ml_dataset`) so backtests and the live
path share one feature surface. It deliberately does **not** do calibration or the
promotion gate — those are Plan 03. Here the only question is whether a conservative
ML candidate can be trained and scored under the same temporal discipline as the
baseline.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from cdd_mundial.models.metrics import brier_multiclass, rps
from cdd_mundial.models.ml_features import (
    ML_FEATURE_COLUMNS,
    MIN_PRIOR_MATCHES,
    build_ml_dataset,
)
from cdd_mundial.models.ml_xgboost import DEFAULT_SEED, MulticlassXGBoost

# Reuse the baseline's holdout calendar verbatim (T-05-04): identical tournaments,
# cutoffs, years, and expected counts. No parallel definition is allowed to drift.
from cdd_mundial.models.validation import HOLDOUTS, Holdout

_FEATURES = tuple(ML_FEATURE_COLUMNS)


def _artifact_date() -> str:
    return date.today().isoformat()


def _eligible(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep only ML-eligible rows (D-04). Ineligible rows fall back to baseline."""
    return frame.loc[frame["ml_eligible"].astype(bool)].copy()


def _select_ml_holdout(dataset: pd.DataFrame, holdout: Holdout) -> pd.DataFrame:
    """Select a holdout by exact tournament string and year, sorted deterministically.

    Unlike the baseline ``select_holdout`` this does not assert the full official
    match count: the ML dataset legitimately drops ineligible rows downstream, so the
    eligible-row count per holdout is data-dependent and is reported, not enforced.
    """
    selected = dataset[
        (dataset["tournament"] == holdout.tournament)
        & (dataset["date"].dt.year == holdout.year)
    ].copy()
    return selected.sort_values(["date", "match_id"]).reset_index(drop=True)


def _metrics(probs: np.ndarray, outcome_idx: np.ndarray) -> dict[str, float]:
    return {
        "log_loss": float(log_loss(outcome_idx, probs, labels=[0, 1, 2])),
        "brier": float(brier_multiclass(probs, outcome_idx)),
        "rps": float(rps(probs, outcome_idx)),
    }


def _coerce_dataset(
    dataset: pd.DataFrame | None,
    *,
    data_root: Path,
) -> pd.DataFrame:
    """Return a ready ML-feature dataset, building it from the canonical parquet if needed."""
    if dataset is not None:
        frame = dataset.copy()
    else:
        frame = build_ml_dataset(
            path=data_root / "processed" / "historical_matches.parquet"
        )
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    missing = set(_FEATURES) | {"ml_eligible", "target_outcome_idx", "match_id"}
    absent = missing - set(frame.columns)
    if absent:
        raise ValueError(f"ml dataset is missing required columns: {sorted(absent)}")
    return frame


def run_ml_validation(
    dataset: pd.DataFrame | None = None,
    *,
    data_root: Path = Path("data"),
    seed: int = DEFAULT_SEED,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Score the conservative ML candidate across the four holdouts under fit-at-cutoff.

    Parameters
    ----------
    dataset
        A pre-built ML-feature frame (output of ``build_ml_dataset``). When ``None``
        the canonical historical parquet under ``data_root`` is built on the fly.
    data_root
        Used only when ``dataset`` is ``None``.
    seed
        Seed forwarded to every per-fold :class:`MulticlassXGBoost` for reproducibility.

    Returns
    -------
    (report, predictions)
        ``report`` carries per-holdout metrics, cutoff, train/exclusion counts, and the
        feature contract; ``predictions`` is one row per scored holdout match.
    """
    frame = _coerce_dataset(dataset, data_root=data_root)

    per_holdout_report: dict[str, Any] = {}
    prediction_rows: list[dict[str, Any]] = []
    log_losses: list[float] = []

    for holdout_name, holdout in HOLDOUTS.items():
        cutoff = pd.Timestamp(holdout.start)

        # --- fit strictly before the cutoff, eligible rows only (T-05-04/T-05-06) ---
        train_all = frame[frame["date"] < cutoff]
        train = _eligible(train_all)
        n_train_excluded = int(len(train_all) - len(train))

        holdout_all = _select_ml_holdout(frame, holdout)
        holdout_eligible = _eligible(holdout_all)
        n_holdout_excluded = int(len(holdout_all) - len(holdout_eligible))

        if train.empty or holdout_eligible.empty:
            raise ValueError(
                f"holdout {holdout_name}: no eligible {'training' if train.empty else 'scoring'} "
                "rows remain after the D-04 filter"
            )

        x_train = train[list(_FEATURES)].to_numpy(dtype=float)
        y_train = train["target_outcome_idx"].to_numpy(dtype=int)
        model = MulticlassXGBoost(seed=seed).fit(x_train, y_train)

        x_holdout = holdout_eligible[list(_FEATURES)].to_numpy(dtype=float)
        probs = model.predict_proba(x_holdout)
        outcome_idx = holdout_eligible["target_outcome_idx"].to_numpy(dtype=int)

        per_holdout_report[holdout_name] = {
            "cutoff": holdout.start,
            "tournament": holdout.tournament,
            "n_train": int(len(train)),
            "n_train_excluded": n_train_excluded,
            "n_scored": int(len(holdout_eligible)),
            "n_excluded": n_holdout_excluded,
            "train_max_date": str(train["date"].max().date()),
            "metrics": _metrics(probs, outcome_idx),
        }
        log_losses.append(per_holdout_report[holdout_name]["metrics"]["log_loss"])

        for match_id, outcome, prob in zip(
            holdout_eligible["match_id"].tolist(), outcome_idx, probs, strict=True
        ):
            prediction_rows.append(
                {
                    "match_id": str(match_id),
                    "holdout": holdout_name,
                    "model": "ml_xgboost",
                    "p_home_win": float(prob[0]),
                    "p_draw": float(prob[1]),
                    "p_away_win": float(prob[2]),
                    "outcome_idx": int(outcome),
                }
            )

    report = {
        "candidate": "ml_xgboost",
        "seed": int(seed),
        "feature_columns": list(_FEATURES),
        "min_prior_matches": int(MIN_PRIOR_MATCHES),
        "mean_log_loss": float(np.mean(log_losses)),
        "per_holdout": per_holdout_report,
    }
    return report, pd.DataFrame(prediction_rows)


def materialize_ml_validation(
    dataset: pd.DataFrame | None = None,
    *,
    data_root: Path = Path("data"),
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Persist the ML validation report + holdout predictions as dated artifacts."""
    report, predictions = run_ml_validation(dataset, data_root=data_root, seed=seed)
    artifact_date = _artifact_date()
    models_root = data_root / "processed" / "models"
    models_root.mkdir(parents=True, exist_ok=True)

    report_path = models_root / f"ml_validation_report_{artifact_date}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    predictions_path = models_root / f"ml_holdout_predictions_{artifact_date}.parquet"
    predictions.to_parquet(predictions_path, index=False)

    return {
        "candidate": report["candidate"],
        "mean_log_loss": report["mean_log_loss"],
        "per_holdout": report["per_holdout"],
        "prediction_rows": int(len(predictions)),
        "report_path": report_path.as_posix(),
        "predictions_path": predictions_path.as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ML-only temporal validation harness over the four holdouts."
    )
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    args = parser.parse_args()
    summary = materialize_ml_validation(data_root=args.data_root)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
