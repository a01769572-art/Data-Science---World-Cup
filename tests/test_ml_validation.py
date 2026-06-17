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
        # The DC probability features must be valid 3-class distributions: they double
        # as the baseline candidate's point-in-time predictions (D-02). Bias them
        # toward the realized outcome so the baseline is a non-trivial competitor.
        dc_logits = rng.normal(0.0, 0.6, size=3)
        dc_logits[outcome] += 1.2
        dc_p = np.exp(dc_logits)
        dc_p /= dc_p.sum()
        feat["p_home_win_dc"] = float(dc_p[0])
        feat["p_draw_dc"] = float(dc_p[1])
        feat["p_away_win_dc"] = float(dc_p[2])
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


# --------------------------------------------------------------------------- #
# Plan 03: calibrated baseline-vs-ML-vs-ensemble comparison + promotion gate   #
# --------------------------------------------------------------------------- #


def test_pure_gate_passes_only_when_candidate_beats_baseline_on_all_four() -> None:
    """T-05-08: the promotion gate is a pure 4-holdout log-loss criterion.

    A candidate is promoted only if it beats the baseline in log-loss on EVERY
    holdout. Beating it on three of four (or tying on one) must NOT promote.
    """
    from cdd_mundial.models.ml_validation import evaluate_ml_gate
    from cdd_mundial.models.validation import HOLDOUTS

    names = list(HOLDOUTS)
    baseline = {h: 1.00 for h in names}

    # ML wins on all four -> ML promoted.
    ml_all_win = {h: 0.90 for h in names}
    ens_worse = {h: 1.10 for h in names}
    gate = evaluate_ml_gate(baseline, ml_all_win, ens_worse)
    assert gate["promoted"] is True
    assert gate["winner"] == "ml"

    # ML ties on one holdout -> not strictly better everywhere -> no promotion.
    ml_one_tie = {**{h: 0.90 for h in names}, names[0]: 1.00}
    gate2 = evaluate_ml_gate(baseline, ml_one_tie, ens_worse)
    assert gate2["promoted"] is False
    assert gate2["winner"] == "baseline"


def test_pure_gate_negative_result_is_first_class() -> None:
    """T-05-09: 'baseline wins' is an explicit successful outcome, not an absence."""
    from cdd_mundial.models.ml_validation import evaluate_ml_gate
    from cdd_mundial.models.validation import HOLDOUTS

    names = list(HOLDOUTS)
    baseline = {h: 0.80 for h in names}
    ml = {h: 0.95 for h in names}
    ensemble = {h: 0.90 for h in names}

    gate = evaluate_ml_gate(baseline, ml, ensemble)
    assert gate["promoted"] is False
    assert gate["winner"] == "baseline"
    # The report explains WHY, per holdout, the candidates failed (auditable).
    assert set(gate["beats_baseline_all_holdouts"]) == {"ml", "ensemble"}
    assert gate["beats_baseline_all_holdouts"]["ml"] is False
    assert gate["beats_baseline_all_holdouts"]["ensemble"] is False


def test_comparison_scores_three_candidates_per_holdout() -> None:
    """D-10: every holdout reports baseline, ml, and ensemble metrics."""
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    report, predictions = ml_validation.run_ml_comparison(dataset)

    for info in report["per_holdout"].values():
        assert set(info["candidates"]) == {"baseline", "ml", "ensemble"}
        for cand in ("baseline", "ml", "ensemble"):
            assert set(info["candidates"][cand]["metrics"]) == {"log_loss", "brier", "rps"}

    # Predictions carry all three candidate families.
    assert set(predictions["model"].unique()) == {"baseline", "ml", "ensemble"}


def test_comparison_records_chosen_calibrator_and_weight_per_holdout() -> None:
    """D-11/D-12: each holdout names the calibrator used and the ensemble weight."""
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    report, _ = ml_validation.run_ml_comparison(dataset)

    for info in report["per_holdout"].values():
        assert info["chosen_ml_calibrator"] in {"none", "sigmoid", "isotonic"}
        assert info["chosen_ensemble_calibrator"] in {"none", "sigmoid", "isotonic"}
        w = info["ensemble_weight"]
        assert 0.0 <= w <= 1.0


def test_comparison_calibration_uses_only_pre_holdout_rows(monkeypatch) -> None:
    """T-05-07: calibrators/weights are selected without touching the scored holdout.

    We assert that the dates of every row used to fit calibration are strictly before
    the holdout cutoff, via the per-holdout audit field the harness must expose.
    """
    from cdd_mundial.models import ml_validation
    from cdd_mundial.models.validation import HOLDOUTS

    dataset = _synthetic_ml_dataset()
    report, _ = ml_validation.run_ml_comparison(dataset)

    for holdout_name, holdout in HOLDOUTS.items():
        info = report["per_holdout"][holdout_name]
        # The latest date used anywhere in calibration/selection predates the cutoff.
        assert info["calibration_max_date"] < holdout.start


def test_comparison_emits_top_level_gate_verdict() -> None:
    """The phase-level gate verdict is reproducible from the report alone."""
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    report, _ = ml_validation.run_ml_comparison(dataset)

    gate = report["gate"]
    assert isinstance(gate["promoted"], bool)
    assert gate["winner"] in {"baseline", "ml", "ensemble"}
    # Mean log-loss per candidate over the four holdouts is recorded.
    assert set(gate["mean_log_loss"]) == {"baseline", "ml", "ensemble"}


def test_comparison_materializes_dated_gate_report(test_workspace) -> None:
    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    data_root = test_workspace / "data"
    summary = ml_validation.materialize_ml_comparison(dataset, data_root=data_root)

    models_root = data_root / "processed" / "models"
    report_files = list(models_root.glob("ml_comparison_report_*.json"))
    pred_files = list(models_root.glob("ml_comparison_predictions_*.parquet"))
    assert len(report_files) == 1
    assert len(pred_files) == 1

    report = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert report["gate"]["winner"] == summary["winner"]
    assert isinstance(report["gate"]["promoted"], bool)


# --------------------------------------------------------------------------- #
# CR-01 regression guard: train/serve model identity in run_ml_comparison      #
# --------------------------------------------------------------------------- #


def _instrument_identity(monkeypatch, *, distort_holdout_scoring: bool = False):
    """Install identity instrumentation over ``run_ml_comparison`` and run it.

    Returns a dict of captured maps that let a caller assert the CR-01 *identity*
    invariant — not a fit count. The instrumentation is layered so the assertion can
    anchor on the VERBATIM ``predict_proba`` output of the calibration model (WR-01
    note #1), and pairs calibration-fit with scoring-transform by CALIBRATOR OBJECT
    identity, never by call-sequence index (WR-01 note #2):

    * ``verbatim_output_ids``     -- ``set`` of ``id(out)`` for every UNDISTORTED
      ``predict_proba`` return value (the raw the model actually produced);
    * ``output_to_model``         -- ``id(verbatim_out) -> id(producing model)``;
    * ``models_per_run``          -- ``id(model)`` in fit order (kept as a COMPLEMENTARY
      count guard for the literal ``final_model`` defect);
    * ``cal_fit_producer``        -- ``id(calibrator) -> id(model whose verbatim raw it
      was fit on)`` (``None`` if the fit array was not a verbatim model output);
    * ``cal_transform_inputs``    -- ``list[(id(calibrator), id(probs))]`` for every
      ``transform`` call, in order.

    When ``distort_holdout_scoring`` is True the verifier's WR-01 probe is applied: the
    holdout-scoring raw (``ml_holdout_raw``) is replaced by ``out**3`` renormalized,
    WITHOUT adding any extra ``fit()``. Critically the distortion wraps OVER the verbatim
    tracker, so the array the scoring ``transform`` receives is a DERIVED array whose
    ``id`` is absent from ``verbatim_output_ids`` — exactly the signal the identity
    assertion must catch and the count guard cannot.
    """
    from cdd_mundial.models.ml_xgboost import MulticlassXGBoost
    from cdd_mundial.models import ml_calibration

    verbatim_output_ids: set[int] = set()
    output_to_model: dict[int, int] = {}
    models_per_run: list[int] = []
    cal_fit_producer: dict[int, int | None] = {}
    cal_transform_inputs: list[tuple[int, int]] = []
    # Keep a strong reference to every object we identify by ``id`` for the duration of the
    # run: the predict_proba arrays AND the model/calibrator objects whose ids are stored as
    # dict keys/values. Without this, those objects are garbage-collected once unused and
    # CPython recycles their ``id`` for a later object, silently corrupting the id->model map
    # and the calibrator-keyed producer map (cross-holdout id reuse — the source of the
    # full-suite-only false positive). Holding references pins every id unique for the run.
    _retained: list[object] = []

    real_fit = MulticlassXGBoost.fit
    real_predict = MulticlassXGBoost.predict_proba
    real_cal_fit = ml_calibration.MulticlassCalibrator.fit
    real_cal_transform = ml_calibration.MulticlassCalibrator.transform

    def tracking_fit(self, x, y):
        _retained.append(self)  # pin the model OBJECT so its id can't be recycled
        models_per_run.append(id(self))
        return real_fit(self, x, y)

    # Inner tracker: record the VERBATIM output the model produced. This is the array
    # whose id legitimately means "produced by this model".
    def tracking_predict(self, x):
        out = real_predict(self, x)
        _retained.append(out)  # pin id(out) so it cannot be recycled (id-reuse hazard)
        _retained.append(self)  # pin the producing model OBJECT (id stored as a value)
        verbatim_output_ids.add(id(out))
        output_to_model[id(out)] = id(self)
        return out

    monkeypatch.setattr(MulticlassXGBoost, "fit", tracking_fit)
    monkeypatch.setattr(MulticlassXGBoost, "predict_proba", tracking_predict)

    if distort_holdout_scoring:
        # The synthetic holdouts each scored a known eligible-row count; distort only the
        # predict_proba whose input row count matches a holdout's scored count, i.e. only
        # ``ml_holdout_raw``. No extra fit() is added (count stays n_holdouts).
        from cdd_mundial.models.validation import HOLDOUTS as _HOLDOUTS

        probe_dataset = _synthetic_ml_dataset()
        holdout_scored_counts: set[int] = set()
        for holdout in _HOLDOUTS.values():
            sel = probe_dataset[
                (probe_dataset["tournament"] == holdout.tournament)
                & (pd.to_datetime(probe_dataset["date"]).dt.year == holdout.year)
            ]
            holdout_scored_counts.add(int(sel["ml_eligible"].astype(bool).sum()))

        inner_predict = MulticlassXGBoost.predict_proba  # == tracking_predict

        def distorting_predict(self, x):
            out = inner_predict(self, x)  # verbatim id already registered by the tracker
            if len(x) in holdout_scored_counts:
                distorted = out**3
                distorted = distorted / distorted.sum(axis=1, keepdims=True)
                _retained.append(distorted)  # pin id so it can't collide with a verbatim id
                # NOTE: distorted is a NEW array; its id is NOT in verbatim_output_ids,
                # and we deliberately do NOT register it — that is the mismatch signal.
                return distorted
            return out

        monkeypatch.setattr(MulticlassXGBoost, "predict_proba", distorting_predict)

    def tracking_cal_fit(self, probs, y):
        # Pair by calibrator OBJECT identity: remember which verbatim model produced the
        # raw THIS calibrator was fit on (None if the fit array is not a verbatim output).
        _retained.append(probs)  # pin the fit array's id for the run
        _retained.append(self)  # pin the calibrator OBJECT so id(self) (the dict key) is unique
        cal_fit_producer[id(self)] = output_to_model.get(id(probs))
        return real_cal_fit(self, probs, y)

    def tracking_cal_transform(self, probs):
        _retained.append(probs)  # pin id(probs) for the run so comparisons stay valid
        _retained.append(self)  # pin the calibrator OBJECT so id(self) cannot be recycled
        cal_transform_inputs.append((id(self), id(probs)))
        return real_cal_transform(self, probs)

    monkeypatch.setattr(
        "cdd_mundial.models.ml_validation.MulticlassCalibrator.fit", tracking_cal_fit
    )
    monkeypatch.setattr(
        "cdd_mundial.models.ml_validation.MulticlassCalibrator.transform",
        tracking_cal_transform,
    )

    from cdd_mundial.models import ml_validation

    dataset = _synthetic_ml_dataset()
    report, _ = ml_validation.run_ml_comparison(dataset)

    return {
        "report": report,
        "verbatim_output_ids": verbatim_output_ids,
        "output_to_model": output_to_model,
        "models_per_run": models_per_run,
        "cal_fit_producer": cal_fit_producer,
        "cal_transform_inputs": cal_transform_inputs,
        # Return the strong references so every tracked id stays pinned through the
        # assertion that runs AFTER this function returns. Dropping these would let
        # CPython recycle ids mid-assertion and corrupt the verbatim/producer maps.
        "_retained": _retained,
    }


def _assert_train_serve_identity(captured) -> None:
    """Load-bearing CR-01 IDENTITY assertion (replaces the old fit-count proxy).

    For the ML calibrator that scores each holdout, the array it transforms at scoring
    time MUST be a VERBATIM ``predict_proba`` output (``id`` in ``verbatim_output_ids``)
    produced by the SAME model whose verbatim raw fed that calibrator's ``fit``. This is
    identity of model AND of distribution, paired by calibrator object — so it fails both
    the literal ``final_model`` re-fit (different producing model) and a distribution
    mismatch with no extra fit (a derived, non-verbatim scoring array).
    """
    from cdd_mundial.models.validation import HOLDOUTS

    output_to_model = captured["output_to_model"]
    verbatim_output_ids = captured["verbatim_output_ids"]
    cal_fit_producer = captured["cal_fit_producer"]
    cal_transform_inputs = captured["cal_transform_inputs"]

    # Sanity: instrumentation actually captured calibration-fit producers.
    fit_models = {m for m in cal_fit_producer.values() if m is not None}
    assert fit_models, "no calibration-fit raw array traced to a verbatim model output"

    # The ML scoring transform for each holdout is the FIRST transform call made by a
    # calibrator that was fit on a verbatim model output (ml_calibrator.transform of
    # ml_holdout_raw at ml_validation.py:439). Iterate transform calls; for each
    # calibrator that was fit on a verbatim producer, the first array it transforms after
    # being fit on the holdout-scoring path must itself be a verbatim output of THAT SAME
    # model. We check every transform whose calibrator has a known fit producer.
    checked = 0
    for cal_id, probs_id in cal_transform_inputs:
        producer = cal_fit_producer.get(cal_id)
        if producer is None:
            # Calibrator fit on a derived (ensemble) array — its scoring distribution
            # identity is enforced transitively via the ML calibrator below; skip.
            continue
        # IDENTITY: the transformed scoring array must be a VERBATIM model output ...
        assert probs_id in verbatim_output_ids, (
            "CR-01 identity violation: a calibrator fit on a model's verbatim raw is "
            "transforming a NON-verbatim (derived/distorted) array at scoring time — the "
            "served distribution differs from the one calibrated (mismatch without an "
            "extra fit())"
        )
        # ... produced by the SAME model whose raw the calibrator was fit on.
        assert output_to_model.get(probs_id) == producer, (
            "CR-01 identity violation: the holdout-scoring array was produced by a "
            "DIFFERENT model than the one the calibrator was fit on (re-fit final_model)"
        )
        checked += 1

    # One ML calibrator transforms a verbatim scoring array per holdout.
    assert checked >= len(HOLDOUTS), (
        f"expected at least one verbatim-producer scoring transform per holdout "
        f"({len(HOLDOUTS)}), checked {checked}"
    )

    # COMPLEMENTARY count guard (not the only assertion): the literal final_model defect
    # also re-fits a second model per holdout, doubling the fit count.
    n_models = len(captured["models_per_run"])
    assert n_models == len(HOLDOUTS), (
        f"expected exactly one model per holdout (train==serve), got {n_models} "
        f"across {len(HOLDOUTS)} holdouts — a second model reintroduces CR-01"
    )


def test_comparison_scores_holdout_with_the_same_model_calibrators_were_fit_on(
    monkeypatch,
) -> None:
    """CR-01 regression: the model whose raw probabilities the calibrators/weight are
    fit on MUST be the same model that produces the holdout raw probabilities those
    calibrators then transform.

    The original defect fit ``ml_calibrator``/``ens_calibrator``/``weight`` against an
    ``inner_model`` (trained on ~75% of pre-cutoff rows) yet scored the holdout with a
    *different* ``final_model`` (re-fit on ALL pre-cutoff rows). Their probability
    distributions differ, so the per-class isotonic/sigmoid maps were invalid for the
    served distribution and the gate verdict was computed on miscalibrated inputs.

    The load-bearing assertion (``_assert_train_serve_identity``) proves IDENTITY, not a
    fit count: per holdout, the array the ML calibrator transforms at scoring time is a
    VERBATIM ``predict_proba`` output of the SAME model whose verbatim raw fed that same
    calibrator's ``fit`` — paired by calibrator object, anchored on the verbatim output
    of the calibration model. It fails on a re-fit ``final_model`` AND on a distribution
    mismatch with no extra fit (see the sibling ``...guard_fails_on_distribution...``).
    """
    captured = _instrument_identity(monkeypatch, distort_holdout_scoring=False)

    # The comparison must still produce a valid gate verdict.
    assert captured["report"]["gate"]["winner"] in {"baseline", "ml", "ensemble"}

    _assert_train_serve_identity(captured)


def test_comparison_guard_fails_on_distribution_mismatch_without_extra_fit(
    monkeypatch,
) -> None:
    """WR-01: the strengthened guard MUST fail the verifier's mismatch-without-extra-fit
    probe — distorting ``ml_holdout_raw`` (cube + renormalize) so the distribution the
    calibrators transform at scoring time differs from the one they were fit on, WITHOUT
    adding any ``fit()`` call (the per-holdout fit count stays at ``len(HOLDOUTS)``).

    Under the old count-based guard this probe PASSED (the documented WR-01 defect). The
    identity assertion now catches it: the scoring array is a DERIVED (non-verbatim)
    array, so ``id(probs) not in verbatim_output_ids`` and the guard raises. This turns
    the Task-1 RED scaffold into a permanent green assertion that the guard bites.
    """
    captured = _instrument_identity(monkeypatch, distort_holdout_scoring=True)

    # No extra fit() was added: the count proxy alone would still pass (proves the probe
    # is a distribution mismatch, not a literal final_model re-fit).
    from cdd_mundial.models.validation import HOLDOUTS

    assert len(captured["models_per_run"]) == len(HOLDOUTS)

    # The strengthened identity guard MUST raise on this mismatch.
    with pytest.raises(AssertionError, match="CR-01 identity violation"):
        _assert_train_serve_identity(captured)
