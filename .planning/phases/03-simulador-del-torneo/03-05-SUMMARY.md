---
phase: 03-simulador-del-torneo
plan: "05"
subsystem: simulation
tags: [monte-carlo, numpy, tournament-engine, marginals, notebook]
requires:
  - "src/cdd_mundial/simulation/rules_fifa.py (rank_group, rank_best_thirds)"
  - "src/cdd_mundial/simulation/slots.py (resolve_third_place_assignments)"
  - "src/cdd_mundial/simulation/knockout.py (compact post-draw resolver)"
  - "src/cdd_mundial/simulation/state.py (TournamentState, PlayedMatchResult)"
  - "src/cdd_mundial/models/dixon_coles.py (predict_lambdas, score_matrix)"
  - "data/external/fixture_2026.csv (frozen 104-match bracket)"
provides:
  - "src/cdd_mundial/simulation/engine.py (simulate_tournaments, SimulationResult)"
  - "src/cdd_mundial/simulation/outputs.py (advancement_table, group_position_table)"
  - "notebooks/03_simulador_torneo.ipynb (executed integral Phase 3 notebook)"
  - "public cdd_mundial.simulation API for Phase 4 consumption"
affects:
  - "Phase 4 daily reports and published forecasts"
tech-stack:
  added: []
  patterns:
    - "NumPy-first vectorized stage sampling with seeded Generator streams"
    - "SeedSequence keyed by stable match_id ordinal for stable common random numbers"
    - "counts-to-probabilities marginal tables separated from the engine loop"
key-files:
  created:
    - src/cdd_mundial/simulation/engine.py
    - src/cdd_mundial/simulation/outputs.py
    - tests/test_simulation_engine.py
    - tests/test_simulation_outputs.py
    - tests/test_simulation_performance.py
    - notebooks/03_simulador_torneo.ipynb
  modified:
    - src/cdd_mundial/simulation/__init__.py
    - tests/test_notebooks.py
    - pyproject.toml
decisions:
  - "Engine accepts a caller-supplied ctx (default neutral World Cup) so the production Dixon-Coles predictor receives its required neutral/date/tournament_type keys."
  - "Batch group ranking uses official global criteria (points->GD->GF) with a deterministic team-order tiebreak; the branchy Article 13 cascade stays in rules_fifa for pure-rules tests."
metrics:
  duration: 11 min
  completed: 2026-06-13
  tasks: 3
  files: 9
---

# Phase 3 Plan 05: Simulador del Torneo Summary

Vectorized NumPy Monte Carlo tournament engine conditioned on played results, emitting stable per-team advancement and group-position marginals, with an executed integral notebook backed exclusively by the tested `cdd_mundial.simulation` production API.

## What Was Built

- **`engine.py` — `simulate_tournaments`**: NumPy-first executor that integer-codes the 48 teams once, overlays `TournamentState` played results, samples every unresolved match's Poisson scoreline from a seeded `Generator`, accumulates group standings vectorially, ranks groups by the official global criteria, selects the 8 best thirds and assigns them to R32 slots via the official Annexe C mapping, and advances the knockout bracket from the frozen fixture slot tokens using the compact post-draw resolver. Returns a `SimulationResult` of integer counts plus retained group scores.
- **Deterministic CRN**: all randomness derives from `SeedSequence([seed, _VERSION])`; each match owns an independent stream via a fixed `spawn_key` keyed by its stable `match_id` ordinal, so fixing earlier matches in a daily update never perturbs still-unplayed match streams (verified by `test_match_streams_are_stable_across_state_updates`).
- **`outputs.py`**: `advancement_table` (per-team `P(R32)`..`P(Campeon)`, monotone by construction) and `group_position_table` (per-team `P(1st)`..`P(4th)`); no joint group-configuration table (D-11).
- **`notebooks/03_simulador_torneo.ipynb`**: executed didactic notebook importing the production API, with the mandatory `What and why -> code -> Interpretation` structure, a visible config exposing quick/10k/100k, marginal tables, reproducibility/timing diagnostics, and a champion-probability plot, committed with lightweight deterministic outputs.

## Performance

- 10,000 tournaments: hard gate met (median run under 60 s; no run exceeded the 75 s ceiling).
- 100,000 tournaments: measured ~8.5 s on the project machine — comfortably beats the target.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking / Rule 2 - Missing critical functionality] Engine ctx was incomplete for the production predictor**
- **Found during:** Task 3 (executing the notebook against the real Dixon-Coles model).
- **Issue:** The engine hard-coded `ctx = {"neutral": neutral}`, but the frozen `predict_lambdas` contract requires `neutral`, `date`, and `tournament_type`. The notebook (which uses the production model) failed with `ctx is missing required key(s): ['date', 'tournament_type']`.
- **Fix:** Added a `ctx` parameter to `simulate_tournaments` that defaults to a neutral-venue World Cup context and is passed through unchanged to the predictor. Stub-based engine tests are unaffected (they ignore ctx); the notebook now runs against the real model.
- **Files modified:** `src/cdd_mundial/simulation/engine.py`
- **Commit:** b226550 (parameter shape), exercised end-to-end in d6a59c1

## Notes

- A one-off notebook builder script (`notebooks/_build_03.py`) was used to construct the notebook deterministically and then removed; the committed artifact is the executed `.ipynb`.
- Pre-existing uncommitted changes (`notebooks/02_modelos_baseline.ipynb`, untracked `.claude/`, `.planning/debug/`) were left untouched per execution instructions.

## Validation

- Per-task quick suite, contract regression suite, and notebook gate: all green (132 passed).
- Full repo suite excluding network/manual/data_acceptance/performance: 248 passed.
- Performance gate: 10k under 60 s (hard), 100k ~8.5 s (target).

## Self-Check: PASSED

All created files exist on disk and all five per-task commits (d8b32d9, b226550, c460d1a, c3c519b, d6a59c1) are present in git history.
