---
phase: 02-modelos-baseline
plan: 04
subsystem: models
tags: [temporal-validation, holdouts, dixon-coles, log-loss, brier, rps, provenance]

requires:
  - phase: 02-modelos-baseline
    plan: 02
    provides: Elo history and solo-Elo baseline
  - phase: 02-modelos-baseline
    plan: 03
    provides: Dixon-Coles fit, W/D/L conversion, and production model contract
provides:
  - Strict fit-at-cutoff validation over WC2018, WC2022, Euro2024, and Copa America 2024
  - Mini-grid selection of xi and persisted D-13 comparison against uniform and solo-Elo
  - Production dc_params artifact activating predict_lambdas for Phase 3
  - Holdout-level predictions for reliability analysis in Plan 02-05
affects: [02-05 notebook, 03 simulator, 05 ml]

tech-stack:
  added: []
  patterns: [fit-at-cutoff validation, exact holdout count gates, dated generated artifacts, stable provenance manifests]

key-files:
  created:
    - src/cdd_mundial/models/validation.py
    - tests/test_validation_temporal.py
    - data/metadata/dc_params.provenance.json
    - data/metadata/holdout_predictions.provenance.json
  modified:
    - src/cdd_mundial/data/contracts.py
    - src/cdd_mundial/models/dixon_coles.py
    - tests/test_dixon_coles.py

key-decisions:
  - "xi=0.00095 selected by mean log-loss across the four temporal holdouts"
  - "D-13 passed: Dixon-Coles mean log-loss 0.9672 beats solo-Elo 0.9830 and uniform 1.0986"
  - "L-BFGS-B starts gamma at zero and uses explicit line-search/iteration tolerances to avoid a degenerate sparse-window basin"

requirements-completed: [MODEL-02, MODEL-04]

duration: 25min
completed: 2026-06-12
---

# Phase 2 Plan 04: Temporal Validation and Production Model Summary

**Strict four-tournament temporal validation selected `xi=0.00095`, passed gate D-13, persisted 633 holdout prediction rows, and materialized the production Dixon-Coles model used by `predict_lambdas`.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-12T15:13:32Z
- **Completed:** 2026-06-12T15:38:28Z
- **Tasks:** 2
- **Files modified:** 7 tracked files plus 3 gitignored generated model artifacts

## Accomplishments

- Enforced exact holdout counts of 64/64/51/32 and strict `date < cutoff` training boundaries.
- Evaluated `xi` values 0.00095 and 0.0018 independently across all four holdouts.
- Persisted log-loss, multiclass Brier, and RPS for Dixon-Coles, uniform, and solo-Elo.
- Passed D-13 with mean log-loss: Dixon-Coles 0.967184, solo-Elo 0.983017, uniform 1.098612.
- Materialized `dc_params_2026-06-12.json`, `validation_report_2026-06-12.json`, and `holdout_predictions_2026-06-12.parquet`.
- Activated the frozen production contract: Argentina vs Mexico returns positive lambdas `(1.5131, 0.4721)`.

## Task Commits

1. **Tasks 1-2: validation harness, production materialization, provenance, and optimizer robustness** - `40d5b7b`

## Deviations from Plan

### [Rule 1 - Bug] Sparse recent-window Dixon-Coles fit entered a degenerate optimizer basin

- **Found during:** Task 2 real materialization
- **Issue:** Copa America 2024 with `xi=0.0018` drove the original `gamma=0.1` initialization to extreme `c/gamma` values and an abnormal L-BFGS-B termination.
- **Fix:** Start `gamma` at zero and configure bounded line-search effort and convergence tolerances; added a real-data regression test for the failing cutoff.
- **Verification:** All eight holdout fits and the production fit complete; 25 focused tests pass.
- **Commit:** `40d5b7b`

**Total deviations:** 1 auto-fixed bug. **Impact:** Fit behavior is more robust without changing the model contract or selected hyperparameter.

## Verification Results

- `python -m pytest tests/test_validation_temporal.py tests/test_dixon_coles.py -q` -> 25 passed
- `python -m ruff check ...` -> all checks passed
- `python -m cdd_mundial.models.validation --verify-only` -> gate passed, 633 prediction rows
- `predict_lambdas("argentina", "mexico", ...)` -> two positive finite lambdas

## Issues Encountered

None unresolved.

## Next Phase Readiness

- Plan 02-05 can read the validation report and holdout predictions without refitting.
- Phase 3 can consume the production `predict_lambdas` contract immediately.

## Self-Check: PASSED

All tracked files and provenance manifests exist, generated artifacts verify, and commit `40d5b7b` is present.
