# Phase 05: ML + Ensemble (upgrade gated) - Research

**Date:** 2026-06-15
**Question:** What do we need to know to plan Phase 5 well?

## Executive Summary

Phase 5 should reuse the existing baseline discipline instead of creating a parallel ML stack. The safest architecture is:

1. Build one point-in-time supervised dataset from the same canonical historical/live path already used by Phase 4.
2. Train a small multiclass XGBoost classifier on that dataset under the exact same four holdouts used by `src/cdd_mundial/models/validation.py`.
3. Evaluate three candidates on every holdout: baseline, ML solo, ensemble.
4. Calibrate ML solo and ensemble inside temporal folds only, then apply one explicit promotion gate.
5. If the gate passes, integrate the winner as a dual-publication candidate in the live pipeline without removing the baseline path.

The main planning risk is not model choice. It is temporal leakage. Every plan should preserve the Phase 2 and Phase 4 invariant that features, labels, and artifacts are all reconstructible from information available strictly before kickoff.

## Codebase Facts That Matter

### Existing reusable assets

- `src/cdd_mundial/models/loading.py` already defines the canonical 3-way target (`outcome_idx`) with 90-minute semantics.
- `src/cdd_mundial/models/validation.py` already defines the four holdouts, the fit-at-cutoff pattern, the metric set (`log_loss`, `brier`, `rps`), and the artifact materialization pattern.
- `src/cdd_mundial/models/dixon_coles.py` already exposes production `predict_lambdas(...)` plus `wdl_from_lambdas(...)`.
- `src/cdd_mundial/live/materialization.py` already proves how to fold live rows into a dated, immutable point-in-time artifact without mutating history.
- `src/cdd_mundial/live/pipeline.py` already has a canonical publication path, snapshot metadata, model provenance, and calibration ledger integration.

### Constraints implied by the current repo

- `pyproject.toml` includes `scikit-learn` but not `xgboost`. Phase 5 must add the dependency explicitly.
- Phase 4 already uses `model_version` and append-only snapshot semantics. Phase 5 cannot improvise a new metadata style.
- The baseline notebook closes by stating that Phase 5 will reuse `elo_history.parquet`, holdout predictions, and Dixon-Coles rates under the same temporal protocol.

## Recommended Architecture

### 1. Dataset builder first, model second

Do not start with model code. Start with a deterministic builder that emits one row per match with:

- join keys: `match_id`, `date`, `home_team_id`, `away_team_id`, `tournament`
- target: `outcome_idx`
- coverage metadata: at minimum `has_min_history_home`, `has_min_history_away`, and a boolean that marks whether the row is ML-eligible under D-04
- the fixed 12-feature matrix from `05-CONTEXT.md`

This builder should accept either:

- the canonical historical parquet alone for backtests, or
- a dated live-training frame for the production/live path

That mirrors the design already used in `load_matches(...)` and `materialize_live_training(...)`.

### 2. Keep feature provenance explicit

Recommended feature groups:

- structural baseline features:
  - `lambda_home_dc`
  - `lambda_away_dc`
  - `p_home_win_dc`
  - `p_draw_dc`
  - `p_away_win_dc`
- raw point-in-time features:
  - `elo_diff`
  - `is_host_home`
  - `days_rest_diff`
  - `form_points_diff_last_5`
  - `goal_diff_per_match_diff_last_5`
  - `goals_for_per_match_diff_last_5`
  - `goals_against_per_match_diff_last_5`

The builder should compute raw rolling features from prior matches only. No centered windows, no tournament-level aggregates that peek ahead, and no backfilled FIFA ranking placeholder if the source does not exist.

### 3. D-04 must be hard, not advisory

If either team has fewer than 5 prior matches:

- the row should remain in the master dataset for auditability,
- but it should be marked ineligible for ML training and ML inference,
- and production prediction should fall back to the baseline explicitly.

This preserves coverage transparency without contaminating the supervised problem with ad hoc imputation.

### 4. Train XGBoost conservatively

The repo wants a small-data, auditable first model. Recommended first-pass constraints:

- `objective="multi:softprob"`
- `num_class=3`
- shallow trees (`max_depth` 3 or 4)
- low feature count fixed by context
- modest boosting rounds with early stopping on temporal validation
- deterministic seed handling

Do not add broad hyperparameter search. The hard question is whether ML adds signal beyond the structural baseline, not whether a large search can overfit four holdouts.

### 5. Treat calibration as part of model selection

The context decision is clear: calibrate ML solo and ensemble separately inside temporal validation.

Recommended comparison:

- uncalibrated ML solo
- ML solo + sigmoid/Platt
- ML solo + isotonic
- uncalibrated ensemble
- ensemble + sigmoid/Platt
- ensemble + isotonic

Pick the best calibrated version per candidate using holdout evidence only. Do not fit a calibrator once on all holdouts combined and then report that result retroactively.

### 6. Ensemble design should stay simple

A weighted convex blend of probability vectors is enough for v1:

`p_ensemble = w * p_ml + (1 - w) * p_baseline`

Recommended search:

- fixed small grid over `w`, for example `0.1` to `0.9`
- choose `w` inside temporal validation only

That is easier to audit than a stacked meta-learner and aligns with the “upgrade gated” framing.

### 7. Promotion gate must be registered in code

The gate should be encoded as a pure function, parallel to `evaluate_gate(...)` in `src/cdd_mundial/models/validation.py`.

Recommended semantics:

- input: per-holdout metrics for baseline, ML solo, ensemble
- pass only if the promoted candidate beats baseline in `log_loss` on all four holdouts
- include tie/no-pass handling that records a negative result explicitly

The likely outcome may be “baseline keeps winning”. The phase should still succeed if that negative result is well documented and production remains stable.

## File/Module Recommendations

### New modules

- `src/cdd_mundial/models/ml_features.py`
  - deterministic point-in-time feature builder
- `src/cdd_mundial/models/ml_baseline.py` or `ml_xgboost.py`
  - model fitting and prediction for XGBoost
- `src/cdd_mundial/models/ml_calibration.py`
  - sigmoid/isotonic wrappers for multiclass probabilities
- `src/cdd_mundial/models/ml_validation.py`
  - temporal holdout orchestration, candidate comparison, promotion gate, artifact writes
- `src/cdd_mundial/live/ml_selection.py` or equivalent
  - production-time fallback and winner-selection logic for live publication

### Expected tests

- `tests/test_ml_features.py`
- `tests/test_ml_validation.py`
- `tests/test_ml_calibration.py`
- updates to `tests/test_live_pipeline.py`
- updates to notebook tests if a Phase 5 notebook is added

## Risks And Mitigations

### Risk 1: temporal leakage through rolling features

Mitigation:

- compute every feature from matches with `date < kickoff`
- add tests that assert strict cutoffs, similar to `test_training_cut_is_strict_for_every_holdout`

### Risk 2: hidden fallback behavior in production

Mitigation:

- encode fallback to baseline explicitly in one production function
- record whether a published match used `baseline`, `ml`, or `ensemble`

### Risk 3: overfitting via hyperparameter sprawl

Mitigation:

- keep the first model small and search space narrow
- prefer simple, explainable gates over leaderboard-style tuning

### Risk 4: calibration trained on the wrong slice

Mitigation:

- fit calibrators only on training/validation data before the holdout being scored
- artifact metadata should state which calibrator won per candidate

### Risk 5: unclear negative result handling

Mitigation:

- make “no promotion” a first-class successful state
- write a report artifact that explains why the baseline stayed live

## Open Research Result: FIFA ranking feature

Conclusion: treat historical FIFA ranking as optional and non-blocking.

Rationale:

- the context already resolves this as D-08/D-09,
- there is no in-repo source yet,
- inventing a proxy under the same column name would blur provenance.

So the plan should branch cleanly:

- if a reproducible point-in-time source is found quickly, add it behind a contract,
- otherwise omit it and document the omission in the validation report and notebook.

## Planning Implications

Phase 5 should be split into four executable plans:

1. Freeze point-in-time ML dataset construction and tests.
2. Implement conservative XGBoost training under the existing temporal holdout harness.
3. Add calibrated ML/ensemble comparison plus the explicit promotion gate and artifacts.
4. Integrate the winner-or-fallback path into live dual publication without replacing baseline.

That ordering matches the real dependency chain: data contract -> model -> calibrated comparison -> production integration.

## Recommendation

Proceed with planning around the four-plan shape above. Do not spend a plan on broad feature ideation or large tuning loops. The project already has a strong baseline and a live publication path; Phase 5 only creates value if it preserves that rigor while making the upgrade decision auditable.
