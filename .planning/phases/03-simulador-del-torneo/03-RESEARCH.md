# Phase 3: Simulador del Torneo - Research

**Researched:** 2026-06-12 [VERIFIED: current session date]
**Domain:** FIFA World Cup 2026 tournament rules engine and vectorized Monte Carlo simulation [VERIFIED: .planning/ROADMAP.md]
**Confidence:** MEDIUM [VERIFIED: this research artifact]

<user_constraints>
## User Constraints (from CONTEXT.md)

Verbatim copy from `03-CONTEXT.md`. [VERIFIED: .planning/phases/03-simulador-del-torneo/03-CONTEXT.md]

### Locked Decisions
- **D-01:** `TournamentState` guarda solo resultados ya jugados. No debe persistir tablas derivadas ni estados intermedios redundantes; esos se recomputan desde fixture + resultados fijados.
- **D-02:** El contrato interno para resultados jugados debe usar `team_a` / `team_b`, no `home_*` / `away_*`. La ventaja de anfitrion se modela solo via `ctx`, no via nombres de columnas.
- **D-03:** El rules engine de la fase SI incluye la cadena completa requerida por FIFA 2026, hasta `fair play` y `drawing of lots`. No se reduce a criterios deterministicos solamente.
- **D-04:** El criterio de exito del rules engine se centra en que los criterios queden implementados correctamente en funciones puras y testeados; no se exige una capa extra de evidencia documental mas alla de fijar la referencia oficial como prerequisito de implementacion.
- **D-05:** El simulador se diseÃ±a desde el inicio para miles de iteraciones con `numpy`. No se prioriza una version naive partido-por-partido como arquitectura principal.
- **D-06:** El motor debe operar sobre el fixture oficial y sus `slot` references existentes (`1A`, `3CDFGH`, `W74`, etc.), resolviendo el bracket sobre esa estructura en vez de redefinirla.
- **D-07:** La resolucion de eliminatorias despues de un empate a 90 minutos usa una aproximacion compacta. No se modela explicitamente tiempo extra con lambdas separadas en esta fase.
- **D-08:** La aproximacion compacta puede convertir el empate a 90 minutos en una probabilidad de avanzar posterior, preservando neutralidad y evitando sesgo de orden entre equipos.
- **D-09:** Phase 3 debe producir las probabilidades de avance por seleccion: `P(R32)`, `P(R16)`, `P(QF)`, `P(SF)`, `P(Final)`, `P(Campeon)`.
- **D-10:** Phase 3 tambien debe producir probabilidades marginales de posicion de grupo por seleccion: `P(1st)`, `P(2nd)`, `P(3rd)`, `P(4th)`.
- **D-11:** No se requieren tablas conjuntas completas de configuraciones de grupo en esta fase; solo marginals por equipo.

### the agent's Discretion
- Elegir la representacion concreta en memoria para `TournamentState`, siempre que cumpla con el principio de almacenar solo resultados ya jugados.
- Elegir la forma numerica exacta de la aproximacion compacta para desempatar eliminatorias despues de 90 minutos, siempre que no introduzca un pseudo-modelo detallado de tiempo extra.
- Elegir la estrategia de vectorizacion y acumulacion de resultados mas simple que cumpla la meta de rendimiento.

### Deferred Ideas (OUT OF SCOPE)
- Full joint group outcome tables - deferred beyond Phase 3; not required for roadmap success criteria.
- Explicit extra-time scoring submodel - deferred; Phase 3 uses the compact post-draw advancement approximation instead.
- Richer state snapshots that cache derived standings after every simulated match - deferred unless performance profiling proves recomputation is the bottleneck.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIM-01 | Reglas FIFA 2026 completas, mejores terceros y asignaciÃ³n a R32, verificadas contra reglamento oficial [VERIFIED: .planning/REQUIREMENTS.md] | Planner must start with a regulation capture gate because the direct official regulation PDF was not resolved in this session. [VERIFIED: attempted-access evidence below] |
| SIM-02 | Monte Carlo vectorizado en numpy, â‰¥10,000 simulaciones, objetivo 100k, <1 min [VERIFIED: .planning/REQUIREMENTS.md] | Use stage-batched NumPy arrays, seeded `Generator`, and mostly vectorized group updates with rare tie-fallback logic. [ASSUMED] |
| SIM-03 | SimulaciÃ³n condicional: resultados jugados se fijan y solo se simula lo restante [VERIFIED: .planning/REQUIREMENTS.md] | `TournamentState` should store only played results keyed by `match_id`, then overlay them onto fixture arrays before sampling. [ASSUMED] |
| SIM-04 | Salidas P(R32), P(R16), P(QF), P(SF), P(Final), P(CampeÃ³n) [VERIFIED: .planning/REQUIREMENTS.md] | Aggregate per-team round indicators from integer team-index arrays after each stage. [ASSUMED] |
| SIM-05 | Eliminatorias con ET/penales y desempate aleatorio sin sesgo [VERIFIED: .planning/REQUIREMENTS.md] | Locked D-07/D-08 forbid separate ET lambdas, so satisfy the behavioral intent with a compact post-draw advancement probability derived from 90-minute strengths. [VERIFIED: .planning/phases/03-simulador-del-torneo/03-CONTEXT.md] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- The project runtime target is Python `>=3.11,<3.13`. [VERIFIED: pyproject.toml]
- The installed local runtime is Python `3.12.13`. [VERIFIED: .venv/python.exe]
- Core numerical libraries already present are `numpy 2.4.6`, `pandas 2.3.3`, `scipy 1.17.1`, `scikit-learn 1.9.0`, `pandera 0.31.1`, `pytest 8.4.2`, and `seaborn 0.13.2`. [VERIFIED: .venv/python.exe]
- Tests run under `pytest` with `addopts = "-ra -p no:cacheprovider"` and `testpaths = ["tests"]`. [VERIFIED: pyproject.toml]
- The repo already treats fixture structure and model interfaces as validated contracts; Phase 3 should extend those contracts rather than rename them. [VERIFIED: src/cdd_mundial/data/ingest_fixture.py, src/cdd_mundial/models/dixon_coles.py]

## Summary

The repo is ready for Phase 3 from a code-contract perspective: the frozen fixture already contains the full 104-match skeleton, the 72 group matches, and the authoritative knockout slot strings (`2A`, `3ABCDF`, `W74`, `L101`). [VERIFIED: data/external/fixture_2026.csv, src/cdd_mundial/data/ingest_fixture.py, tests/test_fixture.py] The model contract Phase 3 must consume is also frozen as `predict_lambdas(team_a, team_b, ctx)`, with `ctx["neutral"]` carrying host advantage and team naming already standardized to `team_a` / `team_b`. [VERIFIED: src/cdd_mundial/models/dixon_coles.py, tests/test_dixon_coles.py]

The main planning blocker remains regulatory, not numerical. [VERIFIED: .planning/STATE.md] This session verified the official FIFA fixture page already used by the repo, and it verified that `fifa.com`, `inside.fifa.com`, and `digitalhub.fifa.com` were reachable after network escalation, but it did not resolve a direct official regulation PDF or official annex URL for the 2026 tie-break and best-third assignment rules before the user-requested cutoff. [VERIFIED: data/external/fixture_2026.csv, direct network attempt log 2026-06-12] Any plan should therefore make regulation capture and archival the first task in Plan `03-01`, with implementation blocked only on the unresolved rule text rather than on the simulator architecture. [VERIFIED: this research artifact]

Architecturally, the right design is a pure-rules layer plus a NumPy engine layer. [ASSUMED] The rules layer should expose deterministic functions for group tables, tie cascades, best-third ranking, and knockout slot resolution. [ASSUMED] The engine layer should operate on integer-coded team arrays and sampled score arrays, apply played results from `TournamentState`, and aggregate marginal probabilities without storing redundant derived state. [ASSUMED]

**Primary recommendation:** Plan `03-01` as a regulation-capture gate plus pure `rules_fifa.py` scaffolding, and plan `03-02` onward around a NumPy-first engine that consumes the existing fixture slots and `predict_lambdas` contract. [VERIFIED: .planning/STATE.md, .planning/phases/03-simulador-del-torneo/03-CONTEXT.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Group standings and tie-break cascade | API / Backend | Database / Storage | Pure rules on in-memory fixture/results data; no browser concerns. [ASSUMED] |
| Best-third ranking across 12 groups | API / Backend | — | Cross-group ranking is part of the same rules engine. [ASSUMED] |
| Third-place assignment to R32 slots | API / Backend | — | Slot resolution is deterministic bracket logic driven by official tokens. [VERIFIED: data/external/fixture_2026.csv] |
| Conditional score simulation for unplayed matches | API / Backend | — | Vectorized Poisson sampling and tournament state overlay belong in compute code. [ASSUMED] |
| Probability aggregation by team and round | API / Backend | Database / Storage | The outputs are tabular artifacts for later reporting phases. [VERIFIED: .planning/phases/03-simulador-del-torneo/03-CONTEXT.md] |

## Official Rule Status

### Verified Officially in This Session

| Claim | Evidence | Confidence |
|------|----------|------------|
| The repo's frozen fixture source is FIFA's official `scores-fixtures` page for the 2026 tournament. [CITED: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures] | The CSV `source_url` column is that FIFA page for every row, and fixture tests enforce it. [VERIFIED: data/external/fixture_2026.csv, tests/test_fixture.py] | HIGH |
| The fixture contains 104 matches, 72 group matches, and knockout slot tokens including third-place selectors and winner/loser references. [VERIFIED: data/external/fixture_2026.csv, tests/test_fixture.py] | This is the authoritative tournament skeleton already accepted by the repo. [VERIFIED: src/cdd_mundial/data/ingest_fixture.py] | HIGH |
| `fifa.com`, `inside.fifa.com`, and `digitalhub.fifa.com` were reachable over direct HTTP after escalation on 2026-06-12. [VERIFIED: direct network attempt log 2026-06-12] | Reachability does not imply the regulation PDF URL was resolved. [VERIFIED: this research artifact] | HIGH |

### Not Verified Officially in This Session

| Topic | Status | What to do next |
|------|--------|-----------------|
| Exact 2026 group tie-break article text | Direct official regulation URL not resolved before cutoff. [VERIFIED: this research artifact] | Plan `03-01` must archive the official PDF and quote the article text into test fixtures. [ASSUMED] |
| Exact fair-play points table for 2026 | Direct official regulation URL not resolved before cutoff. [VERIFIED: this research artifact] | Plan `03-01` must capture the exact disciplinary scoring article from FIFA, not rely on memory. [ASSUMED] |
| Exact wording for drawing of lots | Direct official regulation URL not resolved before cutoff. [VERIFIED: this research artifact] | Plan `03-01` must quote the official fallback criterion. [ASSUMED] |
| Exact official mechanism for assigning the eight best third-placed teams into R32 slots | Direct official regulation annex URL not resolved before cutoff. [VERIFIED: this research artifact] | Plan `03-01` must capture the official annex table or equivalent mapping. [ASSUMED] |

### Attempted Official URLs and Outcome

| URL attempted | Outcome | Notes |
|--------------|---------|-------|
| `https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures` [CITED: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures] | Accessible indirectly through the frozen repo artifact. [VERIFIED: data/external/fixture_2026.csv] | Good enough for fixture slot authority, not enough for regulations text. [VERIFIED: this research artifact] |
| `https://www.fifa.com` [CITED: https://www.fifa.com] | Reachable after escalation. [VERIFIED: direct network attempt log 2026-06-12] | No direct regulation URL resolved before cutoff. [VERIFIED: this research artifact] |
| `https://inside.fifa.com` [CITED: https://inside.fifa.com] | Reachable after escalation. [VERIFIED: direct network attempt log 2026-06-12] | Follow-up content inspection was interrupted at user stop; no regulation URL was pinned. [VERIFIED: interrupted command state 2026-06-12] |
| `https://digitalhub.fifa.com` [CITED: https://digitalhub.fifa.com] | Reachable after escalation. [VERIFIED: direct network attempt log 2026-06-12] | No document path was pinned before cutoff. [VERIFIED: this research artifact] |

### Secondary Evidence Only

Wikipedia's 2026 World Cup page appears to reference a 2025 FIFA regulations document and an Annex C for the 48-team bracket, but that is secondary evidence and must not be treated as implementation authority until the official FIFA document is archived locally. [CITED: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | `3.12.13` | Runtime for simulator modules and tests. [VERIFIED: .venv/python.exe] | Already installed and within the repo's supported range. [VERIFIED: pyproject.toml, .venv/python.exe] |
| NumPy | `2.4.6` | Vectorized sampling, standings accumulation, and aggregation. [VERIFIED: .venv/python.exe] | Phase 3 is explicitly locked to a NumPy-first architecture. [VERIFIED: .planning/phases/03-simulador-del-torneo/03-CONTEXT.md] |
| pandas | `2.3.3` | Fixture loading, state ingestion, and output tables. [VERIFIED: .venv/python.exe] | Already used by fixture ingestion and contracts. [VERIFIED: src/cdd_mundial/data/ingest_fixture.py, src/cdd_mundial/data/contracts.py] |
| SciPy | `1.17.1` | Optional helper for Poisson PMFs or verification utilities. [VERIFIED: .venv/python.exe] | Already present; no new core dependency is needed for simulation. [VERIFIED: pyproject.toml, .venv/python.exe] |
| pytest | `8.4.2` | Unit and integration tests for rules and simulator. [VERIFIED: .venv/python.exe] | Test infrastructure already exists and is configured in repo. [VERIFIED: pyproject.toml] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandera | `0.31.1` | Schema validation for any new state/output tables. [VERIFIED: .venv/python.exe] | Use when persisting simulation artifacts or new input tables. [ASSUMED] |
| joblib | `1.5.3` | Optional persistence for precomputed lookup maps. [VERIFIED: .venv/python.exe] | Use only if lookup generation is expensive enough to cache. [ASSUMED] |
| scikit-learn | `1.9.0` | Not part of the core simulator, but already present. [VERIFIED: .venv/python.exe] | Keep out of the hot loop. [ASSUMED] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure NumPy engine | Numba-accelerated loops | The repo already pins `numpy<2.5` and Phase 3's branchy tie logic is likely correctness-limited, not raw-array-limited, so Numba adds complexity before profiling. [VERIFIED: pyproject.toml] |
| Rules encoded from fixture tokens alone | Official annex lookup or generated lookup table | A local exhaustive check showed the existing third-place tokens do not yield a unique assignment for any of the 495 possible 8-of-12 combinations. [VERIFIED: local exhaustive matching script 2026-06-12] |

**Installation:** No new runtime package is required to plan Phase 3 beyond the already-installed scientific stack. [VERIFIED: pyproject.toml, .venv/python.exe]

## Architecture Patterns

### System Architecture Diagram

```text
Fixture CSV + teams.csv + played results
            |
            v
      TournamentState overlay
            |
            v
   Match preparation by stage/group
            |
            +--> played match -> fixed score arrays
            |
            +--> unplayed match -> predict_lambdas(team_a, team_b, ctx)
                                 -> sample goals with seeded NumPy RNG
            |
            v
   Group table accumulation (points/GD/GF)
            |
            v
   Tie-break cascade + best-third ranking
            |
            v
   R32 slot resolution from official tokens + annex mapping
            |
            v
   Knockout advancement loop with post-draw resolver
            |
            v
   Round indicators -> marginal probabilities by team
```

The data path above matches the current fixture and model contracts already in repo. [VERIFIED: data/external/fixture_2026.csv, src/cdd_mundial/models/dixon_coles.py]

### Recommended Project Structure

```text
src/cdd_mundial/simulation/
├── state.py          # TournamentState and played-result normalization
├── rules_fifa.py     # pure standings, tie-break, best-third, slot-resolution rules
├── slots.py          # third-place annex lookup and fixture-slot parsing helpers
├── engine.py         # vectorized Monte Carlo orchestration
├── knockout.py       # post-draw advancement approximation
└── outputs.py        # probability tables and artifact shaping
tests/
├── test_rules_fifa.py
├── test_simulation_engine.py
├── test_knockout.py
└── fixtures/tournament/
```

This structure follows the repo's existing separation between data contracts and model logic. [VERIFIED: src/cdd_mundial/data, src/cdd_mundial/models]

### Pattern 1: Thin `TournamentState`

**What:** Store only played match results keyed by `match_id`, plus optional tie-break metadata that cannot be recomputed from scores alone. [VERIFIED: D-01 in 03-CONTEXT.md; ASSUMED for optional metadata]
**When to use:** Always. [VERIFIED: D-01 in 03-CONTEXT.md]
**Example:**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PlayedMatchResult:
    match_id: str
    team_a: str
    team_b: str
    goals_a: int
    goals_b: int
    fair_play_a: int | None = None
    fair_play_b: int | None = None


@dataclass(frozen=True)
class TournamentState:
    played: dict[str, PlayedMatchResult]
```

The `fair_play_*` fields are implementation-ready only if real disciplinary inputs will be available; otherwise leave them `None` and treat future fair-play as an unresolved modeling gap. [ASSUMED]

### Pattern 2: Stage-Batched Sampling

**What:** Convert stage fixtures into integer-coded arrays once, then sample goals for all unplayed matches in a stage as `shape = (n_sims, n_matches_stage)`. [ASSUMED]
**When to use:** Group stage and each knockout round. [ASSUMED]
**Example:**

```python
import numpy as np

def sample_stage_goals(lam_a, lam_b, played_mask, fixed_a, fixed_b, rng):
    goals_a = rng.poisson(lam_a, size=lam_a.shape)
    goals_b = rng.poisson(lam_b, size=lam_b.shape)
    goals_a = np.where(played_mask, fixed_a, goals_a)
    goals_b = np.where(played_mask, fixed_b, goals_b)
    return goals_a, goals_b
```

This pattern is consistent with the locked NumPy-first architecture. [VERIFIED: D-05 in 03-CONTEXT.md]

### Pattern 3: Hybrid Tie Resolver

**What:** Vectorize points, goal difference, and goals scored, then fall back to a smaller pure-Python resolver only for simulations with unresolved multi-team ties after those columns. [ASSUMED]
**When to use:** Group ranking and best-third ranking. [ASSUMED]
**Example:**

```python
def rank_group_fast(points, gd, gf):
    return np.lexsort((-gf, -gd, -points), axis=1)
```

The fallback exists because head-to-head subsets, fair play, and lots are inherently branchy. [ASSUMED]

### Anti-Patterns to Avoid

- **Rebuilding the bracket from scratch:** The fixture already encodes the official slot topology, so duplicating a second bracket map increases divergence risk. [VERIFIED: data/external/fixture_2026.csv]
- **Using tokens alone to infer third-place placement:** The token family admits multiple valid perfect matchings for every 8-group combination tested, so it is not self-sufficient. [VERIFIED: local exhaustive matching script 2026-06-12]
- **Persisting derived standings inside `TournamentState`:** That violates D-01 and creates stale-state bugs after updates. [VERIFIED: .planning/phases/03-simulador-del-torneo/03-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fixture topology | A second manual bracket constant | The existing fixture CSV and slot strings | The repo already validates them and downstream phases depend on them. [VERIFIED: data/external/fixture_2026.csv, tests/test_fixture.py] |
| Team identity resolution | New ad hoc string matching | Existing canonical `team_id` tables and resolver path | Team identity is already a hard project contract. [VERIFIED: data/external/teams.csv, src/cdd_mundial/data/contracts.py] |
| Match scoring model | A new 1/X/2 model for simulation | Existing `predict_lambdas(team_a, team_b, ctx)` contract | Phase 2 already froze that interface for Phase 3. [VERIFIED: src/cdd_mundial/models/dixon_coles.py, tests/test_dixon_coles.py] |

**Key insight:** The custom work belongs in `rules_fifa.py`, not in recreating data/model contracts that already exist. [VERIFIED: repo files cited above]

## Common Pitfalls

### Pitfall 1: Planning around an unverified annex

**What goes wrong:** The team-to-slot placement for third-placed qualifiers is guessed from the `3ABCDF`-style tokens instead of being verified against FIFA's official annex. [VERIFIED: this research artifact]
**Why it happens:** The tokens look informative, but they do not uniquely determine a matching. [VERIFIED: local exhaustive matching script 2026-06-12]
**How to avoid:** Make official annex capture the first planning task and treat slot resolution code as blocked until the lookup is archived. [ASSUMED]
**Warning signs:** More than one perfect matching exists for a qualified 8-group set. [VERIFIED: local exhaustive matching script 2026-06-12]

### Pitfall 2: Mixing rule completeness with card modeling

**What goes wrong:** "Full FIFA chain" is interpreted as "simulate yellow/red cards." [VERIFIED: D-03 in 03-CONTEXT.md]
**Why it happens:** Fair play is part of the regulatory cascade, but no card-generation model exists in current scope. [VERIFIED: .planning/REQUIREMENTS.md, .planning/phases/03-simulador-del-torneo/03-CONTEXT.md]
**How to avoid:** Implement fair-play as an input-aware rule in `rules_fifa.py`; do not promise realistic future card simulation unless a separate data/model task is added. [ASSUMED]
**Warning signs:** `TournamentState` lacks any place to carry observed disciplinary tie-break information for real played matches. [ASSUMED]

### Pitfall 3: Violating D-07/D-08 while trying to satisfy SIM-05 literally

**What goes wrong:** A plan adds explicit extra-time lambdas and separate ET score sampling. [VERIFIED: conflict between .planning/REQUIREMENTS.md and 03-CONTEXT.md]
**Why it happens:** SIM-05 still uses older wording about ET and penalties. [VERIFIED: .planning/REQUIREMENTS.md]
**How to avoid:** State explicitly that Phase 3 satisfies the requirement's behavioral intent with a compact post-draw advancement approximation rather than a separate ET model. [ASSUMED]
**Warning signs:** New code introduces ET-specific `predict_lambdas` calls or extra ET parameters. [ASSUMED]

## Code Examples

Verified repo patterns and implementation-ready sketches:

### Existing frozen scoring contract

```python
def predict_lambdas(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    ...
```

Source: `src/cdd_mundial/models/dixon_coles.py`. [VERIFIED: src/cdd_mundial/models/dixon_coles.py]

### Recommended post-draw knockout resolver

```python
def p_advance_after_90(p_win: float, p_draw: float, p_loss: float, shrink: float = 1.0) -> float:
    # strength-based split of the draw bucket, symmetric by construction
    if p_win + p_loss == 0.0:
        q = 0.5
    else:
        q = p_win / (p_win + p_loss)
    q = 0.5 + shrink * (q - 0.5)
    return p_win + p_draw * q
```

This uses only the 90-minute model and stays order-neutral because swapping the teams swaps `q` with `1-q`. [ASSUMED]

### Recommended group output aggregation

```python
def accumulate_group_marginals(rankings, n_teams):
    # rankings shape: (n_sims, 4) with team indices ordered 1st..4th
    out = np.zeros((n_teams, 4), dtype=np.int64)
    for pos in range(4):
        np.add.at(out[:, pos], rankings[:, pos], 1)
    return out
```

The same pattern extends to round-advancement indicators. [ASSUMED]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Simulate match-by-match with Python objects | Vectorized stage sampling with seeded NumPy arrays | Locked in Phase 3 context on 2026-06-12. [VERIFIED: 03-CONTEXT.md] | Better shot at the `<1 min` Monte Carlo target. [ASSUMED] |
| Recompute paths from custom bracket constants | Drive resolution from the frozen official fixture slots | Already true in the current repo. [VERIFIED: data/external/fixture_2026.csv] | Lowers mismatch risk versus a second bracket source. [VERIFIED: data/external/fixture_2026.csv] |
| Literal ET submodel | Compact post-draw advancement approximation | Locked in D-07/D-08 on 2026-06-12. [VERIFIED: 03-CONTEXT.md] | Resolves the SIM-05 conflict without expanding model scope. [ASSUMED] |

**Deprecated/outdated:**
- Treating the fixture as only a scheduling artifact is outdated for this phase because it already carries the bracket slot contract. [VERIFIED: data/external/fixture_2026.csv]

## Open Rule Conflict: SIM-05 vs D-07/D-08

The requirement text still says "modelo de tiempo extra y penales," but the locked decisions forbid separate ET lambdas and require a compact post-draw approximation. [VERIFIED: .planning/REQUIREMENTS.md, .planning/phases/03-simulador-del-torneo/03-CONTEXT.md] The clean planning interpretation is: Phase 3 must resolve knockout draws stochastically and without order bias, but it must do so using only the 90-minute model outputs already available from Phase 2. [ASSUMED] If the planner wants literal ET-score simulation, that is irreconcilable with D-07/D-08 and should be flagged as out of scope or re-decided before execution. [VERIFIED: locked decisions in 03-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Stage-batched NumPy arrays plus a rare Python fallback will hit the target performance on this machine. | Phase Requirements / Architecture Patterns | Planner may under-budget optimization work. |
| A2 | `TournamentState` should optionally carry fair-play fields for played matches if real disciplinary data will be ingested later. | Pattern 1 | API may need a small redesign once live data integration starts. |
| A3 | The compact knockout resolver should use the 90-minute non-draw strength split `p_win / (p_win + p_loss)` or a shrinkage toward `0.5`. | Code Examples / SIM-05 conflict | If rejected, a different compact rule must be chosen before implementation. |
| A4 | Fair-play should be implemented as an input-aware rule, not as a simulated card process, in Phase 3. | Common Pitfalls | Historical replay can work, but hypothetical future fair-play ties may remain approximated. |
| A5 | Official annex capture can be isolated as Plan `03-01` without blocking the rest of the architectural planning. | Summary / Official Rule Status | If official rules are harder to capture than expected, Phase 3 execution timing may slip. |

## Open Questions (RESOLVED)

1. **Where will observed fair-play data come from for live conditional runs?**
   Planning resolution: the rules API accepts observed disciplinary deductions as optional inputs for already played matches, but Phase 3 does not simulate future cards. Live disciplinary ingestion is deferred to Phase 4. [VERIFIED: revision instruction 1, D-03 in 03-CONTEXT.md]
   Implementation consequence: `TournamentState` and pure rules functions must allow optional observed fair-play values while remaining correct when those values are absent. [ASSUMED]

2. **Can the official annex be archived locally without licensing issues?**
   Planning resolution: prefer a small committed extracted rules/provenance artifact containing the official HTTPS URL, retrieval timestamp, SHA-256, article and annex references, and reviewed mapping evidence. The raw PDF may remain uncommitted if redistribution terms are unclear. [VERIFIED: revision instruction 1]
   Implementation consequence: Plan `03-01` must fail closed on provenance completeness even when the raw PDF itself is not committed. [ASSUMED]

3. **How aggressive should common-random-number reuse be across daily reruns?**
   Planning resolution: use deterministic independent RNG streams keyed by stable `match_id` plus a simulation/version seed. Document the exact `SeedSequence` approach in the implementation plan so unresolved matches retain comparable randomness across state updates. [VERIFIED: revision instruction 1]
   Implementation consequence: the engine plan must test that fixing earlier matches does not perturb still-unplayed match streams under the same version seed. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All Phase 3 code | ✓ | `3.12.13` | — |
| NumPy | Monte Carlo engine | ✓ | `2.4.6` | None worth planning around |
| pandas | Fixture/state/output shaping | ✓ | `2.3.3` | Minimal CSV-only fallback is possible but not useful |
| pytest | Rule and engine validation | ✓ | `8.4.2` | — |

**Missing dependencies with no fallback:**
- None found in the current local environment for planning Phase 3. [VERIFIED: .venv/python.exe, pyproject.toml]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest 8.4.2` [VERIFIED: .venv/python.exe] |
| Config file | `pyproject.toml` [VERIFIED: pyproject.toml] |
| Quick run command | `.venv\\python.exe -m pytest -q -p no:cacheprovider tests/test_rules_fifa.py tests/test_knockout.py` [ASSUMED] |
| Full suite command | `.venv\\python.exe -m pytest -q -p no:cacheprovider` [VERIFIED: pyproject.toml plus local venv path] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIM-01 | Group ranking cascade, best-third ranking, R32 slot assignment | unit | `.venv\\python.exe -m pytest -q -p no:cacheprovider tests/test_rules_fifa.py -x` | ❌ Wave 0 |
| SIM-02 | Performance and seeded reproducibility | integration | `.venv\\python.exe -m pytest -q -p no:cacheprovider tests/test_simulation_engine.py -x` | ❌ Wave 0 |
| SIM-03 | Played results stay fixed | unit | `.venv\\python.exe -m pytest -q -p no:cacheprovider tests/test_simulation_engine.py::test_played_matches_are_fixed -x` | ❌ Wave 0 |
| SIM-04 | Advancement and group-position marginals | unit | `.venv\\python.exe -m pytest -q -p no:cacheprovider tests/test_outputs.py -x` | ❌ Wave 0 |
| SIM-05 | Unbiased post-draw knockout advancement | unit | `.venv\\python.exe -m pytest -q -p no:cacheprovider tests/test_knockout.py::test_order_bias_is_absent -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** targeted Phase 3 tests. [ASSUMED]
- **Per wave merge:** full Phase 3 test set plus existing fixture and Dixon-Coles contract tests. [ASSUMED]
- **Phase gate:** full suite green before `$gsd-verify-work`. [VERIFIED: workflow intent from project process]

### Wave 0 Gaps

- [ ] `tests/test_rules_fifa.py` — exact tie cascade, historical case fixtures, best-third ranking, annex-driven slot mapping. [ASSUMED]
- [ ] `tests/test_simulation_engine.py` — fixed-state conditioning, seed reproducibility, basic speed guard. [ASSUMED]
- [ ] `tests/test_knockout.py` — draw-resolution symmetry and 50/50 sanity under identical strengths. [ASSUMED]
- [ ] `tests/fixtures/tournament/` — synthetic multi-way ties plus archived regulatory excerpts or checksum metadata. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user-auth flow in this phase. [VERIFIED: phase scope] |
| V3 Session Management | no | No session state in this phase. [VERIFIED: phase scope] |
| V4 Access Control | no | No multi-user authorization logic in this phase. [VERIFIED: phase scope] |
| V5 Input Validation | yes | Keep strict canonical IDs and schema checks on any new state/output tables. [VERIFIED: src/cdd_mundial/data/contracts.py] |
| V6 Cryptography | no | No cryptographic processing is required by the current simulator scope. [VERIFIED: phase scope] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unknown or malformed team IDs entering state | Tampering | Reuse canonical `team_id` validation and fail loudly. [VERIFIED: data/external/teams.csv, contracts.py] |
| Silent drift between fixture slots and slot-resolution code | Tampering | Resolve against fixture tokens, not duplicated constants, and test every slot family. [VERIFIED: data/external/fixture_2026.csv] |
| Non-reproducible simulation runs | Repudiation | Seed `numpy.random.Generator` deterministically and test for stable outputs. [ASSUMED] |

## Sources

### Primary (HIGH confidence)

- `data/external/fixture_2026.csv` - frozen 104-match tournament skeleton, authoritative slot strings, FIFA source URL provenance. [VERIFIED: repo file]
- `src/cdd_mundial/data/ingest_fixture.py` - enforced fixture structure and slot integrity contract. [VERIFIED: repo file]
- `tests/test_fixture.py` - current guarantees about match counts, slot preservation, and FIFA source URL. [VERIFIED: repo file]
- `src/cdd_mundial/models/dixon_coles.py` - frozen `predict_lambdas(team_a, team_b, ctx)` contract. [VERIFIED: repo file]
- `tests/test_dixon_coles.py` - explicit contract tests for model signature and `ctx` semantics. [VERIFIED: repo file]
- `pyproject.toml` and local `.venv` package versions - installed runtime and test framework. [VERIFIED: repo file, .venv/python.exe]
- `https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures` - official fixture source already embedded in repo provenance. [CITED: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures]

### Secondary (MEDIUM confidence)

- `https://en.wikipedia.org/wiki/2026_FIFA_World_Cup` - secondary indication that a 2025 FIFA regulations document and annex exist; not sufficient for implementation authority. [CITED: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup]

### Tertiary (LOW confidence)

- None intentionally relied upon for implementation decisions. [VERIFIED: this research artifact]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - fully verified from `pyproject.toml` and the local `.venv`. [VERIFIED: pyproject.toml, .venv/python.exe]
- Architecture: MEDIUM - strongly constrained by existing repo contracts, but performance and fallback rates remain unmeasured in this session. [VERIFIED: repo files plus A1]
- Pitfalls: HIGH - the third-place assignment ambiguity was verified locally, and the SIM-05 wording conflict is explicit in project docs. [VERIFIED: local exhaustive matching script 2026-06-12, REQUIREMENTS.md, 03-CONTEXT.md]

**Research date:** 2026-06-12 [VERIFIED: current session date]
**Valid until:** 2026-06-19 for unresolved regulation access, 2026-07-12 for local architecture guidance. [ASSUMED]
