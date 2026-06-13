# Phase 3: Simulador del Torneo - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-12
**Phase:** 03-simulador-del-torneo
**Areas discussed:** Tournament state, rules engine scope, Monte Carlo architecture, knockout resolution, simulation outputs

---

## Tournament state

| Option | Description | Selected |
|--------|-------------|----------|
| Results only | Store only already-played results and recompute standings from fixture plus results | x |
| Rich state | Persist derived standings and incremental state inside `TournamentState` | |

**User's choice:** Results only, with `team_a` / `team_b` naming instead of `home` / `away`.
**Notes:** Host advantage should stay in context because most matches are neutral except for hosts.

---

## Rules engine scope

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic only | Stop at deterministic criteria and defer fair play / drawing of lots | |
| Full FIFA chain | Include fair play and drawing of lots within Phase 3 scope | x |

**User's choice:** Keep fair play and drawing of lots in scope.
**Notes:** The user initially suggested deterministic-only, then resolved the requirements conflict in favor of the full Phase 3 requirement.

---

## Monte Carlo architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Simple first | Build a readable sequential simulator first, vectorize later if needed | |
| Vectorized from the start | Design for thousands of iterations with `numpy` as the primary architecture | x |

**User's choice:** Design for thousands of iterations with `numpy`.
**Notes:** This locks the implementation style for planning; performance is a first-order requirement, not a later optimization.

---

## Knockout resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit ET model | Simulate 90', then extra time, then penalties | |
| Compact approximation | Resolve 90' draws with a compact advancement approximation | x |

**User's choice:** Compact approximation.
**Notes:** The user selected the simplest compact version rather than an explicit extra-time submodel.

---

## Simulation outputs

| Option | Description | Selected |
|--------|-------------|----------|
| Advancement only | Output knockout-round advancement probabilities only | |
| Advancement + group marginals | Output knockout advancement plus `P(1st)` / `P(2nd)` / `P(3rd)` / `P(4th)` per team | x |

**User's choice:** Advancement + group marginals.
**Notes:** The user first deferred group-position outputs to Phase 4, then changed that decision and kept them in Phase 3 as marginal outputs only.

---

## the agent's Discretion

- Concrete in-memory representation of `TournamentState`
- Exact numeric shape of the compact post-draw advancement approximation
- Vectorization strategy and output artifact format

## Deferred Ideas

- Full joint group outcome tables
- Explicit extra-time goal model
