"""Conservative multiclass XGBoost wrapper + ML-only temporal harness tests (Phase 5, ML-02).

These tests freeze the *model contract* and the *temporal protocol* for the first ML
candidate BEFORE the candidate is allowed into any phase-level comparison:

Task 1 (wrapper, ``-k xgboost``):
* a small, deterministic 3-class probability model with explicit seeds and shallow,
  auditable defaults (D-05: natural units, no scaling baked in; no broad search),
* every predicted row is a valid probability distribution (>=0, sums to 1, shape (n, 3)),
* repeated fits/predictions under a fixed seed are bit-identical (R-threat T-05-05),
* malformed inputs (wrong column count, empty fit, unknown #classes) are rejected loudly.

Task 2 (harness):
* the ML candidate is scored across the exact four Phase-2 holdouts with fit-at-cutoff
  semantics reused verbatim (T-05-04),
* ineligible rows (D-04, ``ml_eligible == False``) never enter ML fitting or scoring
  (T-05-06),
* the dated artifacts (report JSON + holdout prediction table) explain what was trained,
  scored, and excluded, parallel to the baseline ``validation`` style.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from cdd_mundial.models.ml_features import ML_FEATURE_COLUMNS


# --------------------------------------------------------------------------- #
# Task 1: conservative multiclass XGBoost wrapper                             #
# --------------------------------------------------------------------------- #


def _separable_classification(
    n_per_class: int = 60, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """A trivially-separable 3-class problem over the 12 feature columns.

    Each class is a Gaussian blob with a distinct mean so a shallow tree model
    learns it perfectly; this keeps the wrapper tests deterministic and fast.
    """
    rng = np.random.default_rng(seed)
    n_features = len(ML_FEATURE_COLUMNS)
    blobs = []
    labels = []
    for cls in range(3):
        center = np.zeros(n_features)
        center[cls % n_features] = 5.0 * (cls + 1)
        blobs.append(rng.normal(center, 0.25, size=(n_per_class, n_features)))
        labels.append(np.full(n_per_class, cls, dtype=int))
    x = np.vstack(blobs)
    y = np.concatenate(labels)
    order = rng.permutation(len(y))
    return x[order], y[order]


def test_xgboost_predict_proba_rows_are_valid_distributions() -> None:
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    x, y = _separable_classification()
    model = MulticlassXGBoost().fit(x, y)
    probs = model.predict_proba(x)

    assert probs.shape == (len(y), 3)
    assert (probs >= 0.0).all()
    assert (probs <= 1.0).all()
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)


def test_xgboost_defaults_are_conservative_and_shallow() -> None:
    """D-05 / research: shallow trees, a fixed seed, multi:softprob, num_class=3, no search."""
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    model = MulticlassXGBoost()
    params = model.params

    assert params["objective"] == "multi:softprob"
    assert params["num_class"] == 3
    assert params["max_depth"] <= 4
    # A deterministic seed must be pinned by default (reproducibility, T-05-05).
    assert "seed" in params or "random_state" in params


def test_xgboost_is_deterministic_under_fixed_seed() -> None:
    """Two independent fits with the same seed give bit-identical probabilities (T-05-05)."""
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    x, y = _separable_classification(seed=1)
    a = MulticlassXGBoost(seed=123).fit(x, y).predict_proba(x)
    b = MulticlassXGBoost(seed=123).fit(x, y).predict_proba(x)

    np.testing.assert_array_equal(a, b)


def test_xgboost_learns_separable_signal() -> None:
    """Sanity: a separable 3-class problem is classified near-perfectly."""
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    x, y = _separable_classification(seed=2)
    model = MulticlassXGBoost(seed=7).fit(x, y)
    predicted = model.predict_proba(x).argmax(axis=1)

    accuracy = float((predicted == y).mean())
    assert accuracy > 0.95


def test_xgboost_rejects_feature_count_mismatch() -> None:
    """Predict with the wrong number of columns must fail loudly, not silently broadcast."""
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    x, y = _separable_classification(seed=3)
    model = MulticlassXGBoost(seed=3).fit(x, y)

    wrong = np.zeros((4, len(ML_FEATURE_COLUMNS) + 1))
    with pytest.raises(ValueError):
        model.predict_proba(wrong)


def test_xgboost_rejects_predict_before_fit() -> None:
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    model = MulticlassXGBoost()
    with pytest.raises((ValueError, RuntimeError)):
        model.predict_proba(np.zeros((2, len(ML_FEATURE_COLUMNS))))


def test_xgboost_rejects_non_three_class_targets() -> None:
    """The wrapper is hard-wired to the canonical 3-way target (0/1/2)."""
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost

    x = np.zeros((6, len(ML_FEATURE_COLUMNS)))
    y = np.array([0, 1, 0, 1, 0, 1])  # only two classes present
    with pytest.raises(ValueError):
        MulticlassXGBoost().fit(x, y)


# --------------------------------------------------------------------------- #
# Task 2: ML-only temporal holdout harness                                    #
# --------------------------------------------------------------------------- #


def _synthetic_ml_dataset() -> pd.DataFrame:
    """A small ML-feature frame spanning the four holdout years plus prior training years.

    Built to exercise the harness contract directly (cutoff selection, eligibility
    filtering, metric shape) without depending on the real parquet, so the suite
    runs in the quick (non ``data_acceptance``) path.
    """
    rng = np.random.default_rng(99)
    from cdd_mundial.models.validation import HOLDOUTS

    rows: list[dict[str, object]] = []
    match_counter = 0

    def _emit(year: int, tournament: str, month: int, day: int, eligible: bool) -> None:
        nonlocal match_counter
        match_counter += 1
        outcome = int(rng.integers(0, 3))
        feat = {col: float(rng.normal()) for col in ML_FEATURE_COLUMNS}
        # Inject a weak but learnable signal so the model is not pathological.
        feat["elo_diff"] = float((outcome - 1) * 120.0 + rng.normal(0, 20))
        rows.append(
            {
                "match_id": f"s{match_counter}",
                "date": pd.Timestamp(year=year, month=month, day=day),
                "home_team_id": f"h{match_counter}",
                "away_team_id": f"a{match_counter}",
                "tournament": tournament,
                "target_outcome_idx": outcome,
                "ml_eligible": eligible,
                "has_min_history_home": eligible,
                "has_min_history_away": eligible,
                **feat,
            }
        )

    # Training history before every cutoff: lots of eligible rows in 2016-2017.
    for _ in range(300):
        y = int(rng.integers(2015, 2018))
        _emit(y, "Friendly", int(rng.integers(1, 12)), int(rng.integers(1, 28)), eligible=True)
    # A handful of ineligible training rows that must never be fit on.
    for _ in range(20):
        _emit(2017, "Friendly", 6, 1, eligible=False)

    # Each holdout: emit exactly its expected_matches count on/after the cutoff.
    for holdout in HOLDOUTS.values():
        cutoff = pd.Timestamp(holdout.start)
        for i in range(holdout.expected_matches):
            _emit(
                holdout.year,
                holdout.tournament,
                cutoff.month,
                min(cutoff.day + (i % 5), 28),
                eligible=(i != 0),  # one ineligible holdout row per tournament
            )

    return pd.DataFrame(rows)


def test_harness_excludes_ineligible_rows_from_fit_and_score() -> None:
    """D-04 / T-05-06: ``ml_eligible == False`` rows never reach fit or scoring."""
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    report, predictions = ml_validation.run_ml_validation(dataset)

    # No prediction row may correspond to an ineligible match.
    ineligible_ids = set(dataset.loc[~dataset["ml_eligible"], "match_id"])
    assert not (set(predictions["match_id"]) & ineligible_ids)

    # The report must state, per holdout, how many rows were excluded.
    for holdout_name, info in report["per_holdout"].items():
        assert "n_excluded" in info
        assert info["n_excluded"] >= 1  # we injected one ineligible row per holdout


def test_harness_covers_all_four_holdouts_with_metric_family() -> None:
    """T-05-04: same four holdouts and the log-loss/Brier/RPS family as the baseline."""
    from cdd_mundial.models import ml_validation
    from cdd_mundial.models.validation import HOLDOUTS

    dataset = _synthetic_ml_dataset()
    report, _ = ml_validation.run_ml_validation(dataset)

    assert set(report["per_holdout"]) == set(HOLDOUTS)
    for info in report["per_holdout"].values():
        assert set(info["metrics"]) == {"log_loss", "brier", "rps"}


def test_harness_fit_is_strictly_before_each_cutoff() -> None:
    """Anti-leakage: a holdout's own matches never enter its training fit."""
    from cdd_mundial.models import ml_validation
    from cdd_mundial.models.validation import HOLDOUTS

    dataset = _synthetic_ml_dataset()
    report, _ = ml_validation.run_ml_validation(dataset)

    for holdout_name, holdout in HOLDOUTS.items():
        info = report["per_holdout"][holdout_name]
        assert info["cutoff"] == holdout.start
        # Every training row used must predate the cutoff.
        assert info["train_max_date"] < holdout.start


def test_harness_prediction_rows_are_valid_distributions() -> None:
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    _, predictions = ml_validation.run_ml_validation(dataset)

    probs = predictions[["p_home_win", "p_draw", "p_away_win"]].to_numpy(dtype=float)
    assert (probs >= 0.0).all()
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)
    assert set(predictions["model"].unique()) == {"ml_xgboost"}


def test_harness_materializes_dated_artifacts(test_workspace) -> None:
    """Artifacts mirror the baseline style: report JSON + holdout prediction table."""
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    data_root = test_workspace / "data"
    summary = ml_validation.materialize_ml_validation(dataset, data_root=data_root)

    report_path = data_root / "processed" / "models"
    report_files = list(report_path.glob("ml_validation_report_*.json"))
    pred_files = list(report_path.glob("ml_holdout_predictions_*.parquet"))
    assert len(report_files) == 1
    assert len(pred_files) == 1

    report = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert set(report["per_holdout"]) == set(summary["per_holdout"])
    # The report records the ML feature contract it trained on (auditability).
    assert tuple(report["feature_columns"]) == tuple(ML_FEATURE_COLUMNS)
    assert report["min_prior_matches"] >= 1
