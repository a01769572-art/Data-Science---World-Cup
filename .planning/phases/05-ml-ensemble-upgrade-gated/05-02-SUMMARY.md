---
phase: 05-ml-ensemble-upgrade-gated
plan: "02"
subsystem: api
tags: [ml, xgboost, multiclass, temporal-validation, holdouts, anti-leakage, determinism]

# Dependency graph
requires:
  - phase: 05-ml-ensemble-upgrade-gated
    plan: "01"
    provides: "build_ml_dataset point-in-time dataset, ML_FEATURE_COLUMNS (12), MIN_PRIOR_MATCHES, ml_eligible metadata"
  - phase: 02-baseline-elo-dixoncoles
    provides: "HOLDOUTS calendar, select_holdout, log_loss/Brier/RPS metric family (validation.py + metrics.py)"
provides:
  - "cdd_mundial.models.MulticlassXGBoost: conservative deterministic 3-class probability wrapper (multi:softprob, num_class=3, max_depth=3, pinned seed)"
  - "cdd_mundial.models.ml_validation.run_ml_validation: ML-only fit-at-cutoff harness over the four Phase-2 holdouts with hard D-04 exclusion"
  - "cdd_mundial.models.ml_validation.materialize_ml_validation: dated report JSON + holdout prediction parquet artifacts"
affects: [05-03-calibration-ensemble-gate, 05-04-live-dual-publication]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wrapper forces the canonical 3-way contract (objective/num_class) regardless of caller param overrides — model identity cannot drift"
    - "Determinism via pinned seed + single-thread exact tree method, asserted by a two-fit bit-identity test (T-05-05)"
    - "D-04 exclusion applied to BOTH the training fit and the scoring set, with per-holdout n_excluded recorded for audit (T-05-06)"
    - "ML harness imports HOLDOUTS/Holdout from baseline validation.py verbatim so the holdout calendar cannot fork"

key-files:
  created:
    - "src/cdd_mundial/models/ml_xgboost.py"
    - "src/cdd_mundial/models/ml_validation.py"
    - "tests/test_ml_validation.py"
  modified:
    - "src/cdd_mundial/models/__init__.py"

key-decisions:
  - "ML predictions use a self-contained dated artifact + local normalization check rather than the frozen baseline HoldoutPredictionsSchema, whose model field is restricted to baseline names — keeps ML-candidate churn decoupled from the baseline contract"
  - "_select_ml_holdout selects by exact tournament string + year but does NOT assert the official match count: the ML dataset legitimately drops ineligible rows, so eligible-per-holdout counts are reported (n_scored/n_excluded), not enforced"
  - "Wrapper exposes only fit/predict_proba/params; no calibration, no hyperparameter search, no eligibility filtering — those belong to the harness and Plan 03"

patterns-established:
  - "First ML candidate is held to the same temporal discipline as the baseline before it is allowed into any comparison"
  - "Eligibility (D-04) is enforced at the harness boundary, never inside the model wrapper"

requirements-completed: [ML-02]

# Metrics
duration: 5min
completed: 2026-06-16
---

# Phase 5 Plan 02: Conservative XGBoost Candidate + ML-Only Temporal Harness Summary

**A small, deterministic multiclass XGBoost wrapper (`multi:softprob`, `num_class=3`, `max_depth=3`, pinned seed) plus an ML-only fit-at-cutoff harness that reuses the Phase-2 holdouts and log-loss/Brier/RPS family verbatim, excludes D-04-ineligible rows from both fit and scoring, and writes dated report + prediction artifacts.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-16T01:35:46Z
- **Completed:** 2026-06-16T01:40:34Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4

## Accomplishments

- `MulticlassXGBoost` is a thin, auditable wrapper around XGBoost's native API: `multi:softprob` + `num_class=3` are forced regardless of caller overrides; shallow trees (`max_depth=3`), modest boosting rounds, and a pinned seed keep it conservative (research §4, D-05).
- Determinism is contract-tested: two independent fits with the same seed produce bit-identical probability matrices (single-thread + `tree_method="exact"`), closing threat T-05-05.
- Malformed inputs fail loudly: feature-count mismatch, predict-before-fit, and non-3-class targets all raise instead of silently degrading.
- `run_ml_validation` scores the candidate across `wc2018`, `wc2022`, `euro2024`, `copa2024` under fit-at-cutoff semantics, importing `HOLDOUTS`/`Holdout` straight from the baseline `validation.py` so the calendar and metric family cannot fork (T-05-04).
- D-04 exclusion is hard on both sides of the fold (T-05-06): ineligible rows never enter the training fit nor the scoring set, and the report records `n_excluded`, `n_train_excluded`, `n_train`, `n_scored`, and `train_max_date` per holdout for auditability.
- `materialize_ml_validation` persists dated artifacts parallel to the baseline style: `ml_validation_report_<date>.json` (carrying the exact `feature_columns` and `min_prior_matches` it trained on) plus `ml_holdout_predictions_<date>.parquet`.
- Public wrapper exported as `cdd_mundial.models.MulticlassXGBoost`; harness reachable as `cdd_mundial.models.ml_validation`.

## Task Commits

Each task committed atomically (TDD RED → GREEN):

1. **RED: failing wrapper + harness contract tests** — `c84b693` (test)
2. **Task 1 GREEN: conservative deterministic multiclass XGBoost wrapper** — `7bd25d1` (feat)
3. **Task 2 GREEN: ML-only temporal holdout harness + dated artifacts** — `ce97715` (feat)

_Note: a single RED commit covers both tasks' failing tests (one test module). Each task's implementation then turned its slice green independently — `-k xgboost` for Task 1, the full module for Task 2 — preserving a clean RED→GREEN sequence per task._

## Files Created/Modified

- `src/cdd_mundial/models/ml_xgboost.py` — `MulticlassXGBoost` wrapper: forced 3-way contract, pinned-seed determinism, shallow conservative defaults, loud input validation.
- `src/cdd_mundial/models/ml_validation.py` — `run_ml_validation` / `materialize_ml_validation`: fit-at-cutoff over the four baseline holdouts, hard D-04 exclusion, dated report + prediction artifacts.
- `tests/test_ml_validation.py` — 12 tests: 7 wrapper (valid prob rows, conservative defaults, seed determinism, separable-signal sanity, three rejection paths) + 5 harness (eligibility exclusion, holdout/metric coverage, strict pre-cutoff fit, valid prediction rows, dated artifacts).
- `src/cdd_mundial/models/__init__.py` — exports `MulticlassXGBoost`.

## Decisions Made

- **Self-contained ML predictions artifact** instead of reusing the frozen baseline `HoldoutPredictionsSchema`: that schema restricts the `model` column to `{dixon_coles, uniform, solo_elo}` and asserts the full official match count. The ML candidate is `ml_xgboost` and legitimately scores a reduced (eligible-only) set, so coupling it to the baseline schema would have forced an architectural change to a frozen Phase-2 contract. The harness instead writes its own dated artifacts and validates normalization locally — keeping ML churn decoupled from the baseline.
- **`_select_ml_holdout` reports, not enforces, holdout counts**: it selects by exact tournament string + year (same anti-collision discipline as `select_holdout`, e.g. excluding "Copa América qualification") but does not assert `expected_matches`, because D-04 exclusion makes the eligible count data-dependent. The excluded/scored counts are surfaced in the report.
- **Eligibility lives at the harness boundary, never in the model**: `MulticlassXGBoost` is a pure model contract; the harness owns the D-04 filter. This keeps the wrapper reusable for the calibrated/ensemble candidates in Plan 03 without re-implementing filtering.

## Deviations from Plan

None — plan executed as written. Both tasks followed the prescribed TDD flow; no Rule 1–4 deviations were needed.

## Note on the real full-history backtest path

The unit suite injects a deterministic/stub `dc_predict` (or synthetic feature frames), matching the 05-01 contract. Building the *entire* deep-history ML dataset with the **production** Dixon-Coles predictor raises `UnknownTeamError` for ancient teams (e.g. `czechoslovakia`) the production model never saw — this is the production model's domain limit, not a harness defect. The canonical backtest wiring (supplying a cutoff-correct DC model fit per holdout plus real `elo_history`, exactly as `validation.py` does for the baseline) is the production materialization concern and is built in the later production/integration plan. `run_ml_validation` accepts a pre-built dataset precisely so this wiring is injectable rather than hard-coded.

## Threat Model Compliance

- **T-05-04 (tampering, holdout evaluation):** mitigated — `HOLDOUTS`/`Holdout` imported verbatim from `validation.py`; same four cutoffs and the same `log_loss`/`brier`/`rps` family. Test `test_harness_covers_all_four_holdouts_with_metric_family` + `test_harness_fit_is_strictly_before_each_cutoff`.
- **T-05-05 (repudiation, determinism):** mitigated — pinned seed + single-thread exact trees; `test_xgboost_is_deterministic_under_fixed_seed` asserts bit-identical repeated fits.
- **T-05-06 (tampering, low-coverage rows):** mitigated — `_eligible` filter on both train and score sets; `test_harness_excludes_ineligible_rows_from_fit_and_score` asserts no ineligible match reaches predictions and `n_excluded >= 1` per holdout.

## Known Stubs

None. No placeholder data flows to any output; the synthetic dataset is test-only and the wrapper/harness operate on real feature contracts.

## Next Phase Readiness

- ML-02 is reachable: a conservative XGBoost candidate can be trained and scored under the same temporal discipline as the baseline, with reproducible dated artifacts.
- Plan 03 (calibration + ensemble + promotion gate) can wrap `MulticlassXGBoost` in `CalibratedClassifierCV`/manual calibrators, blend its `predict_proba` with the baseline DC probabilities, and reuse `run_ml_validation`'s fold structure for the gate.
- No blockers.

## Self-Check: PASSED

- FOUND: src/cdd_mundial/models/ml_xgboost.py
- FOUND: src/cdd_mundial/models/ml_validation.py
- FOUND: tests/test_ml_validation.py
- FOUND: .planning/phases/05-ml-ensemble-upgrade-gated/05-02-SUMMARY.md
- Commits verified: c84b693 (RED), 7bd25d1 (Task 1 GREEN), ce97715 (Task 2 GREEN)
- Tests: 12 passed (ml_validation) + 15 passed (ml_features + baselines, no regressions); ruff clean on new files.

## TDD Gate Compliance

- RED gate: `test(05-02)` commit `c84b693` (failing wrapper + harness contract tests; `ModuleNotFoundError`/`ImportError` confirmed before implementation).
- GREEN gate: `feat(05-02)` commits `7bd25d1` (Task 1) and `ce97715` (Task 2) after RED.
- No unexpected pass during RED (target modules did not exist).

---
*Phase: 05-ml-ensemble-upgrade-gated*
*Completed: 2026-06-16*
