# Phase 3: Simulador del Torneo - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 03-simulador-del-torneo
**Areas discussed:** Tournament state, rules engine scope, Monte Carlo architecture, knockout resolution, simulation outputs, simulation artifact format

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
**Notes:** This captured the original intent. Plan `03-01` later verified that the official 2026 fallback is successive FIFA ranking editions, not drawing of lots; the official rule supersedes the earlier wording.

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

## Simulation artifact format

| Option | Description | Selected |
|--------|-------------|----------|
| Orchestration notebook | Import production `.py` functions, explain the workflow, run simulations, and analyze outputs | x |
| Progressive reconstruction | Reproduce parts of the algorithm step by step before calling production code | |
| Notebook-first implementation | Keep most engine logic in the notebook and only helpers in `.py` | |

**User's choice:** Use the notebook as a didactic orchestration layer over production modules.
**Notes:** The `.py` modules remain the single source of truth for reusable and tested logic.

| Option | Description | Selected |
|--------|-------------|----------|
| One integral notebook | Cover state, rules, Monte Carlo, and analysis in `03_simulador_torneo.ipynb` | x |
| Two notebooks | Separate rules/state from simulation/analysis | |
| Monte Carlo only | Leave rules and state documented only in `.py` | |

**User's choice:** One integral notebook.
**Notes:** The notebook must preserve the project didactic cell sequence.

| Option | Description | Selected |
|--------|-------------|----------|
| Quick demo plus configurable run | Execute a small reproducible example by default and expose 10k/100k configuration | x |
| Always run 10k | Make Run All execute the hard performance batch every time | |
| Lightweight demo only | Keep all large runs outside the notebook | |

**User's choice:** Quick reproducible demonstration plus configurable 10k/100k runs.
**Notes:** Heavy runs are opt-in and remain covered by performance tests.

| Option | Description | Selected |
|--------|-------------|----------|
| Executed with outputs | Commit quick-run tables, diagnostics, and plots | x |
| Cleared | Commit no cell outputs | |
| Final outputs only | Keep only selected final tables and plots | |

**User's choice:** Commit the notebook executed with quick-run results.
**Notes:** Outputs must remain deterministic, reviewable, and free of secret material.

---

## the agent's Discretion

- Concrete in-memory representation of `TournamentState`
- Exact numeric shape of the compact post-draw advancement approximation
- Vectorization strategy
- Exact quick-demo simulation count, within the agreed lightweight default

## Deferred Ideas

- Full joint group outcome tables
- Explicit extra-time goal model
