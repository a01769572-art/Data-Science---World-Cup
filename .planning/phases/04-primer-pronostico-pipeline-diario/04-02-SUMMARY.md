---
phase: 04-primer-pronostico-pipeline-diario
plan: "02"
subsystem: live
tags: [official-run, materialization, refit-vs-reuse, snapshots, atomic-publish, cli]
requires:
  - "src/cdd_mundial/live/results.py (build_live_state, OverrideToken)"
  - "src/cdd_mundial/live/contracts.py (UpcomingPredictionsSchema)"
  - "src/cdd_mundial/models/validation.py (dated artifact materialization precedent)"
  - "src/cdd_mundial/models/elo.py (recompute_elo, snapshot_ratings)"
  - "src/cdd_mundial/models/loading.py (load_matches, 90-min outcome semantics)"
  - "src/cdd_mundial/models/dixon_coles.py (fit_dixon_coles, DixonColesModel)"
  - "src/cdd_mundial/simulation/engine.py (simulate_tournaments)"
  - "src/cdd_mundial/simulation/outputs.py (advancement_table, group_position_table)"
  - "src/cdd_mundial/data/provenance.py (file_sha256, write_provenance_manifest)"
provides:
  - "cdd_mundial.live.materialize_live_training (immutable dated live-training artifact + refreshed Elo)"
  - "cdd_mundial.live.select_model_artifact (deterministic refit-vs-reuse, model_version D-13)"
  - "cdd_mundial.live.SnapshotWriter (sibling-temp staging + atomic append-only publish)"
  - "cdd_mundial.live.run_official / verify_official (one-command official run)"
  - "python -m cdd_mundial.live (--verify-only, --allow-dirty)"
affects:
  - "Phase 4 plans 03-05 (report renderer, frozen benchmark, calibration ledger consume the snapshot bundle + SnapshotWriter hooks)"
tech-stack:
  added: []
  patterns:
    - "Materialize-before-decide: immutable dated derived artifact precedes any fingerprint/reuse/refit"
    - "Content-addressed immutable parquet write (identical replay -> identical bytes; mutation fails loud)"
    - "Deterministic input fingerprint (derived-artifact sha + xi + roster) drives reuse vs dated refit"
    - "Sibling-temp staging + finalize-metadata-once + atomic rename for append-only bundles"
key-files:
  created:
    - "src/cdd_mundial/live/materialization.py"
    - "src/cdd_mundial/live/predict.py"
    - "src/cdd_mundial/live/snapshots.py"
    - "src/cdd_mundial/live/pipeline.py"
    - "src/cdd_mundial/live/__main__.py"
    - "tests/test_live_pipeline.py"
    - "tests/test_live_snapshots.py"
  modified:
    - "src/cdd_mundial/live/__init__.py"
    - ".gitignore"
decisions:
  - "Live results map to canonical 90-min schema as neutral-venue FIFA World Cup rows; advanced_team on a draw sets result_after_extra_time (D-06)"
  - "input_fingerprint = sha256(derived-artifact sha + source_version + sorted roster + xi); reuse pinned dc_params when unchanged, dated refit when changed"
  - "model_version = baseline-v1-YYYY-MM-DD-<shortsha7> where shortsha is the leading 7 hex of the input fingerprint (D-13)"
  - "Snapshot staging prefix shortened to .stg- and group table renamed group_positions to stay under Windows MAX_PATH (260) for dated snapshot ids"
  - "Dated live-training provenance JSON and published snapshot bundles are runtime byproducts -> gitignored, not versioned source"
metrics:
  duration: "~16 min"
  completed: "2026-06-13"
  tasks: 2
  files: 9
requirements:
  - LIVE-01
  - LIVE-02
  - DOC-02
---

# Phase 4 Plan 02: Official Run Core and Append-Only Snapshot Writer Summary

One-command official daily run (`python -m cdd_mundial.live`) that first materializes an immutable dated live-training artifact from canonical results + history, deterministically reuses-or-refits the dated Dixon-Coles model by input fingerprint, simulates the remaining tournament conditioned on played results, and publishes an append-only snapshot bundle by atomic rename with full git/provenance metadata.

## What Was Built

- **`src/cdd_mundial/live/materialization.py`** — the materialize-before-decide stage (D-06):
  - `map_live_rows_to_canonical` maps validated `PlayedMatchResult` rows into the canonical `HistoricalMatchesSchema` shape with neutral-venue FIFA-World-Cup / 90-minute semantics, fixture-gated (out-of-fixture rows fail loud), revalidated against the contract.
  - `materialize_live_training` writes a dated **content-addressed immutable** parquet under `data/processed/live/` (identical canonical inputs replay to the same SHA-256; a different payload to the same dated path fails loud), refreshes Elo/form features chronologically over history + live rows via the Phase 2 `recompute_elo`/`snapshot_ratings` APIs, and emits deterministic provenance — without ever rewriting the raw historical parquet.
  - `compute_input_fingerprint` + `select_model_artifact` compute the fingerprint **only after** the derived artifact exists, then deterministically reuse the pinned dated `dc_params_*.json` when unchanged and refit exactly one new dated artifact (with a `baseline-v1-YYYY-MM-DD-<shortsha>` `model_version`) when it changes. The pin lives in `live_model_fingerprint.json`.
- **`src/cdd_mundial/live/predict.py`** — `upcoming_match_predictions` builds the next-block 1/X/2 table against the frozen `UpcomingPredictionsSchema`, excluding already-played and unresolved-participant matches, using the model's fitted `rho`.
- **`src/cdd_mundial/live/snapshots.py`** — `SnapshotWriter`: stages every artifact in a temporary sibling directory, exposes `add_table` / `append_ledger_rows` / `add_report_asset` hooks for later plans, finalizes `metadata.json` **exactly once** (embedding a SHA-256 for every staged artifact, never its own), and publishes by a single atomic `rename` into the timestamped append-only destination. Re-publishing the same id fails loud (append-only); pre-publish failures abort the staging dir.
- **`src/cdd_mundial/live/pipeline.py`** — `run_official` / `verify_official` enforce the `materialize -> select_model -> simulate -> publish` order, gate on a clean worktree by default (D-11), and write `metadata.json` once at publish time with commit hash, dirty status + modified files, live-training provenance, model provenance/fingerprint, and checksums.
- **`src/cdd_mundial/live/__main__.py`** — `python -m cdd_mundial.live` with `--verify-only` (validate prerequisites + print the intended summary and order, no writes) and `--allow-dirty` (record, never hide, the override).

## Task-by-Task

| Task | Name | Gate commits | Files |
| ---- | ---- | ------------ | ----- |
| 1 | Materialize immutable live-training inputs before deterministic reuse/refit | `6b89a5f` (RED), `5e74a51` (GREEN) | materialization.py, tests/test_live_pipeline.py |
| 2 | Simulate and stage the official snapshot only after materialization/refit-reuse resolves | `5374347` (RED), `ec3d8df` (GREEN) | snapshots.py, predict.py, pipeline.py, __main__.py, __init__.py, .gitignore, tests/test_live_snapshots.py, tests/test_live_pipeline.py |

## TDD Gate Compliance

- Task 1 — RED `6b89a5f` (`test(04-02)`, materialization module absent → ImportError), GREEN `5e74a51` (`feat(04-02)`, 8 tests pass).
- Task 2 — RED `5374347` (`test(04-02)`, snapshots/pipeline modules absent → ImportError), GREEN `ec3d8df` (`feat(04-02)`, full 17-test suite passes).
- REFACTOR: none required (the Windows MAX_PATH fix was applied before the GREEN commit, while the suite was still being brought green).

## Verification

- `pytest tests/test_live_snapshots.py tests/test_live_pipeline.py` → **17 passed**.
- Full non-network suite (`-m "not network and not manual"`) → **302 passed**, no regressions (100k-sim engine path ~15s, within budget).
- `python -m cdd_mundial.live --verify-only --allow-dirty` → deterministic JSON summary reporting `live_training_path`/`sha256`, `input_fingerprint`, `model_version` (`baseline-v1-2026-06-13-50d98ab`), `order=[materialize, select_model, simulate, publish]`, `published=false` — and writes no snapshot bundle.

## Threat Model Coverage

| Threat ID | Disposition | How mitigated |
|-----------|-------------|----------------|
| T-04-04 (publication provenance repudiation) | mitigate | `metadata.json` records `commit`, `commit_short`, `dirty`, `modified_files`, and `allow_dirty_override` at publish time (D-10/D-11). Default run fails closed on a dirty worktree. |
| T-04-05 (snapshot tampering) | mitigate | Bundle is staged in a sibling temp dir, metadata finalized once with per-artifact SHA-256, then published only by atomic rename; re-publishing a published id raises `FileExistsError` (append-only, D-09/D-12). |
| T-04-06 (training-input / model-decision tampering) | mitigate | A dated immutable derived training artifact is written with deterministic provenance + SHA-256 before any decision; the reuse/refit choice is driven by a fingerprint over that artifact + feature/model params and recorded in snapshot metadata (D-06/DOC-02). |

## Decisions Made

- Live results enter the model-facing path as canonical neutral-venue FIFA-World-Cup rows with 90-minute semantics; a drawn knockout with `advanced_team` is tagged `result_after_extra_time=True` so the loader labels it a 90-minute draw (consistent with the martj42 FT+ET convention).
- `model_version` ties to the canonical inputs: `baseline-v1-<as_of_date>-<first7 of input_fingerprint>` (D-13), so the version string changes iff the inputs/params change.
- Staging prefix `.stg-` and table name `group_positions` keep full paths under the Windows MAX_PATH limit when snapshot ids embed the dated `model_version`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Windows MAX_PATH overflow on dated snapshot staging paths**
- **Found during:** Task 2 (full official run test)
- **Issue:** Writing `group_position_probabilities.parquet` into `.staging-<53-char snapshot id>/` pushed the absolute path to 264 chars (> Windows 260 MAX_PATH), failing with `FileNotFoundError` on the second staged table.
- **Fix:** Shortened the staging prefix to `.stg-` and renamed the table to `group_positions`.
- **Files modified:** `src/cdd_mundial/live/snapshots.py`, `src/cdd_mundial/live/pipeline.py`
- **Commit:** `ec3d8df`

**2. [Rule 2 - Hygiene] Dated runtime provenance/snapshot byproducts excluded from version control**
- **Found during:** Task 2 (verify-only run against real data)
- **Issue:** Materialization writes a dated `data/metadata/live_training_<date>.parquet.provenance.json`, which `data/metadata/**/*.json` would otherwise track — committing a per-run, date-stamped runtime byproduct as if it were reviewed source. Published snapshot bundles under `reports/snapshots/` are likewise run outputs.
- **Fix:** Added `.gitignore` rules for `data/metadata/live_training_*.parquet.provenance.json` and `reports/snapshots/`.
- **Files modified:** `.gitignore`
- **Commit:** `ec3d8df`

### Plan-file note

The plan listed `src/cdd_mundial/live/predict.py` under Task 1's `<files>`, but the upcoming-prediction table is naturally a Task 2 (snapshot-staging) concern; it was created in Task 2 alongside `snapshots.py`. Materialization (Task 1) is fully self-contained without it.

## Known Stubs

None. Stub scan over all five new source files found no `TODO`/`FIXME`/placeholder/`NotImplementedError` patterns. The `SnapshotWriter` hooks (`append_ledger_rows`, `add_report_asset`) are intentional extension points with working implementations; Phase 4 plans 03-05 will call them to register the frozen benchmark, ledger rows, and rendered report — they are not stubs.

## Self-Check: PASSED

All 7 created files present on disk; all 4 task gate commits (`6b89a5f`, `5e74a51`, `5374347`, `ec3d8df`) present in git history.
