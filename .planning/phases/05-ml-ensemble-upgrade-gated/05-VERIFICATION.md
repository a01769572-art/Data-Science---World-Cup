---
phase: 05-ml-ensemble-upgrade-gated
verified: 2026-06-15T00:00:00Z
status: gaps_found
score: 2/4 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Gate pre-registrado: el ensemble solo reemplaza al baseline si lo vence en log-loss en los 4 holdouts; resultado negativo documentado, baseline sigue publicando."
    status: partial
    reason: >
      The gate function itself (evaluate_ml_gate) is correct, pure, and the
      negative-result/dual-publication path is sound. BUT the holdout log-losses
      that feed the gate for the ml and ensemble candidates are computed on
      miscalibrated probabilities (CR-01, confirmed by direct reading of
      ml_validation.py:393-435). Calibrators and the ensemble weight are tuned on
      inner_model (fit on ~75% of pre-cutoff rows) yet applied to final_model
      (re-fit on ALL pre-cutoff rows) at holdout scoring time. The two models emit
      differently-distributed probabilities, so the per-class isotonic/sigmoid maps
      are invalid for the serving distribution. The promotion verdict — the phase's
      headline deliverable — is therefore decided on systematically biased inputs.
      The baseline candidate is unaffected (uses no calibrator), so the comparison
      is asymmetric and not honest.
    artifacts:
      - path: "src/cdd_mundial/models/ml_validation.py"
        issue: >
          run_ml_comparison lines 393-435: ml_calibrator/weight/ens_calibrator fit
          against inner_model.predict_proba outputs (ml_fit_raw/ml_cal_raw); holdout
          scored with final_model.predict_proba then transformed by those same
          calibrators. Train-serve distribution mismatch.
    missing:
      - "Score the holdout with the SAME model whose outputs the calibrators/weight were fit on (score with inner_model, dropping the final-model re-fit), OR re-derive calibrators/weight from final_model's own held-out predictions before scoring."
      - "Add a test asserting the model that produces *_fit_raw/*_cal_raw is the model that produces the holdout probabilities the calibrators transform (guards against silent regression of CR-01)."
  - truth: "Calibracion isotonica vs Platt comparada empiricamente en folds temporales y elegida por evidencia."
    status: partial
    reason: >
      The empirical isotonic-vs-Platt-vs-none selection machinery
      (select_best_calibration, MulticlassCalibrator) is correctly implemented,
      structurally leakage-free (fit only on the pre-cutoff inner slice;
      calibration_max_date < cutoff is tested), and the choice is recorded per
      holdout. However, the calibrator chosen by select_best_calibration is selected
      against inner_model's probability distribution but then applied to final_model's
      outputs at scoring time (same CR-01 root cause). The empirical choice between
      isotonic and Platt is thus made on the wrong distribution, so 'chosen by
      evidence' is undermined: the evidence describes inner_model, the production-scored
      probabilities come from final_model.
    artifacts:
      - path: "src/cdd_mundial/models/ml_validation.py"
        issue: "ml_choice/ens_choice (lines 403, 416) computed from inner_model outputs; applied to final_model outputs at lines 430, 433-435."
      - path: "src/cdd_mundial/models/ml_calibration.py"
        issue: "WR-04 (cosmetic): identical if/else isotonic/sigmoid branch at lines 150-153 — dead code, not a correctness defect. WR-06: depends on sklearn private _SigmoidCalibration."
    missing:
      - "Resolve the train-serve model mismatch (shared with criterion #3) so the empirical isotonic-vs-Platt comparison reflects the distribution actually scored at the holdout."
deferred: []
---

# Phase 5: ML + Ensemble (upgrade gated) Verification Report

**Phase Goal:** Un ensemble ML calibrado mejora medible y honestamente al baseline — o el resultado negativo queda documentado como hallazgo; el baseline sigue publicando en paralelo en todo momento.
**Verified:** 2026-06-15
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Matriz de features point-in-time sin leakage temporal (shift(1) discipline); FIFA-ranking point-in-time omitido y documentado | ✓ VERIFIED | `ml_features.py` builds 12 frozen features (D-02); coverage metadata read BEFORE state update; `_TeamState.update` called AFTER features read (lines 207-278), so no look-ahead. Ties broken by `match_id` (line 193). FIFA ranking feature deliberately absent from `ML_FEATURE_COLUMNS`; omission documented in D-08/D-09 (05-CONTEXT.md) and feature list. DC features via injected cutoff-correct `dc_predict`. |
| 2 | Clasificador XGBoost 3 clases (constrained depth<=3-4, ~<=10 features) con la misma validacion temporal que el baseline | ✓ VERIFIED | `MulticlassXGBoost` (`ml_xgboost.py`): `multi:softprob`, `num_class=3`, `max_depth=3`, deterministic (`tree_method="exact"`, `nthread=1`, pinned seed). `run_ml_validation` reuses baseline `HOLDOUTS` + `log_loss`/`brier`/`rps` verbatim (imported from `validation.py`), fit-at-cutoff, hard D-04 exclusion. 12 features (slightly above ~10 but includes 5 structural DC pass-throughs; within "constrained" intent). Tests pass. |
| 3 | Gate pre-registrado: ensemble vence baseline en log-loss en los 4 holdouts; resultado negativo documentado; baseline sigue publicando | ✗ FAILED (partial) | Gate function `evaluate_ml_gate` is pure and correct; dual-publication + explicit fallback (`ml_selection.py`, `pipeline.py`) preserve baseline unconditionally with per-row provenance (D-13/D-14). BUT the ml/ensemble holdout log-losses feeding the gate are MISCALIBRATED — CR-01 confirmed: calibrators/weight fit on `inner_model`, applied to `final_model` at scoring (`ml_validation.py:393-435`). Gate verdict computed on biased inputs. |
| 4 | Calibracion isotonica vs Platt comparada empiricamente en folds temporales y elegida por evidencia | ✗ FAILED (partial) | `select_best_calibration` compares none/sigmoid/isotonic by held-out log-loss, leakage-free by construction, choice recorded per holdout. BUT selection is made on `inner_model`'s distribution while production scoring uses `final_model`'s (same CR-01 root cause), so the "evidence" describes a different distribution than the one scored. |

**Score:** 2/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/cdd_mundial/models/ml_features.py` | Point-in-time 12-feature builder, eligibility metadata | ✓ VERIFIED | Substantive (281 lines), wired (imported by `ml_validation.py`), data-flowing. Anti-leakage discipline correct. |
| `src/cdd_mundial/models/ml_xgboost.py` | Conservative deterministic XGBoost wrapper | ✓ VERIFIED | Substantive, shallow/seeded, wired into both harnesses. |
| `src/cdd_mundial/models/ml_validation.py` | ML harness + 3-candidate comparison + gate | ⚠️ DEFECTIVE | Exists, substantive, wired, runs — but `run_ml_comparison` carries the CR-01 train-serve calibration mismatch that corrupts gate inputs. Gate purity (`evaluate_ml_gate`) is itself correct. |
| `src/cdd_mundial/models/ml_calibration.py` | Multiclass isotonic/Platt/none calibrator + empirical selection | ✓ VERIFIED (with WR-04 cosmetic) | Substantive, wired. Dead identical if/else branch (WR-04) is cosmetic. Uses sklearn private `_SigmoidCalibration` (WR-06, fragility). |
| `src/cdd_mundial/live/ml_selection.py` | Per-match baseline/upgrade/fallback decision | ✓ VERIFIED | Substantive, wired into `pipeline.py`, full provenance. `winner` param unused (WR-03, cosmetic). |
| `src/cdd_mundial/live/pipeline.py` | Opt-in dual publication integration | ✓ VERIFIED | `ml_selection_provider` seam wired (lines 301, 370-372, 482); baseline path unchanged when absent. |
| `src/cdd_mundial/live/report.py` | Visible upgrade / no-promotion section | ✓ VERIFIED | `_selection_view` + `#model-selection` rendering present (lines 226, 455-506). |
| `notebooks/05_ml_ensemble.ipynb` | Executed didactic evidence | ✓ VERIFIED | 19 cells, 6 code cells all with non-empty outputs. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `ml_validation.py` | `validation.py` | Reuse of HOLDOUTS + metric family | ✓ WIRED | `from ...validation import HOLDOUTS, Holdout`; `log_loss`/`brier`/`rps` shared. |
| `ml_features.py` | `loading.py` | Canonical 3-way target | ✓ WIRED | `load_matches` imported; `target_outcome_idx` from `row.outcome_idx`. |
| `ml_features.py` | `dixon_coles.py` | Structural DC features | ✓ WIRED | `predict_lambdas`, `wdl_from_lambdas` imported and used. |
| `ml_selection.py` | `pipeline.py` | Per-match selection + fallback | ✓ WIRED | `build_dual_publication` imported and called in `run_official`. |
| calibrators (fit) | holdout scoring (serve) | Same model produces fit-raw and serve-raw probs | ✗ NOT_WIRED | CR-01: calibrators fit on `inner_model`, applied to `final_model`. The two are different models on different data. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| ML test suites pass | `pytest tests/test_ml_validation.py test_ml_calibration.py test_ml_features.py test_ml_selection.py` | 46 passed in 12.77s | ✓ PASS |
| Env healthy (pandas/numpy/xgboost/sklearn) | `python -c "import ..."` | xgboost 3.2.0, sklearn 1.9.0 | ✓ PASS |
| Notebook executed with outputs | inspect `.ipynb` | 6/6 code cells have outputs | ✓ PASS |
| Tests catch CR-01 | grep test_ml_validation.py | No test asserts train==serve model for calibrators | ✗ FAIL (gap is silent) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ML-01 | 05-01 | Pipeline de features point-in-time | ✓ SATISFIED | `ml_features.py` leakage-free 12-feature builder; FIFA-ranking omission documented (D-08/D-09). |
| ML-02 | 05-02 | XGBoost 3-clases con validacion temporal del baseline | ✓ SATISFIED | `ml_xgboost.py` + `run_ml_validation` reusing baseline holdouts/metrics. |
| ML-03 | 05-02, 05-03, 05-04 | Ensemble + gate pre-registrado + dual publication | ✗ BLOCKED | Gate logic and dual-publication correct, but gate INPUTS are miscalibrated (CR-01). Promotion decision not trustworthy. |
| ML-04 | 05-03 | Calibracion isotonic vs Platt empirica en folds temporales | ✗ BLOCKED | Selection machinery correct but evidence computed on `inner_model` distribution, applied to `final_model` (CR-01). |

All four declared requirement IDs (ML-01..ML-04) are accounted for across the plans. No orphaned requirements: REQUIREMENTS.md maps ML-01..ML-04 to Phase 5 and all four are claimed in plan frontmatter. (REQUIREMENTS.md currently marks all four `[x] Complete` — that status is premature given CR-01; the gate/calibration deliverables ML-03/ML-04 are not honestly satisfied yet.)

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `ml_validation.py` | 393-435 | Train-serve model mismatch for calibrators/weight (CR-01) | 🛑 Blocker | Corrupts the gate (criterion #3) and calibration-evidence (criterion #4) — the phase's core deliverable. |
| `ml_validation.py` | 305-308 | `_ensemble_probs` divides by row sum with no positive-floor guard (WR-02) | ⚠️ Warning | `inf`/`nan` risk into `log_loss` under degenerate blends; `ml_selection._normalize_triplet` guards, this does not. |
| `ml_features.py` | 228-231 | `elo_diff` all-NaN if `elo_history` absent for a fold (WR-01) | ⚠️ Warning | A contract feature can be silently all-missing; gate then judges a crippled candidate. No per-fold NaN audit. |
| `ml_calibration.py` | 150-153 | Identical isotonic/sigmoid if/else branch (WR-04) | ℹ️ Info | Dead code; misleads maintainers. No behavioral effect. |
| `ml_calibration.py` | 37, 130 | sklearn private `_SigmoidCalibration` (WR-06) | ⚠️ Warning | Platt path can break on a 1.9.x patch upgrade; no smoke test pins it. |
| `ml_selection.py` | 91-123 | `decide_publication(winner=...)` unused (WR-03) | ℹ️ Info | Misleading inert parameter. |
| `ml_features.py` | 79, 246 | `_DEFAULT_RHO=0.0` baseline candidate != production DC rho (IN-02) | ℹ️ Info | Gate baseline is a rho=0 approximation of production DC; compounds the "honest comparison" concern but is documented. |

### Human Verification Required

None required for the gap determination. The blocking defect (CR-01) is observable in code and decisive on its own; the phase cannot be marked passed regardless of any human-only checks.

### Gaps Summary

The phase delivered nearly all of its scaffolding correctly: a leakage-free point-in-time feature table (criterion #1, VERIFIED), a conservative temporally-validated XGBoost classifier (criterion #2, VERIFIED), a pure and correct promotion-gate function, an empirical calibration-selection machinery, and a sound dual-publication / explicit-baseline-fallback live path that never displaces the baseline.

The phase goal, however, is not "build a gate" — it is for "un ensemble ML calibrado [to] mejora medible y HONESTAMENTE al baseline, o [for] el resultado negativo [to] quede documentado como hallazgo." That honesty hinges on the holdout log-losses being correct. CR-01 (confirmed by direct reading of `ml_validation.py:393-435`, unaddressed since the review per git log) breaks exactly that: the ML and ensemble candidates are scored through calibrators and an ensemble weight tuned on a *different* model's (`inner_model`'s) output distribution than the one actually scored (`final_model`'s). The baseline candidate, using no calibrator, is scored correctly. The gate therefore pits a correctly-scored baseline against systematically miscalibrated challengers — the comparison is not honest, and the empirical isotonic-vs-Platt choice (criterion #4) is made on the wrong distribution. Both criteria #3 and #4 are PARTIAL/FAILED for the same root cause.

This is a methodological-rigor project where a miscalibrated gate undermines the headline deliverable, so it is a BLOCKER, not a warning. The fix is mechanical (score the holdout with the model the calibrators were fit on, or re-derive calibrators from the final model) and the existing tests pass only because they assert distribution validity and anti-leakage, never train-serve consistency — so a regression guard test should accompany the fix.

The live integration, feature pipeline, and classifier are solid and should not need rework; the gap is localized to `run_ml_comparison`.

---

_Verified: 2026-06-15_
_Verifier: Claude (gsd-verifier)_
