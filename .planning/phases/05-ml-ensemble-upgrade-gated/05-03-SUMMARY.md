---
phase: 05-ml-ensemble-upgrade-gated
plan: "03"
subsystem: api
tags: [ml, calibration, isotonic, platt, ensemble, promotion-gate, temporal-validation, anti-leakage]

# Dependency graph
requires:
  - phase: 05-ml-ensemble-upgrade-gated
    plan: "02"
    provides: "MulticlassXGBoost wrapper; run_ml_validation fit-at-cutoff harness over the four Phase-2 holdouts with hard D-04 exclusion; HOLDOUTS calendar + log_loss/Brier/RPS family"
  - phase: 05-ml-ensemble-upgrade-gated
    plan: "01"
    provides: "build_ml_dataset point-in-time dataset, ML_FEATURE_COLUMNS (12) incl. point-in-time DC WDL probabilities, ml_eligible metadata"
provides:
  - "cdd_mundial.models.ml_calibration.MulticlassCalibrator: one-vs-rest per-class isotonic/sigmoid/none calibrator over already-computed 3-class probabilities, renormalized to valid rows"
  - "cdd_mundial.models.ml_calibration.select_best_calibration: empirical sigmoid-vs-isotonic-vs-none choice by validation log-loss on a disjoint slice (D-12)"
  - "cdd_mundial.models.ml_validation.evaluate_ml_gate: pure 4-holdout promotion gate (promote only if a candidate beats baseline log-loss on ALL four holdouts)"
  - "cdd_mundial.models.ml_validation.run_ml_comparison / materialize_ml_comparison: calibrated baseline-vs-ML-vs-ensemble comparison + dated gate report"
affects: [05-04-live-dual-publication]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Probability-in/probability-out calibration (not estimator wrapping): the only representation that covers XGBoost, baseline DC, and the probability-blend ensemble uniformly"
    - "Per-class one-vs-rest calibration (sklearn IsotonicRegression / _SigmoidCalibration) + renormalization keeps every calibrated row a valid 3-class distribution"
    - "Temporal inner split: pre-cutoff eligible rows -> earliest fit slice + latest inner calibration slice; calibrators and ensemble weight chosen on the cal slice ONLY, never the scored holdout (T-05-07)"
    - "Promotion gate is a pure function of per-holdout log-loss maps; 'baseline wins' is a first-class explicit outcome, never an implicit absence (T-05-09)"
    - "'none' calibration is an exact pass-through and is preferred on ties, so calibration is applied only when it strictly improves log-loss"

key-files:
  created:
    - "src/cdd_mundial/models/ml_calibration.py"
    - "tests/test_ml_calibration.py"
  modified:
    - "src/cdd_mundial/models/ml_validation.py"
    - "tests/test_ml_validation.py"
    - "src/cdd_mundial/models/__init__.py"

key-decisions:
  - "Calibration operates on already-computed probabilities rather than wrapping the estimator (cv='prefit' is removed anyway): the ensemble is a probability blend with no single sklearn estimator, so probability-in/probability-out is the only uniform contract across all three candidates"
  - "The baseline candidate reuses the point-in-time Dixon-Coles WDL columns already present in the ML dataset (D-02) instead of re-running the production DC model inside the harness — one point-in-time feature surface, one holdout calendar, no second leakage surface"
  - "Inner calibration/selection slice is the latest 25% (by date) of pre-cutoff eligible rows; the model re-fits on ALL pre-cutoff rows for final holdout scoring so calibrator selection never costs training data on the scored fold"
  - "Gate ties (both ML and ensemble clear) break toward 'ml' (simpler model); calibration ties break toward 'none' so the upgrade is only taken when it strictly helps"

patterns-established:
  - "A candidate enters the phase-level comparison only in its best calibrated form, chosen by held-out evidence, not assumption (D-11/D-12)"
  - "The upgrade decision is reproducible from code + dated artifact alone: per-holdout candidate metrics, chosen calibrator, ensemble weight, and the final gate verdict"

requirements-completed: [ML-03, ML-04]

# Metrics
duration: 14min
completed: 2026-06-16
---

# Phase 5 Plan 03: Calibrated Candidate Comparison + 4-Holdout Promotion Gate Summary

**A multiclass temporal calibration layer (one-vs-rest isotonic/Platt/none over already-computed 3-class probabilities) plus an extension of the ML harness that scores baseline, ML-solo, and a convex ensemble per holdout — selecting calibrators and the ensemble weight strictly on pre-holdout rows — and decides promotion through a pure gate that promotes a candidate only if it beats the baseline in log-loss on all four holdouts, treating "baseline wins" as a first-class auditable outcome.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 2 (both TDD)
- **Files created/modified:** 5

## Accomplishments

- `MulticlassCalibrator` calibrates 3-class probability vectors one-vs-rest using scikit-learn's `IsotonicRegression` and the internal `_SigmoidCalibration` (the exact Platt fit `CalibratedClassifierCV(method="sigmoid")` uses), then renormalizes so every output row stays a valid distribution. `method="none"` is an exact pass-through so the uncalibrated candidate competes on equal footing.
- `select_best_calibration` decides sigmoid vs isotonic vs none **empirically** by validation log-loss on a disjoint slice (D-12), with a deterministic argmin that lists `none` first so calibration is preferred only when it strictly improves. Isotonic is never assumed superior.
- Anti-leakage is structural (T-05-07): a calibrator only sees the rows passed to `fit`. `n_fit_samples` exposes exactly how many rows each per-class map was fit on, and a test asserts that count equals the train slice (never train+holdout).
- `evaluate_ml_gate` is a pure 4-holdout promotion gate (T-05-08): a candidate is promoted only if it beats the baseline in log-loss on **every** holdout (strictly, never tying). If both ML and ensemble clear, the lower mean log-loss wins (tie -> `ml`). If neither clears, the baseline stays live and that negative result is recorded explicitly with per-candidate `beats_baseline_all_holdouts` flags and `mean_log_loss` (T-05-09).
- `run_ml_comparison` scores three candidates per holdout: baseline (the point-in-time DC WDL columns from D-02), calibrated ML-solo, and a calibrated convex ensemble `w*ml + (1-w)*baseline`. For each holdout it splits the pre-cutoff eligible rows into an inner fit slice and a latest inner calibration slice; it selects the ML calibrator, the ensemble weight (grid `0.0..1.0`), and the ensemble calibrator on the calibration slice only, then re-fits the model on all pre-cutoff eligible rows to score the actual holdout. `calibration_max_date` proves the selection slice predates the cutoff.
- `materialize_ml_comparison` writes dated artifacts — `ml_comparison_report_<date>.json` (per-holdout candidate metrics, chosen calibrator, ensemble weight, per-method calibration log-loss, and the top-level gate verdict) plus `ml_comparison_predictions_<date>.parquet` carrying all three candidate families. A `--compare` CLI flag runs this path.
- Public surface exported via `cdd_mundial.models`: `MulticlassCalibrator`, `select_best_calibration`, `evaluate_ml_gate`, `run_ml_comparison`.

## Task Commits

Each task committed atomically (TDD RED -> GREEN):

1. **RED: failing calibration contract tests** — `82bfb09` (test)
2. **Task 1 GREEN: multiclass temporal calibration (isotonic/sigmoid/none)** — `d27d969` (feat)
3. **RED: failing baseline-vs-ML-vs-ensemble + 4-holdout gate tests** — `21d2e64` (test)
4. **Task 2 GREEN: calibrated comparison + 4-holdout promotion gate** — `00cd94a` (feat)

## Files Created/Modified

- `src/cdd_mundial/models/ml_calibration.py` (created) — `MulticlassCalibrator`, `select_best_calibration`, `fit_selected_calibrator`; one-vs-rest per-class calibration with renormalization and an exact `none` pass-through.
- `tests/test_ml_calibration.py` (created) — 6 tests: valid-distribution preservation for all methods, `none` no-op, transform-before-fit rejection, unknown-method rejection, fit-only-on-pre-holdout-rows (leakage audit via `n_fit_samples`), and empirical method selection by validation log-loss.
- `src/cdd_mundial/models/ml_validation.py` (modified) — added `evaluate_ml_gate`, `run_ml_comparison`, `materialize_ml_comparison`, the convex-ensemble helpers, the inner temporal split, and the `--compare` CLI flag.
- `tests/test_ml_validation.py` (modified) — +7 tests covering the pure gate (promote-on-all-four, ties don't promote, first-class negative result), three-candidate scoring, per-holdout calibrator/weight recording, pre-holdout-only calibration, top-level gate verdict, and dated gate-report materialization; synthetic dataset now emits valid DC probability features so the baseline candidate is a real competitor.
- `src/cdd_mundial/models/__init__.py` (modified) — exports the four new public functions/classes.

## Decisions Made

- **Probability-in/probability-out calibration over estimator wrapping.** `cv="prefit"` is removed from sklearn and the project mandates `FrozenEstimator` for wrapping a trained classifier — but the ensemble candidate is a probability blend with no single sklearn estimator to wrap. Calibrating already-computed probabilities one-vs-rest is the only representation that covers the XGBoost candidate, the baseline DC probabilities, and the ensemble uniformly, and it keeps the per-fold calibration cheap and auditable. The per-class primitives are still the sklearn-mandated isotonic/Platt fits.
- **Baseline candidate = the point-in-time DC WDL feature columns (D-02).** Re-running the production Dixon-Coles model inside the comparison harness would re-introduce the `UnknownTeamError` domain-limit issue noted in 05-02 and add a second leakage surface. The `p_*_dc` columns are already point-in-time by the 05-01 contract, so reusing them keeps one feature surface and the verbatim Phase-2 holdout calendar.
- **Inner 25%-by-date calibration slice + re-fit on all pre-cutoff rows.** Selecting calibrators/weight needs a held-out slice that is still strictly pre-cutoff (T-05-07). Reserving the latest 25% of pre-cutoff eligible rows for selection, then re-fitting the model on all pre-cutoff eligible rows for final scoring, means calibrator selection costs no training data on the scored fold.
- **Tie-breaking favors simplicity.** Gate ties resolve to `ml`; calibration ties resolve to `none`. The upgrade (and any calibration) is only taken when it strictly improves log-loss.

## Deviations from Plan

None — plan executed as written. Both tasks followed the prescribed TDD flow; no Rule 1–4 deviations were needed. The plan's Task 1 verify (`-k calibration`) selects the six calibration tests across both files and passes; Task 2's full-module verify passes all 19 `test_ml_validation.py` tests.

## Threat Model Compliance

- **T-05-07 (information disclosure, calibrator fitting):** mitigated — `MulticlassCalibrator` fits only on rows passed to `fit`; `run_ml_comparison` selects calibrators/weight on the latest pre-cutoff inner slice only. Tests `test_calibrator_fits_only_on_provided_pre_holdout_rows` (asserts `n_fit_samples == train size`) and `test_comparison_calibration_uses_only_pre_holdout_rows` (asserts `calibration_max_date < cutoff`).
- **T-05-08 (repudiation, promotion gate):** mitigated — `evaluate_ml_gate` is a pure function encoding the strict four-holdout criterion and is persisted into the dated report. Test `test_pure_gate_passes_only_when_candidate_beats_baseline_on_all_four`.
- **T-05-09 (information disclosure, negative-result handling):** mitigated — "baseline wins" is an explicit outcome with `promoted=False`, `winner="baseline"`, and per-candidate `beats_baseline_all_holdouts` fields. Test `test_pure_gate_negative_result_is_first_class`.

## Must-Haves Compliance

- "La comparacion metodologica de la fase incluye baseline, ML solo y ensemble." — `run_ml_comparison` scores all three per holdout; test asserts `{baseline, ml, ensemble}`.
- "ML solo y ensemble se calibran por separado dentro de validacion temporal; la calibracion no se aplica retroactivamente." — separate calibrator selection per candidate on a pre-cutoff inner slice; `calibration_max_date < cutoff` per holdout.
- "La promocion del upgrade solo ocurre si un candidato vence al baseline en log-loss en los cuatro holdouts." — encoded in `evaluate_ml_gate`'s strict all-holdouts criterion.

## Known Stubs

None. The synthetic dataset is test-only; the production comparison consumes the real `build_ml_dataset` feature contract (including the point-in-time DC probability columns). The canonical full-history backtest wiring (supplying a cutoff-correct DC model per holdout plus real `elo_history`, as `validation.py` does for the baseline) remains the production-materialization concern of the live-integration plan (05-04) — `run_ml_comparison` accepts a pre-built dataset precisely so that wiring is injectable. This boundary is inherited from 05-02 and is not a new stub.

## Next Phase Readiness

- ML-03 and ML-04 are structurally reachable: the phase can compare calibrated candidates honestly and decide promotion with an explicit, reproducible gate.
- Plan 05-04 (live dual publication) can consume `run_ml_comparison`'s gate verdict to decide whether the upgrade is published alongside the baseline, and can reuse `MulticlassCalibrator` + the selected weight for live inference. The dated `ml_comparison_report_<date>.json` is the auditable promotion record.
- No blockers.

## Self-Check: PASSED

- FOUND: src/cdd_mundial/models/ml_calibration.py
- FOUND: tests/test_ml_calibration.py
- FOUND: src/cdd_mundial/models/ml_validation.py (extended)
- FOUND: tests/test_ml_validation.py (extended)
- Commits verified: 82bfb09 (RED cal), d27d969 (Task 1 GREEN), 21d2e64 (RED gate), 00cd94a (Task 2 GREEN)
- Tests: 6 calibration + 19 ml_validation pass; 45 passed across ml_validation/ml_calibration/validation_temporal/ml_features with no regressions; ruff clean on all new/modified files.

## TDD Gate Compliance

- RED gates: `test(05-03)` commits `82bfb09` (calibration `ModuleNotFoundError`) and `21d2e64` (gate `ImportError`/`AttributeError`) confirmed failing before implementation.
- GREEN gates: `feat(05-03)` commits `d27d969` (Task 1) and `00cd94a` (Task 2) after their respective RED.
- No unexpected pass during RED (target symbols did not exist).

---
*Phase: 05-ml-ensemble-upgrade-gated*
*Completed: 2026-06-16*
