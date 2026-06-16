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
from cdd_mundial.models.ml_calibration import (
    CALIBRATION_METHODS,
    MulticlassCalibrator,
    select_best_calibration,
)
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

# The point-in-time Dixon-Coles WDL columns inside the ML dataset (D-02). They double
# as the *baseline candidate's* per-match probabilities so the comparison reuses one
# point-in-time feature surface instead of re-running the production DC model here.
_DC_PROB_COLUMNS = ("p_home_win_dc", "p_draw_dc", "p_away_win_dc")

# Convex ensemble weight grid over probability vectors (research §6): a small, auditable
# grid chosen inside temporal validation only. ``w`` is the weight on the ML candidate.
ENSEMBLE_WEIGHT_GRID: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Fraction of the pre-cutoff eligible rows (latest by date) reserved as the inner
# calibration/selection slice. The earlier rows fit the model; this latest slice
# selects calibrators and the ensemble weight WITHOUT seeing the scored holdout
# (T-05-07). Kept as a fraction so small synthetic frames and the real dataset both
# leave a usable selection slice.
_INNER_CAL_FRACTION = 0.25


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


# --------------------------------------------------------------------------- #
# Plan 03: calibrated baseline-vs-ML-vs-ensemble comparison + promotion gate    #
# --------------------------------------------------------------------------- #


def evaluate_ml_gate(
    baseline_log_loss: dict[str, float],
    ml_log_loss: dict[str, float],
    ensemble_log_loss: dict[str, float],
) -> dict[str, Any]:
    """Pure 4-holdout promotion gate (T-05-08).

    A candidate is promoted **only** if it beats the baseline in log-loss on *every*
    holdout (strictly lower, never equal). If both ML and ensemble clear the gate, the
    one with the lower mean log-loss is promoted; ties break toward ``ml`` for a simpler
    model. If neither clears the gate, the baseline stays live and that negative result
    is recorded as a first-class outcome (T-05-09), never an implicit absence.

    Parameters are per-holdout ``{holdout_name: log_loss}`` maps that must share keys.
    """
    holdouts = set(baseline_log_loss)
    if not (holdouts == set(ml_log_loss) == set(ensemble_log_loss)):
        raise ValueError("baseline/ml/ensemble log-loss maps must cover the same holdouts")
    if not holdouts:
        raise ValueError("the gate requires at least one holdout")

    candidates = {"ml": ml_log_loss, "ensemble": ensemble_log_loss}
    beats_all: dict[str, bool] = {
        name: all(scores[h] < baseline_log_loss[h] for h in holdouts)
        for name, scores in candidates.items()
    }
    mean_log_loss = {
        "baseline": float(np.mean(list(baseline_log_loss.values()))),
        "ml": float(np.mean(list(ml_log_loss.values()))),
        "ensemble": float(np.mean(list(ensemble_log_loss.values()))),
    }

    qualified = [name for name, ok in beats_all.items() if ok]
    if qualified:
        # Lowest mean log-loss wins; tie -> 'ml' (simpler) by stable ordering.
        winner = min(qualified, key=lambda n: (mean_log_loss[n], 0 if n == "ml" else 1))
        promoted = True
    else:
        winner = "baseline"
        promoted = False

    return {
        "promoted": promoted,
        "winner": winner,
        "criterion": "strictly lower log-loss than baseline on all four holdouts",
        "beats_baseline_all_holdouts": beats_all,
        "mean_log_loss": mean_log_loss,
    }


def _ensemble_probs(ml_probs: np.ndarray, baseline_probs: np.ndarray, weight: float) -> np.ndarray:
    """Convex blend ``w * ml + (1 - w) * baseline`` renormalized defensively."""
    blended = weight * ml_probs + (1.0 - weight) * baseline_probs
    return blended / blended.sum(axis=1, keepdims=True)


def _split_inner(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split pre-cutoff eligible rows into (inner_fit, inner_cal) by date.

    The latest ``_INNER_CAL_FRACTION`` of rows (by date, then match_id) become the
    calibration/selection slice; everything earlier fits the model. Both are strictly
    pre-cutoff, so neither sees the scored holdout (T-05-07).
    """
    ordered = train.sort_values(["date", "match_id"]).reset_index(drop=True)
    n = len(ordered)
    n_cal = max(1, int(round(n * _INNER_CAL_FRACTION)))
    n_cal = min(n_cal, n - 1)  # always leave at least one fitting row
    inner_fit = ordered.iloc[: n - n_cal].copy()
    inner_cal = ordered.iloc[n - n_cal :].copy()
    return inner_fit, inner_cal


def _select_weight(
    ml_cal: np.ndarray, baseline_cal: np.ndarray, y_cal: np.ndarray
) -> float:
    """Choose the convex ensemble weight by log-loss on the inner calibration slice."""
    best_w = 0.0
    best_score = None
    for w in ENSEMBLE_WEIGHT_GRID:
        probs = _ensemble_probs(ml_cal, baseline_cal, w)
        score = float(log_loss(y_cal, probs, labels=[0, 1, 2]))
        if best_score is None or score < best_score:
            best_score = score
            best_w = float(w)
    return best_w


def run_ml_comparison(
    dataset: pd.DataFrame | None = None,
    *,
    data_root: Path = Path("data"),
    seed: int = DEFAULT_SEED,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Score baseline, ML-solo, and ensemble candidates per holdout and apply the gate.

    For each holdout the pre-cutoff eligible rows are split into an inner fit slice and
    a latest inner calibration slice (both strictly pre-cutoff). Calibrators (sigmoid /
    isotonic / none) for the ML candidate and for the ensemble are selected empirically
    on the calibration slice, and the convex ensemble weight is chosen there too — never
    on the scored holdout (D-11/D-12, T-05-07). The SAME model that produced the raw
    probabilities those calibrators/weight were fit on is also the model that scores the
    holdout (CR-01 train/serve identity, T-05-13): the calibrators learned per-class maps
    for *this* model's output distribution, so applying them to a different, re-fit
    model's probabilities would feed the gate a miscalibrated distribution. We therefore
    score the holdout with the inner model rather than re-fitting on all pre-cutoff rows.

    The baseline candidate uses the point-in-time Dixon-Coles WDL columns already present
    in the ML dataset (D-02), so all three candidates share one feature surface and one
    holdout calendar (T-05-04). The four-holdout promotion gate (``evaluate_ml_gate``)
    decides the winner; a negative result keeps the baseline live explicitly (T-05-09).
    """
    frame = _coerce_dataset(dataset, data_root=data_root)
    absent = set(_DC_PROB_COLUMNS) - set(frame.columns)
    if absent:
        raise ValueError(f"ml dataset is missing baseline DC probability columns: {sorted(absent)}")

    per_holdout_report: dict[str, Any] = {}
    prediction_rows: list[dict[str, Any]] = []
    log_loss_by_candidate: dict[str, dict[str, float]] = {
        "baseline": {},
        "ml": {},
        "ensemble": {},
    }

    for holdout_name, holdout in HOLDOUTS.items():
        cutoff = pd.Timestamp(holdout.start)
        train = _eligible(frame[frame["date"] < cutoff])
        holdout_eligible = _eligible(_select_ml_holdout(frame, holdout))
        n_holdout_excluded = int(
            len(_select_ml_holdout(frame, holdout)) - len(holdout_eligible)
        )
        if train.empty or holdout_eligible.empty:
            raise ValueError(
                f"holdout {holdout_name}: no eligible "
                f"{'training' if train.empty else 'scoring'} rows after the D-04 filter"
            )

        inner_fit, inner_cal = _split_inner(train)

        # --- 1) fit the model on the inner fit slice and predict the cal slice ---
        x_fit = inner_fit[list(_FEATURES)].to_numpy(dtype=float)
        y_fit = inner_fit["target_outcome_idx"].to_numpy(dtype=int)
        inner_model = MulticlassXGBoost(seed=seed).fit(x_fit, y_fit)

        x_cal = inner_cal[list(_FEATURES)].to_numpy(dtype=float)
        y_cal = inner_cal["target_outcome_idx"].to_numpy(dtype=int)
        ml_cal_raw = inner_model.predict_proba(x_cal)
        baseline_cal = inner_cal[list(_DC_PROB_COLUMNS)].to_numpy(dtype=float)
        baseline_cal = baseline_cal / baseline_cal.sum(axis=1, keepdims=True)

        # --- 2) select ML calibrator on the cal slice (fit on inner_fit predictions) ---
        ml_fit_raw = inner_model.predict_proba(x_fit)
        ml_choice = select_best_calibration(ml_fit_raw, y_fit, ml_cal_raw, y_cal)
        ml_calibrator = MulticlassCalibrator(method=ml_choice["method"]).fit(ml_fit_raw, y_fit)
        ml_cal_calibrated = ml_calibrator.transform(ml_cal_raw)

        # --- 3) select ensemble weight, then its calibrator, both on the cal slice ---
        weight = _select_weight(ml_cal_calibrated, baseline_cal, y_cal)
        ens_fit_raw = _ensemble_probs(
            ml_calibrator.transform(ml_fit_raw),
            (inner_fit[list(_DC_PROB_COLUMNS)].to_numpy(dtype=float)
             / inner_fit[list(_DC_PROB_COLUMNS)].to_numpy(dtype=float).sum(axis=1, keepdims=True)),
            weight,
        )
        ens_cal_raw = _ensemble_probs(ml_cal_calibrated, baseline_cal, weight)
        ens_choice = select_best_calibration(ens_fit_raw, y_fit, ens_cal_raw, y_cal)
        ens_calibrator = MulticlassCalibrator(method=ens_choice["method"]).fit(ens_fit_raw, y_fit)

        calibration_max_date = str(inner_cal["date"].max().date())

        # --- 4) score the holdout with the SAME model the calibrators/weight were fit
        #        on (CR-01 train/serve identity, T-05-13). ``inner_model`` produced the
        #        ml_fit_raw/ml_cal_raw probabilities used to select and fit
        #        ml_calibrator/ens_calibrator and the ensemble weight; the per-class
        #        isotonic/sigmoid maps are only valid for *its* output distribution.
        #        Re-fitting a separate final model on all pre-cutoff rows and applying
        #        these calibrators to its (differently-distributed) probabilities was
        #        the CR-01 defect that fed the gate miscalibrated inputs.
        scoring_model = inner_model

        x_holdout = holdout_eligible[list(_FEATURES)].to_numpy(dtype=float)
        outcome_idx = holdout_eligible["target_outcome_idx"].to_numpy(dtype=int)

        ml_holdout_raw = scoring_model.predict_proba(x_holdout)
        ml_holdout = ml_calibrator.transform(ml_holdout_raw)
        baseline_holdout = holdout_eligible[list(_DC_PROB_COLUMNS)].to_numpy(dtype=float)
        baseline_holdout = baseline_holdout / baseline_holdout.sum(axis=1, keepdims=True)
        ensemble_holdout = ens_calibrator.transform(
            _ensemble_probs(ml_holdout, baseline_holdout, weight)
        )

        candidate_probs = {
            "baseline": baseline_holdout,
            "ml": ml_holdout,
            "ensemble": ensemble_holdout,
        }
        candidate_metrics = {
            name: _metrics(probs, outcome_idx) for name, probs in candidate_probs.items()
        }
        for name, metrics in candidate_metrics.items():
            log_loss_by_candidate[name][holdout_name] = metrics["log_loss"]

        per_holdout_report[holdout_name] = {
            "cutoff": holdout.start,
            "tournament": holdout.tournament,
            "n_train": int(len(train)),
            "n_scored": int(len(holdout_eligible)),
            "n_excluded": n_holdout_excluded,
            "calibration_max_date": calibration_max_date,
            # CR-01 audit (T-05-13): the holdout is scored by the same model the
            # calibrators/weight were fit on, so the gate inputs are calibrated for the
            # distribution actually served. ``n_train`` counts ALL pre-cutoff eligible
            # rows; ``n_inner_fit`` is the subset the scoring model was fit on.
            "scoring_model": "inner_calibration_model",
            "n_inner_fit": int(len(inner_fit)),
            "n_inner_cal": int(len(inner_cal)),
            "chosen_ml_calibrator": ml_choice["method"],
            "chosen_ensemble_calibrator": ens_choice["method"],
            "ensemble_weight": float(weight),
            "ml_calibration_log_loss_by_method": ml_choice["log_loss_by_method"],
            "ensemble_calibration_log_loss_by_method": ens_choice["log_loss_by_method"],
            "candidates": {name: {"metrics": m} for name, m in candidate_metrics.items()},
        }

        match_ids = holdout_eligible["match_id"].tolist()
        for name, probs in candidate_probs.items():
            for match_id, outcome, prob in zip(match_ids, outcome_idx, probs, strict=True):
                prediction_rows.append(
                    {
                        "match_id": str(match_id),
                        "holdout": holdout_name,
                        "model": name,
                        "p_home_win": float(prob[0]),
                        "p_draw": float(prob[1]),
                        "p_away_win": float(prob[2]),
                        "outcome_idx": int(outcome),
                    }
                )

    gate = evaluate_ml_gate(
        log_loss_by_candidate["baseline"],
        log_loss_by_candidate["ml"],
        log_loss_by_candidate["ensemble"],
    )
    report = {
        "comparison": "baseline_vs_ml_vs_ensemble",
        "seed": int(seed),
        "feature_columns": list(_FEATURES),
        "min_prior_matches": int(MIN_PRIOR_MATCHES),
        "calibration_methods": list(CALIBRATION_METHODS),
        "ensemble_weight_grid": list(ENSEMBLE_WEIGHT_GRID),
        "gate": gate,
        "per_holdout": per_holdout_report,
    }
    return report, pd.DataFrame(prediction_rows)


def materialize_ml_comparison(
    dataset: pd.DataFrame | None = None,
    *,
    data_root: Path = Path("data"),
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Persist the calibrated comparison + gate verdict as dated artifacts."""
    report, predictions = run_ml_comparison(dataset, data_root=data_root, seed=seed)
    artifact_date = _artifact_date()
    models_root = data_root / "processed" / "models"
    models_root.mkdir(parents=True, exist_ok=True)

    report_path = models_root / f"ml_comparison_report_{artifact_date}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    predictions_path = models_root / f"ml_comparison_predictions_{artifact_date}.parquet"
    predictions.to_parquet(predictions_path, index=False)

    return {
        "comparison": report["comparison"],
        "promoted": bool(report["gate"]["promoted"]),
        "winner": report["gate"]["winner"],
        "mean_log_loss": report["gate"]["mean_log_loss"],
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
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run the calibrated baseline-vs-ML-vs-ensemble comparison + promotion gate.",
    )
    args = parser.parse_args()
    summary = (
        materialize_ml_comparison(data_root=args.data_root)
        if args.compare
        else materialize_ml_validation(data_root=args.data_root)
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
