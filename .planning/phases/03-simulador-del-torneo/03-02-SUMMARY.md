---
phase: 03-simulador-del-torneo
plan: 02
subsystem: simulation-contracts
tags: [tournament-state, knockout-resolver, tdd, sim-03, sim-05, d-01, d-02, d-07, d-08]

requires:
  - phase: 01-fundacion-de-datos
    plan: 04
    provides: frozen fixture_2026.csv (104 matches, slot tokens, canonical participants)
  - phase: 02-modelos-baseline
    plan: 03
    provides: frozen predict_lambdas(team_a, team_b, ctx) contract and wdl_from_lambdas helper
provides:
  - Bootstrap `cdd_mundial.simulation` package with the first stable Phase 3 exports
  - Thin `TournamentState` contract: played results only, keyed by match_id, fixture-validated
  - `PlayedMatchResult` with team_a/team_b semantics, observed fair-play inputs, knockout advanced_team
  - `played_results_from_json` fail-closed parser for conditioned-results documents
  - Compact post-draw knockout resolver: q = p_win/(p_win+p_loss) with shrinkage, exact complement
  - Vectorized `sample_post_draw_advancers` (one winner per draw by construction)
affects: [03-03, 03-04, 03-05, engine, rules_fifa, outputs]

tech-stack:
  added: []
  patterns:
    [
      frozen dataclass with fail-loud __post_init__,
      fixture-validated state constructor,
      small deterministic probability helpers with explicit float casting,
      TDD RED/GREEN per task,
    ]

key-files:
  created:
    - src/cdd_mundial/simulation/__init__.py
    - src/cdd_mundial/simulation/state.py
    - src/cdd_mundial/simulation/knockout.py
    - tests/fixtures/tournament/conditioned_results.json
    - tests/test_tournament_state.py
    - tests/test_knockout.py
  modified: []

key-decisions:
  - "TournamentState validates against a fixture frame (match_id/stage/home/away columns): unknown match IDs, unknown teams, and participant conflicts fail loudly; known-team universe = resolved fixture participants"
  - "Knockout advancement after a 90-minute draw is recorded state (advanced_team), required for drawn knockout results and forbidden on group matches — never resolved bracket logic"
  - "Fair-play inputs are observed Art. 13 conduct scores (deductions <= 0) accepted per played match; future cards are never simulated (resolved research question)"
  - "Compact resolver splits the draw mass by q = p_win/(p_win+p_loss) with optional shrink toward 0.5; swapping teams swaps q with 1-q so the complement identity is structural (D-07/D-08)"
  - "SIM-03 and SIM-05 are NOT marked complete: this plan locks their behavioral boundaries; engine-level conditioning and integration land in 03-05, which re-lists both requirements"

requirements-completed: []

duration: 7min
completed: 2026-06-13
---

# Phase 3 Plan 02: Estado del Torneo y Resolver de Eliminatorias Summary

**Paquete `simulation` arrancado con el contrato de estado delgado (solo resultados jugados, `team_a`/`team_b`, validado contra el fixture congelado) y el resolver compacto post-empate de eliminatorias (q = p_win/(p_win+p_loss), complemento exacto al intercambiar equipos, sin lambdas de tiempo extra), ambos con ciclo TDD completo.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-06-13T00:28:44Z
- **Completed:** 2026-06-13T00:35:45Z
- **Tasks:** 2 (TDD: 2 RED + 2 GREEN commits)
- **Files modified:** 6

## Accomplishments

- `src/cdd_mundial/simulation/__init__.py` existe antes de que cualquier plan posterior importe del paquete, con el mismo patrón de exports que `models/__init__.py` (6 contratos públicos).
- `TournamentState` es delgado por construcción (D-01): único campo `played` keyed por `match_id`, normalización determinista por orden lexicográfico, sin standings derivados ni participantes futuros resueltos — verificado con un test estructural sobre `dataclasses.fields`.
- `PlayedMatchResult` congela la semántica `team_a`/`team_b` (D-02): goles enteros no negativos, equipos distintos, conduct scores opcionales del Art. 13 (deducciones <= 0), y `advanced_team` validado contra participantes y contra marcadores decididos.
- Validación fail-loud contra el fixture (T-03-04): match_id duplicado, match_id desconocido, slug de equipo desconocido (`UnknownTeamError`), conflicto de participantes con filas resueltas del fixture, `advanced_team` en partidos de grupo, y empate de eliminatoria sin `advanced_team`.
- `tests/fixtures/tournament/conditioned_results.json`: fixture revisable con un partido de grupo decidido (con fair-play observado), un empate de grupo y un empate de eliminatoria con lado avanzante — construye estado contra el fixture oficial congelado real.
- Resolver compacto (D-07/D-08): `post_draw_advance_probability` reparte la masa de empate por fuerza no-empate con shrinkage opcional; `advance_probability` = `p_win + p_draw*q`; complemento exacto bajo intercambio verificado analíticamente y con probabilidades Dixon-Coles reales.
- `sample_post_draw_advancers` vectorizado: exactamente un ganador por empate por construcción (team_b avanza donde team_a no); sesgo de orden empírico < 0.005 con 100,000 resoluciones por orden y semillas fijas independientes (gate de 03-VALIDATION).
- Gate de firma D-07/D-08: test `inspect.signature` congela que el resolver consume solo `(p_win, p_draw, p_loss, shrink)` — sin lambdas de tiempo extra; el docstring documenta que el engine debe alimentar streams deterministas keyed por `match_id` + semilla de simulación/versión.

## Task Commits

1. **Task 1 RED: failing tests for thin TournamentState contract** - `744dcde`
2. **Task 1 GREEN: bootstrap simulation package with thin TournamentState** - `f6567ec`
3. **Task 2 RED: failing symmetry tests for compact knockout resolver** - `557260e`
4. **Task 2 GREEN: implement compact post-draw knockout resolver** - `5933d41`

No REFACTOR commits were needed: both GREEN implementations landed clean (ruff green, 100-char limit respected).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixture used a team unknown to the minimal frame**
- **Found during:** Task 1 GREEN
- **Issue:** `test_drawn_knockout_match_requires_advanced_team` used `canada`, which is not a participant in the minimal 4-row fixture factory, so the unknown-team check fired before the advanced_team check the test targets.
- **Fix:** Switched the drawn knockout record to `mexico` vs `south-korea` (both known to the minimal fixture).
- **Files modified:** `tests/test_tournament_state.py`
- **Commit:** `f6567ec`

No other deviations — plan executed as written.

## Verification

```text
.\.venv\python.exe -m pytest -q -p no:cacheprovider tests/test_tournament_state.py tests/test_knockout.py -x
-> 45 passed

.\.venv\python.exe -m pytest -q -p no:cacheprovider tests/test_fixture.py tests/test_dixon_coles.py
-> 24 passed (frozen fixture + Dixon-Coles contracts remain green)

.\.venv\python.exe -m ruff check src/cdd_mundial/simulation/ tests/test_tournament_state.py tests/test_knockout.py
-> All checks passed!
```

## TDD Gate Compliance

- RED gates: `744dcde` (state), `557260e` (knockout) — both verified failing (ModuleNotFoundError at collection) before implementation.
- GREEN gates: `f6567ec`, `5933d41` — targeted suites green after each.
- REFACTOR: not needed; no behavior-preserving cleanup commits.

## Requirements Status

- **SIM-03 / SIM-05:** NOT marked complete. This plan locks their behavioral boundaries (thin conditioned state; unbiased post-draw advancement) with Wave 0 tests, but the engine-level behaviors (played results fixed across seeds inside Monte Carlo runs; knockout resolution wired into the bracket) land in plan 03-05, which re-lists both requirements in its frontmatter.

## Known Stubs

None — all delivered functions are fully implemented and tested; no placeholder values or unwired data paths.

## Threat Flags

None — no new surface beyond the plan's threat model. T-03-04 (state input tampering), T-03-05 (deterministic conditioning), and T-03-06 (resolver symmetry) mitigations are implemented and tested.

## Self-Check: PASSED

- `src/cdd_mundial/simulation/__init__.py` — FOUND
- `src/cdd_mundial/simulation/state.py` — FOUND
- `src/cdd_mundial/simulation/knockout.py` — FOUND
- `tests/fixtures/tournament/conditioned_results.json` — FOUND
- `tests/test_tournament_state.py` — FOUND
- `tests/test_knockout.py` — FOUND
- Commits `744dcde`, `f6567ec`, `557260e`, `5933d41` — FOUND in git log
