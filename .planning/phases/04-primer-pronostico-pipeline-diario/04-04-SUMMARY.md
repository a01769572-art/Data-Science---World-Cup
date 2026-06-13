---
phase: 04-primer-pronostico-pipeline-diario
plan: "04"
subsystem: live
tags: [calibration, frozen-benchmark, append-only-ledger, median-demargin, rps, model-vs-market]
requires:
  - "src/cdd_mundial/data/ingest_odds.py (demargin_decimal_odds, build_odds_benchmark semantics)"
  - "src/cdd_mundial/data/provenance.py (file_sha256, deterministic JSON/SHA-256 discipline)"
  - "src/cdd_mundial/models/metrics.py (rps, brier_multiclass)"
  - "src/cdd_mundial/models/validation.py (log_loss labels=[0,1,2] usage)"
  - "src/cdd_mundial/live/snapshots.py (SnapshotWriter staging/finalization API)"
  - "src/cdd_mundial/live/contracts.py (FrozenBenchmarkSchema, CalibrationLedgerSchema)"
provides:
  - "cdd_mundial.live.freeze_market_benchmark (median primary + mean auxiliary, publication-time freeze)"
  - "cdd_mundial.live.register_frozen_benchmark (stage slice + deterministic row ids/checksum)"
  - "cdd_mundial.live.build_ledger_rows / append_ledger (append-only per-match calibration ledger)"
  - "cdd_mundial.live.cumulative_metrics (model-vs-market RPS/Brier/log-loss over resolved rows)"
  - "cdd_mundial.live.publish_calibration (append ledger + stage report_inputs slice in one transaction)"
  - "cdd_mundial.live.derive_realized_outcomes (goals -> outcome_idx)"
affects:
  - "Phase 4 plan 03/05 report renderer (consumes calibration_publication_slice + cumulative_metrics)"
  - "Phase 4 pipeline (run_official will wire register_frozen_benchmark + publish_calibration into SnapshotWriter)"
tech-stack:
  added: []
  patterns:
    - "Column-wise median across valid bookmakers as the robust primary benchmark, mean kept only as diagnostic"
    - "Publication-time freeze: benchmark stamped with capture instant, evaluation never re-reads latest odds"
    - "Single top-level append-only parquet ledger; jornada/time-series views are pure derived aggregations"
    - "Deterministic SHA-256 row ids over canonical JSON for one-shot metadata finalization"
key-files:
  created:
    - "src/cdd_mundial/live/calibration.py"
    - "tests/test_live_calibration.py"
  modified:
    - "src/cdd_mundial/live/__init__.py"
decisions:
  - "Primary benchmark is the column-wise median de-margined triplet (robust to a single mispriced book); mean retained as auxiliary diagnostic (D-19/D-20)"
  - "Benchmark frozen at publication time with captured_at_utc stamp; evaluation never reads fresher odds after snapshot (D-21, T-04-10)"
  - "One canonical append-only ledger row per (match_id, snapshot_id); re-append fails loud; jornada views are derived only (D-18/D-22, T-04-11)"
  - "Unresolved matches carry outcome_idx <NA> (Int64) so cumulative metrics skip them while the row stays derivable"
  - "Cumulative metrics reuse rps/brier_multiclass + sklearn log_loss(labels=[0,1,2]) exactly as Phase 2 validation (T-04-12)"
metrics:
  duration: "~12 min"
  completed: "2026-06-13"
  tasks: 2
  files: 3
requirements:
  - LIVE-04
  - DOC-02
---

# Phase 4 Plan 04: Live Calibration Tracker and Frozen Market Benchmark Summary

A single canonical, append-only per-match calibration ledger plus a publication-time frozen market benchmark whose primary signal is the **median** de-margined multi-bookmaker probability triplet, letting every published snapshot be scored honestly against a frozen market baseline using the exact Phase 2 metric helpers — with cumulative and time-series views derived from base records rather than any second mutable summary.

## What Was Built

- **`src/cdd_mundial/live/calibration.py`** — the live-evaluation core:
  - `freeze_market_benchmark(quotes, captured_at_utc=...)` aggregates per-bookmaker de-margined `prob_home/prob_draw/prob_away` rows (the canonical output of `build_odds_benchmark`) into a per-match slice: the **column-wise median** (renormalized) is the primary benchmark, with the **mean** carried as `prob_*_mean` auxiliary diagnostics and `n_bookmakers` recorded. Every row is stamped with the capture instant (`...Z`), making the slice immune to later line movement (D-21, T-04-10). Primary columns satisfy `FrozenBenchmarkSchema`.
  - `benchmark_row_ids` / `register_frozen_benchmark` derive deterministic SHA-256 row ids and stage the slice via `SnapshotWriter.add_table`, returning `{filename, row_ids, sha256}` so the finalizer can reference it once before publication.
  - `derive_realized_outcomes(results)` maps 90-minute goals to `outcome_idx` (0=team_a win, 1=draw, 2=team_b win), matching the project metric convention.
  - `build_ledger_rows(...)` builds one canonical row per match for a publication, freezing model 1/X/2 probabilities, the frozen market benchmark (`market_prob_*`), and the realized `outcome_idx` (nullable `Int64` — `<NA>` when unresolved), keyed by `snapshot_id` + `model_version`.
  - `append_ledger(ledger_path, rows)` appends to the top-level canonical parquet `data/processed/live/calibration/calibration_matches.parquet`, never rewriting existing rows and failing loud on a duplicate `(match_id, snapshot_id)` key (D-18, T-04-11). Returns the appended row ids.
  - `cumulative_metrics(rows)` computes model-vs-market RPS/Brier/log-loss over only the resolved rows, reusing `rps` / `brier_multiclass` from `models.metrics` and `sklearn.metrics.log_loss(labels=[0,1,2])` exactly as `models.validation` does (T-04-12). Jornada / time-series views are derivable by the caller from these base rows — no second stored dataset.
  - `publish_calibration(writer, ledger_path, rows)` runs the publication transaction: append to the canonical ledger and stage the snapshot-local `report_inputs/calibration_publication_slice.parquet`, handing back appended-row ids + slice checksum for one-shot metadata finalization.
- **`tests/test_live_calibration.py`** — 12 tests covering median-not-mean primary benchmark, mean-as-diagnostic, contract conformance, capture-time stamping, deterministic registration/row-ids, outcome derivation, one-row-per-match ledger, append-only + duplicate rejection, cumulative metrics matching Phase 2 helpers, unresolved-match exclusion, and publication-slice staging/referencing.
- **`src/cdd_mundial/live/__init__.py`** — re-exports the public calibration surface.

## Task-by-Task

| Task | Name | Gate commits | Files |
| ---- | ---- | ------------ | ----- |
| 1 | Freeze the market benchmark at publication time | `925f2b5` (RED, shared), `7cb76b7` (GREEN) | calibration.py, __init__.py, tests/test_live_calibration.py |
| 2 | Build the append-only per-match calibration ledger | `925f2b5` (RED, shared), `7cb76b7` (GREEN) | calibration.py, __init__.py, tests/test_live_calibration.py |

Both tasks land in one cohesive module; they share a single RED gate and a single GREEN gate because the ledger (Task 2) consumes the frozen benchmark (Task 1) directly.

## TDD Gate Compliance

- RED gate: `925f2b5` — `test(04-04)` commit; `from cdd_mundial.live import calibration` raised `ImportError` (module absent) before any logic.
- GREEN gate: `7cb76b7` — `feat(04-04)` commit; all 12 calibration tests pass.
- REFACTOR: none required. (One test-infrastructure correction — swapping pytest `tmp_path` for the workspace-local `test_workspace` fixture — was applied while bringing the suite green, per the Phase 1 Windows/OneDrive temp-ACL decision; not a behavior change.)

## Verification

- `pytest tests/test_live_calibration.py` → **12 passed**.
- Full non-network suite (`-m "not network and not manual"`) → **314 passed**, no regressions (was 302 before this plan; +12 calibration tests; 100k-sim engine path ~8.2 s, within budget).
- Verification criterion satisfied: the primary benchmark is the median de-margined triplet, the ledger is append-only with strict duplicate rejection, and cumulative model-vs-market metrics reproduce the Phase 2 helpers exactly.

## Threat Model Coverage

| Threat ID | Disposition | How mitigated |
|-----------|-------------|----------------|
| T-04-10 (benchmark freeze timing) | mitigate | `freeze_market_benchmark` stamps every row with `captured_at_utc` and `register_frozen_benchmark` stages it into the snapshot before metadata finalization; nothing reads "latest odds" after snapshot time (D-21). |
| T-04-11 (calibration ledger) | mitigate | `append_ledger` only appends, validates uniqueness of `(match_id, snapshot_id)` against the existing canonical parquet and within the new rows, and returns appended ids to the finalizer (D-18). |
| T-04-12 (metric comparability) | mitigate | `cumulative_metrics` reuses `rps` / `brier_multiclass` and `log_loss(labels=[0,1,2])`; base rows store frozen model probs, frozen market benchmark, and `outcome_idx`, so cumulative series recompute exactly. |

## Decisions Made

- The primary market benchmark is the **column-wise median** de-margined probability triplet across valid bookmakers (robust to a single mispriced book), renormalized to sum to one; the simple **mean** is retained only as an auxiliary diagnostic alongside `n_bookmakers` (D-19/D-20).
- The benchmark is frozen at publication time (`captured_at_utc`) and the evaluation path never substitutes fresher odds (D-21).
- One canonical append-only ledger row per `(match_id, snapshot_id)`; re-appending the same key fails loud; jornada / time-series views are pure derived aggregations, never a second mutable summary (D-18/D-22).
- Unresolved matches are stored with `outcome_idx = <NA>` (nullable `Int64`) so the row stays in the ledger and becomes scorable once the result lands, while `cumulative_metrics` skips it until then.

## Deviations from Plan

None — plan executed as written. The two plan tasks were implemented as a single cohesive module with shared TDD gates (the ledger consumes the frozen benchmark), and the `SnapshotWriter` staging API was extended with a small internal helper (`_stage_nested_parquet`) to write the nested `report_inputs/calibration_publication_slice.parquet` path, since `add_table` only handles flat names.

## Known Stubs

None. Stub scan over `calibration.py` found no `TODO`/`FIXME`/placeholder/`NotImplementedError` patterns. The canonical ledger parquet and snapshot-local slice are written for real; the only integration left is the pipeline-side wiring (`run_official` calling `register_frozen_benchmark` + `publish_calibration`), which is the explicit next-plan concern, not a stub here.

## Self-Check: PASSED

- `src/cdd_mundial/live/calibration.py` — FOUND on disk.
- `tests/test_live_calibration.py` — FOUND on disk.
- `src/cdd_mundial/live/__init__.py` — FOUND on disk (modified).
- Commits `925f2b5` (RED) and `7cb76b7` (GREEN) — FOUND in git history.
