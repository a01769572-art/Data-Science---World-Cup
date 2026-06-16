---
phase: 05-ml-ensemble-upgrade-gated
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - src/cdd_mundial/models/ml_features.py
  - src/cdd_mundial/models/ml_xgboost.py
  - src/cdd_mundial/models/ml_validation.py
  - src/cdd_mundial/models/ml_calibration.py
  - src/cdd_mundial/models/__init__.py
  - src/cdd_mundial/live/ml_selection.py
  - src/cdd_mundial/live/pipeline.py
  - src/cdd_mundial/live/report.py
  - src/cdd_mundial/live/__init__.py
  - scripts/build_notebook_05.py
  - templates/report_daily.html.jinja
  - pyproject.toml
  - tests/test_ml_features.py
  - tests/test_ml_validation.py
  - tests/test_ml_calibration.py
  - tests/test_ml_selection.py
  - tests/test_live_pipeline.py
findings:
  critical: 1
  warning: 6
  info: 6
  total: 13
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-06-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Phase 5 adds the gated ML/ensemble upgrade. The temporal-leakage discipline in
`ml_features.py` (strict `date < kickoff`, state updated only after reading
features, tie-break by `match_id`) is correct and well-encoded, and the live
dual-publication / fallback path (`ml_selection.py`, `pipeline.py`) preserves the
baseline unconditionally with per-row provenance as required (D-13/D-14). The
seeding/determinism story in `ml_xgboost.py` is sound for the configured
`tree_method="exact"` + `nthread=1`.

The blocking issue is a **calibrator train/serve model mismatch** in
`run_ml_comparison`: the calibrators and the ensemble weight are fit against the
*inner* model's probabilities but then applied to a *differently-trained* final
model's probabilities at holdout scoring time. This silently degrades the very
log-loss numbers the promotion gate consumes, so the gate verdict — the central
deliverable of the phase — is computed on miscalibrated inputs. Several warnings
concern robustness (NaN-producing features fed to XGBoost, non-positive ensemble
denominators, an unused `winner` parameter) and one dead/duplicated code path.

## Critical Issues

### CR-01: Calibrators and ensemble weight are fit on the inner model but applied to a different final model

**File:** `src/cdd_mundial/models/ml_validation.py:393-435`
**Issue:**
Inside each holdout, `run_ml_comparison` fits `ml_calibrator` and selects the
ensemble `weight` and `ens_calibrator` against the predictions of `inner_model`
(trained only on `inner_fit`, ~75% of pre-cutoff rows):

```python
inner_model = MulticlassXGBoost(seed=seed).fit(x_fit, y_fit)   # inner_fit only
...
ml_calibrator = MulticlassCalibrator(method=ml_choice["method"]).fit(ml_fit_raw, y_fit)
weight = _select_weight(ml_cal_calibrated, baseline_cal, y_cal)
ens_calibrator = MulticlassCalibrator(method=ens_choice["method"]).fit(ens_fit_raw, y_fit)
```

Then at step 4 it re-fits a **different** model on *all* pre-cutoff rows and
applies those same calibrators to its outputs:

```python
final_model = MulticlassXGBoost(seed=seed).fit(x_train, y_train)   # all pre-cutoff
ml_holdout = ml_calibrator.transform(final_model.predict_proba(x_holdout))
ensemble_holdout = ens_calibrator.transform(_ensemble_probs(ml_holdout, baseline_holdout, weight))
```

`inner_model` and `final_model` are trained on different data and therefore emit
differently-distributed probabilities. A per-class isotonic/sigmoid map learned
on `inner_model`'s output distribution is not valid for `final_model`'s output
distribution; the calibrated holdout probabilities are systematically off. Because
these holdout log-losses are exactly what `evaluate_ml_gate` compares against the
baseline, the promotion decision — the phase's headline artifact — is made on
miscalibrated numbers. This is a correctness defect in the gate, not a style issue.

Note this is *not* a leakage bug (nothing peeks past the cutoff); the anti-leakage
invariants T-05-07 hold. The defect is that the calibrator's training distribution
(inner model) and serving distribution (final model) differ.

**Fix:** Apply each calibrator to the same model whose outputs it was fit on. The
simplest correct option is to score the holdout with `inner_model` (the one the
calibrators/weight were tuned for) and drop the re-fit, or — if the extra 25% of
data is wanted — re-derive the calibrators/weight from `final_model`'s own
predictions on a held-out slice before scoring. For example, score with the inner
model:

```python
# Score the holdout with the SAME model the calibrators/weight were fit on.
ml_holdout_raw = inner_model.predict_proba(x_holdout)
ml_holdout = ml_calibrator.transform(ml_holdout_raw)
ensemble_holdout = ens_calibrator.transform(
    _ensemble_probs(ml_holdout, baseline_holdout, weight)
)
```

Whichever path is chosen, the model that produces `*_fit_raw`/`*_cal_raw` must be
the model that produces the holdout probabilities the calibrators transform.

## Warnings

### WR-01: NaN-valued features (`days_rest_diff`, `elo_diff`) are passed straight into XGBoost training/scoring

**File:** `src/cdd_mundial/models/ml_features.py:130-134, 223-231` and `ml_validation.py:172-177`
**Issue:**
`_days_rest` returns `float("nan")` when a team has no prior match, and `elo_diff`
is NaN whenever `elo_history` is absent or a `(match_id, team_id)` key is missing
(`elo_by_key.get(..., float("nan"))`). These columns flow unchanged into
`x_train = train[list(_FEATURES)].to_numpy(dtype=float)` and into
`MulticlassXGBoost.fit`. XGBoost tolerates NaN as "missing", but: (a) a fold where
`elo_history` was never injected trains every tree's `elo_diff` split on *all*
NaN, silently neutering a feature the contract claims is present; (b) `days_rest`
NaN only occurs for a team's first-ever match, which is excluded by the
`MIN_PRIOR_MATCHES>=5` eligibility filter, so that case is benign — but the
`elo_diff` all-NaN case is not. The model can be trained on a feature matrix with
an entirely-missing column with no warning, and the gate then judges that
crippled candidate against the baseline.
**Fix:** Either assert in `run_ml_comparison`/`run_ml_validation` that the eligible
training slice has no all-NaN feature column (fail loudly), or document and test
that `elo_diff` is intentionally NaN-as-missing and ensure the production live path
always injects `elo_history`. At minimum log/record per-fold NaN coverage so a
silently-dead feature is auditable.

### WR-02: `_ensemble_probs` can divide by a non-positive row sum

**File:** `src/cdd_mundial/models/ml_validation.py:305-308`
**Issue:**
```python
blended = weight * ml_probs + (1.0 - weight) * baseline_probs
return blended / blended.sum(axis=1, keepdims=True)
```
There is no guard that `blended.sum(axis=1)` is strictly positive. If a calibrated
ML row and a baseline row are both ~0 in some column and the blend underflows, or
if upstream calibration emitted a zero row (the `_renormalize` fallback can yield a
uniform row, which is fine, but `method="none"` does a raw divide with no floor),
a zero or near-zero denominator produces `inf`/`nan` probabilities that then feed
`log_loss`. Compare with `ml_selection._normalize_triplet`, which *does* guard
(`if total <= 0.0: raise`). The ensemble blend should be at least as defensive.
**Fix:** Floor the denominator or validate it, e.g.
`denom = blended.sum(axis=1, keepdims=True); denom = np.where(denom <= _EPS, 1.0, denom)`
and reset all-zero rows to uniform, mirroring `ml_calibration._renormalize`.

### WR-03: `decide_publication` accepts a `winner` argument it never uses

**File:** `src/cdd_mundial/live/ml_selection.py:91-123`
**Issue:**
`decide_publication(..., winner: str, ...)` takes `winner` but the body never
references it; the decision is driven entirely by `gate_promoted`, `ml_eligible`,
`has_ml_prob`. Callers (`build_dual_publication:188`) pass it, and the tests pass
it, but it is dead in the function. This is misleading: a reader assumes the winning
family (`ml` vs `ensemble`) influences the per-match decision, and a future change
that *should* branch on `winner` (e.g. publishing the ml-vs-ensemble family label
on the upgrade row) has a parameter that looks wired but is inert. The upgrade row
in `build_dual_publication:225` hardcodes `UPGRADE_FAMILY` rather than `winner`, so
the promoted family identity is never stamped on the row beyond the separate
`winner` column.
**Fix:** Either drop the unused parameter from `decide_publication`, or actually use
it — e.g. stamp the promoted candidate family (`winner`) onto the upgrade row's
`model_family` so a reviewer can distinguish an `ml` upgrade from an `ensemble`
upgrade at the row level.

### WR-04: `MulticlassCalibrator.transform` has a dead, duplicated isotonic/sigmoid branch

**File:** `src/cdd_mundial/models/ml_calibration.py:147-154`
**Issue:**
```python
for cls, calibrator in enumerate(self._per_class):
    column = arr[:, cls]
    if self.method == "isotonic":
        calibrated[:, cls] = calibrator.predict(column)
    else:
        calibrated[:, cls] = calibrator.predict(column)
```
Both branches are identical (`calibrator.predict(column)`). The `if/else` is dead
code that implies a behavioral difference between isotonic and sigmoid transforms
that does not exist. It will confuse a future maintainer into thinking the two
paths must diverge.
**Fix:** Collapse to a single line:
`calibrated[:, cls] = calibrator.predict(column)`.

### WR-05: `_split_inner` can hand the model a 1-row inner-fit slice on small folds

**File:** `src/cdd_mundial/models/ml_validation.py:311-324`
**Issue:**
`n_cal = min(n_cal, n - 1)` guarantees at least one *fitting* row, but the fitting
slice can shrink to a single row (or to a slice missing one of the three classes).
`MulticlassXGBoost.fit` then raises the hard "requires exactly the canonical 3
classes" error (`ml_xgboost.py:122`), turning a small-but-valid fold into a crash
rather than a graceful skip. On the real ~5k dataset the early holdout (`wc2018`)
has the fewest pre-cutoff rows; an unlucky 75/25 split that drops a class from
`inner_fit` aborts the entire comparison run.
**Fix:** Validate after `_split_inner` that `inner_fit` contains all three classes
(and a minimum row count), and raise a clear, holdout-named error or fall back to a
larger fit fraction, rather than surfacing the generic class-count error from deep
inside the model wrapper.

### WR-06: Use of scikit-learn private API `_SigmoidCalibration` is fragility risk

**File:** `src/cdd_mundial/models/ml_calibration.py:37, 130`
**Issue:**
`from sklearn.calibration import _SigmoidCalibration` imports a leading-underscore
private symbol. The project pins `scikit-learn~=1.9` (pyproject), which allows
1.9.x patch upgrades; private internals carry no API-stability guarantee and can be
renamed/removed in a minor release, breaking the sigmoid calibration path with an
`ImportError` at runtime. The module docstring even acknowledges this is "internal."
For a system meant to keep publishing forecasts through July 2026, a silent
dependency drift here disables Platt calibration entirely.
**Fix:** Pin sklearn more tightly (e.g. `==1.9.*` exact) and add a smoke test that
imports `_SigmoidCalibration`, or replace it with a self-contained Platt fit
(`LogisticRegression` on the single calibrated column) so no private symbol is
depended upon.

## Info

### IN-01: `_select_ml_holdout` is recomputed 2-3x per holdout

**File:** `src/cdd_mundial/models/ml_validation.py:378-381`
**Issue:** `run_ml_comparison` calls `_select_ml_holdout(frame, holdout)` once for
`holdout_eligible` and again inside the `n_holdout_excluded` computation, repeating
the filter+sort. Correctness is unaffected but it is wasteful and invites the two
copies to drift.
**Fix:** Compute `holdout_all = _select_ml_holdout(frame, holdout)` once and derive
both `holdout_eligible` and the excluded count from it.

### IN-02: `_DEFAULT_RHO = 0.0` for the DC WDL features may not match the fitted model's rho

**File:** `src/cdd_mundial/models/ml_features.py:79, 246`
**Issue:** The point-in-time DC probabilities baked into the feature matrix (and
reused as the *baseline candidate* in the comparison) are computed with a hardcoded
`rho=0.0`, which drops the Dixon-Coles low-score correction. The docstring admits
this is a "small, stable value," but it means the baseline candidate's WDL vector is
not the production DC model's actual output. The gate then compares ML/ensemble
against a slightly-wrong baseline.
**Fix:** Thread the fitted model's `rho` through `dc_predict`/`dc_rho` in the live
and backtest paths, or document explicitly that the feature-surface baseline is a
rho=0 approximation and is intentionally distinct from the production DC line.

### IN-03: `_evolution_series` plots a non-contiguous `order` axis when snapshots are skipped

**File:** `src/cdd_mundial/live/report.py:195-210`
**Issue:** `order` is assigned by `enumerate(snapshot_ids)` before the
`cumulative["n_matches"] == 0` skip, so any snapshot with no resolved matches leaves
a gap in the `order` sequence used as the x-axis in `_evolution_plot`. The plot's x
positions then jump (e.g. 1, 3, 4), which is misleading for "Snapshot (orden)".
**Fix:** Assign `order` after filtering, or use a contiguous index over the emitted
rows.

### IN-04: Notebook `dc_predict` lambda ignores neutral/host context

**File:** `scripts/build_notebook_05.py:108-111`
**Issue:** The notebook's `dc_predict = lambda a, b, ctx: (...)` ignores `ctx`
(neutral, date, tournament), so the didactic structural features never reflect home
advantage even on non-neutral matches. Since the synthetic history is all
`neutral=True`, the output is unaffected, but the example silently models away a
feature the prose emphasizes (the +100 host bonus). A learner copying this stub for
real data would lose host advantage.
**Fix:** Have the demo predictor read `ctx["neutral"]` (even trivially) so the
pedagogical example mirrors the production contract it is teaching.

### IN-05: `build_notebook_05._capture` swallows exceptions silently in the last-expression path

**File:** `scripts/build_notebook_05.py:244-251`
**Issue:** If the final line compiles as an expression but raises at `eval` time,
the exception propagates (good), but if an *earlier* `exec(head)` succeeds and the
last expression raises, the cell's partial stdout is still emitted with no error
output — a failed cell can be written to the notebook looking partially successful.
The broader `try/except SyntaxError` only catches `SyntaxError`, so this is mostly
fine, but the generator has no per-cell "this cell raised" record; a runtime error
surfaces only via the top-level `traceback.print_exc()` + `sys.exit(1)`, losing
which cell failed.
**Fix:** Wrap per-cell execution and, on failure, emit an `error` output (or at
least print the cell index) so a broken notebook build is diagnosable.

### IN-06: `run_official` calls `_git_commit()` twice and re-derives the short SHA

**File:** `src/cdd_mundial/live/pipeline.py:439-441` (`_git_commit` + `_git_short_commit`)
**Issue:** `_git_short_commit()` internally calls `_git_commit()` again, so metadata
finalization shells out to `git rev-parse HEAD` twice per run. Minor, but it doubles
a subprocess call and the two calls could in principle observe different HEADs.
**Fix:** Call `_git_commit()` once and slice `[:7]` for the short form.

---

_Reviewed: 2026-06-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
