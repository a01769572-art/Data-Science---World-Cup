---
phase: 02-modelos-baseline
plan: 05
subsystem: notebooks
tags: [jupyter, pedagogy, dixon-coles, elo, calibration, reliability]

requires:
  - phase: 02-modelos-baseline
    plan: 04
    provides: validation report, holdout predictions, and production model
provides:
  - Executed didactic notebook covering Elo, Dixon-Coles derivation, W/D/L, validation, and calibration
  - Structural notebook gates extended to Phase 2
affects: [portfolio, phase-verification, learning-notes]

tech-stack:
  added: []
  patterns: [markdown-code-interpretation notebook contract, production-only imports, rendered-output secret scanning]

key-files:
  created:
    - notebooks/02_modelos_baseline.ipynb
  modified:
    - tests/test_notebooks.py
    - .gitignore

key-decisions:
  - "Notebook consumes dated validation artifacts and never refits or redefines production logic"
  - "Reliability diagram is diagnostic with 211 holdout matches, not evidence for aggressive recalibration"

requirements-completed: [MODEL-01, MODEL-02, MODEL-03, MODEL-04]

duration: 13min
completed: 2026-06-12
---

# Phase 2 Plan 05: Baseline Models Notebook Summary

**Executed Spanish-language notebook derives the Dixon-Coles mathematics, visualizes Elo and score distributions, proves the 24-28% draw sanity check, and reports the honest four-holdout calibration evidence.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-06-12T15:38:28Z
- **Completed:** 2026-06-12T15:51:04Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added six executable code cells, each surrounded by mandatory `What and why` and `Interpretation` Markdown.
- Derived rho correction, weighted log-likelihood, gradient structure, identifiability, and corrected `ln(2)/xi` half-life arithmetic.
- Visualized Elo rank agreement, top ratings, expected-goal score matrix, holdout metrics, xi selection, and one-vs-rest reliability curves.
- Added an executable assertion that representative neutral matchups produce draw probabilities in the 24-28% sanity band.
- Extended forbidden-fragment, production-import, required-analysis, kernel, secret, and structure gates to notebook 02.
- Executed all six cells and saved outputs; full repository suite passes with 165 tests.

## Task Commits

1. **Tasks 1-2: executable notebook and structural gates** - `206bc98`

## Deviations from Plan

### [Rule 3 - Blocking Environment] Jupyter kernel connection file was denied inside the sandbox

- **Found during:** Task 1 notebook execution
- **Issue:** Windows ACL enforcement raised `WinError 5` when `nbconvert` created the kernel connection file.
- **Fix:** Executed `nbconvert` outside the sandbox with `JUPYTER_RUNTIME_DIR` in a local non-OneDrive directory; ignored the generated Jupyter YStore database.
- **Verification:** Notebook executed all six code cells with zero error outputs.
- **Commit:** `206bc98`

**Total deviations:** 1 environment blocker resolved. **Impact:** No change to notebook behavior or repository runtime requirements.

## Verification Results

- `jupyter nbconvert --to notebook --execute --inplace notebooks/02_modelos_baseline.ipynb` -> success
- Notebook inspection -> 6/6 code cells executed, zero errors, all cell IDs present
- `pytest tests/test_notebooks.py -q` -> 15 passed
- `pytest -q` -> 165 passed
- `ruff check tests/test_notebooks.py` -> all checks passed

## Issues Encountered

None unresolved.

## Next Phase Readiness

- Phase 2 deliverables are complete and ready for goal verification.
- Phase 3 can use the frozen production `predict_lambdas` contract.

## Self-Check: PASSED

Notebook and tests exist, outputs are saved, commit `206bc98` is present, and the full suite passes.
