---
phase: 05-ml-ensemble-upgrade-gated
plan: "04"
subsystem: live
tags: [live-integration, dual-publication, fallback, promotion-gate, provenance, notebook, report]

# Dependency graph
requires:
  - phase: 05-ml-ensemble-upgrade-gated
    plan: "03"
    provides: "evaluate_ml_gate verdict, run_ml_comparison, MulticlassCalibrator + selected ensemble weight (the promotion record the live path consumes)"
  - phase: 05-ml-ensemble-upgrade-gated
    plan: "01"
    provides: "build_ml_dataset point-in-time features + ml_eligible metadata (D-04) used to decide live ML eligibility per match"
provides:
  - "cdd_mundial.live.ml_selection.build_dual_publication: per-match baseline/upgrade/fallback decision turning the gate verdict into a dual-publication table with full provenance"
  - "cdd_mundial.live.ml_selection.decide_publication / PublicationDecision: the pure single-match decision primitive (D-13/D-14)"
  - "cdd_mundial.live.pipeline.run_official(ml_selection_provider=...): opt-in dual publication that adds upcoming_dual.parquet + a model_selection metadata block, leaving the baseline path byte-for-byte unchanged when absent"
  - "report.render_snapshot_report model_selection section: legible upgrade-promoted / no-promotion negative result with fallback breakdown"
  - "notebooks/05_ml_ensemble.ipynb: executed didactic Phase-5 evidence notebook over production APIs"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Opt-in production seam: run_official(ml_selection_provider=None) is the stable baseline-only path; a provider strictly ADDS a dual table + metadata, never mutates the baseline publication (D-14)"
    - "Per-match decision is a pure function over (gate_promoted, ml_eligible, has_ml_prob) with a fixed fallback-reason priority, so provenance is deterministic and auditable (T-05-11)"
    - "Dual publication = baseline row ALWAYS published + upgrade row added alongside only for promoted+eligible matches; the baseline is never displaced or shrunk"
    - "Negative result (gate not promoted) is a first-class, visible outcome in both metadata and the rendered report, never an implicit absence (T-05-12)"
    - "Deterministic in-process notebook generator (scripts/build_notebook_05.py) captures real outputs without a Jupyter kernel (jupyter_client unavailable in this venv)"

key-files:
  created:
    - "src/cdd_mundial/live/ml_selection.py"
    - "tests/test_ml_selection.py"
    - "notebooks/05_ml_ensemble.ipynb"
    - "scripts/build_notebook_05.py"
  modified:
    - "src/cdd_mundial/live/pipeline.py"
    - "src/cdd_mundial/live/report.py"
    - "src/cdd_mundial/live/__init__.py"
    - "templates/report_daily.html.jinja"
    - "tests/test_live_pipeline.py"
    - "tests/test_live_report.py"
    - "tests/test_notebooks.py"

key-decisions:
  - "Phase-5 integration is opt-in via an ml_selection_provider callable rather than wired unconditionally: the baseline live path must stay stable (D-14), so with no provider the official run is byte-for-byte the prior baseline-only publication, and all pre-existing pipeline tests pass untouched"
  - "build_dual_publication consumes already-computed baseline + ML probabilities (probability-in) instead of fitting/scoring inside the live layer: the selection module only decides and labels which family publishes, mirroring the probability-in/out contract established in 05-03 and keeping it trivially testable"
  - "The dual table is named upcoming_dual.parquet (not upcoming_match_predictions_dual.parquet) to keep the staging path under the Windows MAX_PATH (260) limit once the dated model_version is embedded in the snapshot id — the same pitfall already guarded across the live layer"
  - "Fallback reasons follow a fixed priority (gate_not_promoted > ml_ineligible > ml_probability_unavailable) so the recorded cause per row is deterministic and never ambiguous"

patterns-established:
  - "A reviewer can read the upgrade decision (promoted family + dual semantics, or the negative result + why baseline stays) from the rendered report and the model_selection metadata block alone, without opening raw artifacts"
  - "Phase notebooks remain orchestration over production APIs (no def/class), executed with non-empty deterministic outputs, generated reproducibly from a committed build script"

requirements-completed: [ML-03]

# Metrics
duration: 18min
completed: 2026-06-16
---

# Phase 5 Plan 04: Live Dual Publication + Explicit Baseline Fallback Summary

**A single explicit production selection module (`ml_selection.py`) that turns the Phase-5 promotion-gate verdict into a per-match publication decision — the baseline is always published, the promoted candidate is published *alongside* it only for ML-eligible matches, and everything else reverts to the baseline with a recorded reason — wired into `run_official` as an opt-in provider that adds a dual table plus auditable `model_selection` metadata without touching the baseline path, surfaced legibly in the snapshot report, and closed out by an executed didactic Phase-5 notebook.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2 (Task 1 TDD)
- **Files created/modified:** 11 (4 created, 7 modified)
- **Tests:** 71 passing across the four touched suites (test_live_pipeline, test_live_report, test_notebooks, test_ml_selection)

## Accomplishments

- **`ml_selection.py` (Task 1).** `decide_publication` is the pure single-match primitive: the baseline is always published; the upgrade is published alongside it only when the gate promoted a candidate AND the match is ML-eligible (D-04) AND an ML probability exists — any missing precondition yields an explicit baseline-only fallback with a deterministic reason (`gate_not_promoted` / `ml_ineligible` / `ml_probability_unavailable`). `build_dual_publication` applies this per match over the baseline upcoming table, emitting a labelled table (one baseline row per match + an upgrade row for each promoted+eligible match) and an auditable summary with counts and the fallback breakdown. The baseline input is never mutated (asserted by test).
- **Pipeline integration (Task 1).** `run_official` gains an opt-in `ml_selection_provider`. When supplied it builds the dual table, stages `upcoming_dual.parquet`, and records a `model_selection` block in `metadata.json` (promoted, winner, per-family published counts, fallback reasons, gate mean log-loss). When absent, the run is byte-for-byte the existing baseline-only publication — a default no-promotion `model_selection` block is still written so a reviewer always sees the (non-)decision. All 14 `test_live_pipeline.py` tests pass, including three new integration tests covering promoted-dual, ineligible-fallback, and failed-gate-baseline-only.
- **Report visibility (Task 2).** `report.py` reads the `model_selection` metadata (synthesizing an explicit baseline-only summary for legacy snapshots) and renders a new `#model-selection` section: the promoted family with dual-publication semantics, or the no-promotion negative result with the explicit fallback-reason breakdown and per-candidate mean log-loss. The renderer still reads only frozen snapshot artifacts + the ledger.
- **Phase-5 evidence notebook (Task 2).** `notebooks/05_ml_ensemble.ipynb` orchestrates production APIs end-to-end on a small reproducible synthetic dataset: the feature table (`build_ml_dataset`), the calibrated baseline-vs-ML-vs-ensemble comparison with the promotion gate (`run_ml_comparison` / `evaluate_ml_gate`), the empirical calibration choice (plot), and the live dual-publication decision (`build_dual_publication`) — closing with the promotion / no-promotion verdict made explicit. It follows the mandatory markdown(What and why) → code → markdown(Interpretation) structure, defines no production logic, and ships executed non-empty outputs (including a rendered plot). `scripts/build_notebook_05.py` regenerates it deterministically in-process (no Jupyter kernel needed).

## Task Commits

1. **RED: failing dual-publication selection contract tests** — `9ac23b0` (test)
2. **Task 1 GREEN: dual-publication selection + pipeline integration** — `2b529fd` (feat)
3. **Task 2: report selection section + Phase-5 evidence notebook** — `9a8cb68` (feat)

## Files Created/Modified

- `src/cdd_mundial/live/ml_selection.py` (created) — `decide_publication`, `build_dual_publication`, `PublicationDecision`, `DualPublication`, family/reason constants.
- `tests/test_ml_selection.py` (created) — 10 tests: per-match decision matrix (promoted+eligible dual, ineligible fallback, failed-gate, missing-prob), dual-table baseline preservation, upgrade-row gating, negative-result baseline-only, provenance columns, summary counts, non-mutation.
- `src/cdd_mundial/live/pipeline.py` (modified) — opt-in `ml_selection_provider`, `_build_dual_table` helper, `upcoming_dual` staging, `model_selection` metadata + return field.
- `src/cdd_mundial/live/report.py` (modified) — `_selection_view`, model-selection rendering, `model_selection` in the result dict.
- `templates/report_daily.html.jinja` (modified) — `#model-selection` section.
- `src/cdd_mundial/live/__init__.py` (modified) — exports the selection surface.
- `tests/test_live_pipeline.py` (modified) — +3 dual-publication integration tests + providers.
- `tests/test_live_report.py` (modified) — +3 selection-visibility tests + a dual-table fixture.
- `tests/test_notebooks.py` (modified) — +6 Phase-5 notebook gates (exists, imports, no-redefine, kernel, sections, executed outputs).
- `notebooks/05_ml_ensemble.ipynb` (created) — executed didactic evidence.
- `scripts/build_notebook_05.py` (created) — deterministic in-process notebook generator.

## Decisions Made

- **Opt-in provider over unconditional wiring.** The locked invariant is that the baseline live path must not be destabilized (D-14). Making Phase-5 a `ml_selection_provider` argument keeps the default official run identical to the prior baseline-only publication (all pre-existing pipeline tests untouched) while still exposing a clean seam for the promoted candidate.
- **Probability-in selection, not in-layer scoring.** `build_dual_publication` decides and labels which family publishes from already-computed baseline + ML probabilities, mirroring the 05-03 probability-in/out contract. The live layer never fits or scores a model, so the decision is pure and trivially testable.
- **`upcoming_dual.parquet` short name.** The longer `upcoming_match_predictions_dual.parquet` pushed the staging path past the Windows MAX_PATH (260) limit once the dated model_version is embedded in the snapshot id (reproduced live during execution). The short name resolves it; this is the same pitfall already guarded elsewhere in the live layer.
- **In-process notebook generator.** `jupyter_client` is not installed in the venv, so the standard kernel-based execution is unavailable. The generator executes each cell in-process and captures real stdout / last-expression / matplotlib-PNG outputs, producing a genuinely executed notebook with deterministic outputs.

## Deviations from Plan

- **[Rule 3 - Blocking] `dc_predict` injection in the notebook.** The default `build_ml_dataset` calls the production Dixon-Coles `predict_lambdas`, which raises `UnknownTeamError` for the notebook's synthetic team slugs. Fixed inline by injecting a small deterministic `dc_predict` lambda (cutoff-correct by construction, the contract the builder is designed for). No production code changed.
- **[Rule 3 - Blocking] Windows MAX_PATH on the dual table filename.** The initial `upcoming_match_predictions_dual.parquet` exceeded the 260-char path limit in the dated staging directory (reproduced during the Task 1 verify). Renamed to `upcoming_dual.parquet` in both the pipeline and the tests. No behavioral change beyond the artifact name.

These were auto-fixed under the deviation rules (no architectural change, no user decision needed). The plan's verify commands used `\.venv\python.exe`; this environment's interpreter is at `.venv\Scripts\python.exe`, which is what was used (path-only difference, not a deviation).

## Threat Model Compliance

- **T-05-10 (tampering, live model selection):** mitigated — all baseline/upgrade/fallback logic is centralized in the single explicit `ml_selection.py` module with 10 dedicated tests; the pipeline delegates to it rather than embedding ad-hoc selection.
- **T-05-11 (repudiation, published model provenance):** mitigated — every published row carries `model_family`, `published_family`, `fallback_reason`, and `winner`; the snapshot `model_selection` metadata records per-family counts and the fallback breakdown. Tests assert provenance on every row and the ineligible row's recorded reason.
- **T-05-12 (information disclosure, hidden negative result):** mitigated — a failed gate publishes baseline-only with explicit `gate_not_promoted` reasons, and the report renders the no-promotion outcome (headline + fallback breakdown) as a visible section. Tests assert both the metadata and the rendered HTML surface the negative result.

## Must-Haves Compliance

- "Aunque el upgrade gane, la publicacion operativa sigue siendo dual: baseline mas candidato promovido." — `build_dual_publication` always emits a baseline row per match and adds the upgrade alongside; `test_dual_publication_preserves_every_baseline_row` + `test_dual_publication_adds_upgrade_rows_only_for_eligible_promoted_matches`.
- "Si el gate no pasa o el partido es inelegible para ML, la prediccion publicada cae de forma explicita al baseline." — encoded in `decide_publication`'s reason priority; `test_failed_gate_keeps_baseline_only_with_reason` + `test_ineligible_match_falls_back_to_baseline_explicitly`.
- "La salida en vivo debe dejar trazabilidad de que modelo produjo cada fila publicada y por que." — provenance columns + `model_selection` metadata; `test_every_published_row_carries_provenance` + pipeline metadata assertions.

## Known Stubs

None. The selection layer consumes real gate verdicts and the real `build_ml_dataset` eligibility contract. The `ml_selection_provider` seam is intentionally injectable (not a stub): the canonical full-history live provider — supplying a cutoff-correct comparison run and the per-match calibrated ML probabilities for the actual upcoming fixtures — is the operational wiring left to the daily-run operator, exactly as the baseline `run_official` already accepts injected paths. The default no-provider run is fully functional (baseline-only), so nothing is left non-functional.

## Next Phase Readiness

- ML-03 is complete: a promoted Phase-5 candidate enters the live system only through explicit dual publication with fallback-safe, auditable reporting.
- The phase is operationally closed: baseline stability is preserved, the upgrade decision is legible end-to-end (selection module → pipeline metadata → report → notebook), and the negative result is first-class.
- No blockers.

## Self-Check: PASSED

- FOUND: src/cdd_mundial/live/ml_selection.py
- FOUND: tests/test_ml_selection.py
- FOUND: notebooks/05_ml_ensemble.ipynb
- FOUND: scripts/build_notebook_05.py
- FOUND: .planning/phases/05-ml-ensemble-upgrade-gated/05-04-SUMMARY.md
- Commits verified: 9ac23b0 (RED), 2b529fd (Task 1 GREEN), 9a8cb68 (Task 2)
- Tests: 71 passed across test_live_pipeline + test_live_report + test_notebooks + test_ml_selection; ruff clean on all new/modified files.

## TDD Gate Compliance

- RED gate: `test(05-04)` commit `9ac23b0` (`ModuleNotFoundError: cdd_mundial.live.ml_selection`) confirmed failing before implementation.
- GREEN gate: `feat(05-04)` commit `2b529fd` after RED. Task 2 (`9a8cb68`) is a non-TDD `auto` task per the plan (report + notebook evidence).
- No unexpected pass during RED (the target module did not exist).
