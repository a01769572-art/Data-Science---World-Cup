---
phase: 04-primer-pronostico-pipeline-diario
plan: "01"
subsystem: live
tags: [live-results, contracts, fail-closed, pandera, tournament-state]
requires:
  - "src/cdd_mundial/simulation/state.py (TournamentState.from_results)"
  - "src/cdd_mundial/data/contracts.py (CanonicalSchema base)"
  - "data/external/fixture_2026.csv"
provides:
  - "data/external/results_2026.csv (canonical live results)"
  - "cdd_mundial.live.LiveResultsSchema + downstream publication schemas"
  - "cdd_mundial.live.build_live_state (fail-closed TournamentState builder)"
affects:
  - "Phase 4 plans 02-05 (predict/snapshot/report/calibration consume frozen contracts)"
tech-stack:
  added: []
  patterns:
    - "Strict/coercing pandera DataFrameModel inheriting shared CanonicalSchema base"
    - "Fail-closed loader delegating to TournamentState.from_results (no ad hoc parsing)"
    - "Explicit traceable OverrideToken for completeness/discrepancy exceptions"
key-files:
  created:
    - "data/external/results_2026.csv"
    - "src/cdd_mundial/live/__init__.py"
    - "src/cdd_mundial/live/contracts.py"
    - "src/cdd_mundial/live/results.py"
    - "tests/test_live_results.py"
  modified: []
decisions:
  - "results_2026.csv carries only the 8 TournamentState columns; no operational metadata (D-03)"
  - "Scraper-assist is verification-only and fails closed on mismatch; canonical CSV always wins (D-04)"
  - "Incomplete already-kicked-off coverage fails by default; only an explicit per-match OverrideToken excuses it (D-05)"
metrics:
  duration: "~14 min"
  completed: "2026-06-13"
  tasks: 2
  files: 5
requirements:
  - DATA-06
  - LIVE-01
---

# Phase 4 Plan 01: Live-Input Contract and Validated Pipeline Entry Summary

Canonical, versioned `results_2026.csv` plus strict pandera contracts and a fail-closed loader that turns it into a `TournamentState` exclusively through `TournamentState.from_results`, making the official daily run independent of any scraper.

## What Was Built

- **`data/external/results_2026.csv`** — minimalist canonical fallback seeded with the three group matches already played as of 2026-06-13 (WC26-001/002/003). Exactly the 8 columns `TournamentState` needs; no timestamps, sources, or notes (D-03).
- **`src/cdd_mundial/live/contracts.py`** — strict/coercing pandera schemas inheriting the shared `CanonicalSchema` base:
  - `LiveResultsSchema` (canonical CSV contract: unique `match_id`, goals ≥ 0, conduct scores ≤ 0, distinct teams).
  - `UpcomingPredictionsSchema`, `FrozenBenchmarkSchema`, `CalibrationLedgerSchema` — frozen now so Phase 4 plans 02–05 implement against a fixed interface without re-touching contracts.
- **`src/cdd_mundial/live/results.py`** — pure, reusable loader:
  - `load_live_results` reads + strict-validates the CSV into `PlayedMatchResult` rows.
  - `build_live_state` runs the gates (scraper-assist verify → completeness → fixture-backed `from_results`) and returns a `TournamentState`.
  - `OverrideToken`, `IncompleteResultsError`, `DiscrepancyError` implement traceable, opt-in exceptions.
- **`tests/test_live_results.py`** — 25 tests covering schema strictness, downstream contract normalization, fail-closed loader paths, completeness/override semantics, scraper-assist verification, and a round-trip against the real frozen fixture.

## Task-by-Task

| Task | Name | Gate commits | Files |
| ---- | ---- | ------------ | ----- |
| 1 | Freeze live-input contracts + CSV fallback | `30d1e22` (RED), `51aa80c` (GREEN) | results_2026.csv, live/__init__.py, live/contracts.py, tests/test_live_results.py |
| 2 | Fail-closed results loading into TournamentState | `30d1e22` (RED, shared), `5737e0d` (GREEN) | live/results.py, live/__init__.py |

## TDD Gate Compliance

- RED gate: `30d1e22` — `test(04-01)` commit; tests failed (module not implemented) before any logic.
- GREEN gates: `51aa80c` (contracts) and `5737e0d` (loader) — `feat(04-01)` commits with the suite passing.
- REFACTOR: none required.

## Verification

- `pytest tests/test_live_results.py tests/test_tournament_state.py` → 44 passed.
- Full non-network suite (`-m "not network and not manual"`) → 285 passed, no regressions.
- Verification criterion satisfied: `build_live_state` is the sole loader and delegates to `TournamentState.from_results`; no parsing path bypasses it.

## Threat Model Coverage

| Threat ID | Disposition | How mitigated |
|-----------|-------------|----------------|
| T-04-01 (CSV tampering) | mitigate | `LiveResultsSchema` strict validation + fixture-backed duplicate/existence/unknown-team checks in `from_results`. |
| T-04-02 (scraper spoof) | mitigate | Scraper-assist is verification-only; `DiscrepancyError` fails closed; canonical CSV value never rewritten. |
| T-04-03 (silent incomplete run) | mitigate | Completeness gate fails by default; `OverrideToken` requires a non-empty reason and records excused matches for snapshot metadata. |

## Decisions Made

- `results_2026.csv` holds only the 8 `TournamentState` columns; operational metadata lives elsewhere (D-03).
- Scraper-assist may only verify the canonical CSV; mismatches fail closed and the canonical value always wins (D-04).
- Incomplete coverage for already-kicked-off matches fails by default; only an explicit per-match `OverrideToken` (with a recorded reason) excuses it (D-05).
- `as_of` drives the completeness gate via the fixture's `kickoff_utc`, keeping the check data-driven rather than hardcoded.

## Deviations from Plan

None — plan executed as written. One test-infrastructure adjustment within Task 1's scope: pandera raises `SchemaErrors` (plural, no shared base with `SchemaError`) on strict-column rejection, so the tests catch both via a `SCHEMA_ERRORS` tuple.

## Known Stubs

None. The CSV is seeded with real played matches and the loader is production-ready. Downstream schemas (`UpcomingPredictionsSchema`, `FrozenBenchmarkSchema`, `CalibrationLedgerSchema`) are intentionally interface-only here; Phase 4 plans 02–05 will produce data against them.

## Self-Check: PASSED

All 5 created files present on disk; all 3 task commits (`30d1e22`, `51aa80c`, `5737e0d`) present in git history.
