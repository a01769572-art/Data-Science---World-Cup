# Phase 3: Simulador del Torneo - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Construir el motor de simulacion del Mundial 2026 que consume el fixture congelado y el contrato `predict_lambdas(team_a, team_b, ctx)` para producir probabilidades de avance del torneo completo, condicionado al estado real del torneo.

El alcance incluye:
1. Rules engine del formato FIFA 2026: tablas de grupo, desempates, ranking de mejores terceros y asignacion a R32.
2. Simulacion Monte Carlo vectorizada del torneo completo.
3. Estado condicional del torneo: los partidos ya jugados se fijan y solo se simula lo restante.
4. Outputs por seleccion: probabilidades de posicion de grupo y de avanzar por ronda.
5. Resolucion de eliminatorias despues de un empate a 90 minutos con una aproximacion compacta.

</domain>

<decisions>
## Implementation Decisions

### Tournament state and match-result contract
- **D-01:** `TournamentState` guarda solo resultados ya jugados. No debe persistir tablas derivadas ni estados intermedios redundantes; esos se recomputan desde fixture + resultados fijados.
- **D-02:** El contrato interno para resultados jugados debe usar `team_a` / `team_b`, no `home_*` / `away_*`. La ventaja de anfitrion se modela solo via `ctx`, no via nombres de columnas.

### Rules engine scope
- **D-03:** El rules engine sigue el Art. 13 oficial verificado en `03-01`: criterios head-to-head primero, reaplicacion residual, criterios globales, conduct score y, como fallback final, ediciones sucesivas del ranking FIFA. No existe `drawing of lots` en la regla oficial 2026.
- **D-04:** El criterio de exito del rules engine se centra en que los criterios queden implementados correctamente en funciones puras y testeados, consumiendo la evidencia regulatoria y el mapping oficial fijados por `03-01`.

### Monte Carlo architecture
- **D-05:** El simulador se diseña desde el inicio para miles de iteraciones con `numpy`. No se prioriza una version naive partido-por-partido como arquitectura principal.
- **D-06:** El motor debe operar sobre el fixture oficial y sus `slot` references existentes (`1A`, `3CDFGH`, `W74`, etc.), resolviendo el bracket sobre esa estructura en vez de redefinirla.

### Knockout resolution
- **D-07:** La resolucion de eliminatorias despues de un empate a 90 minutos usa una aproximacion compacta. No se modela explicitamente tiempo extra con lambdas separadas en esta fase.
- **D-08:** La aproximacion compacta puede convertir el empate a 90 minutos en una probabilidad de avanzar posterior, preservando neutralidad y evitando sesgo de orden entre equipos.

### Simulation outputs
- **D-09:** Phase 3 debe producir las probabilidades de avance por seleccion: `P(R32)`, `P(R16)`, `P(QF)`, `P(SF)`, `P(Final)`, `P(Campeon)`.
- **D-10:** Phase 3 tambien debe producir probabilidades marginales de posicion de grupo por seleccion: `P(1st)`, `P(2nd)`, `P(3rd)`, `P(4th)`.
- **D-11:** No se requieren tablas conjuntas completas de configuraciones de grupo en esta fase; solo marginals por equipo.

### Simulation notebook
- **D-12:** Phase 3 entrega un notebook integral `notebooks/03_simulador_torneo.ipynb` ademas de los modulos productivos `.py`.
- **D-13:** El notebook es una capa de orquestacion didactica: importa las funciones productivas de `cdd_mundial.simulation` y no redefine el motor, las reglas ni la logica de outputs.
- **D-14:** El notebook recorre estado, reglas, simulacion Monte Carlo y analisis; mantiene la estructura obligatoria Markdown `What and why` -> codigo -> Markdown `Interpretation`.
- **D-15:** El notebook se versiona ejecutado con una demostracion rapida reproducible, tablas, diagnosticos y graficos. Una celda de configuracion permite solicitar 10k o 100k simulaciones sin forzar esas corridas pesadas al ejecutar el notebook por defecto.

### the agent's Discretion
- Elegir la representacion concreta en memoria para `TournamentState`, siempre que cumpla con el principio de almacenar solo resultados ya jugados.
- Elegir la forma numerica exacta de la aproximacion compacta para desempatar eliminatorias despues de 90 minutos, siempre que no introduzca un pseudo-modelo detallado de tiempo extra.
- Elegir la estrategia de vectorizacion y acumulacion de resultados mas simple que cumpla la meta de rendimiento.
- Elegir el tamano exacto de la demostracion rapida del notebook, siempre que sea suficientemente pequeno para ejecucion cotidiana y produzca resultados no vacios.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and phase scope
- `.planning/ROADMAP.md` - Phase 3 goal, dependencies, success criteria, and hard timeline.
- `.planning/REQUIREMENTS.md` - `SIM-01` through `SIM-05` define the required simulator behavior.
- `.planning/STATE.md` - current blockers and carry-forward decisions, including the missing official FIFA regulations verification.
- `.planning/PROJECT.md` - project constraints, timeline pressure, and the design reference note.
- `PROYECTO_MUNDIAL_2026.md` - prior design reference called out in `PROJECT.md`; downstream planning should read it if present before locking architecture.

### Data and tournament structure
- `data/external/fixture_2026.csv` - official 104-match tournament skeleton with group assignments, knockout slots, venues, and kickoff timestamps.
- `data/external/teams.csv` - canonical team identities for all 48 participants.
- `data/external/team_aliases.csv` - cross-source alias mapping when results or future live data need resolution.

### Existing code contracts
- `src/cdd_mundial/models/dixon_coles.py` - frozen `predict_lambdas(team_a, team_b, ctx)` contract and current lambda semantics.
- `src/cdd_mundial/models/__init__.py` - exported model interface consumed by downstream phases.
- `src/cdd_mundial/data/ingest_fixture.py` - validated fixture loading logic and slot integrity checks.
- `src/cdd_mundial/data/contracts.py` - fixture/data schema constraints already enforced in the repo.

### Existing tests and examples
- `tests/test_fixture.py` - current guarantees about fixture counts, group structure, and knockout slot preservation.
- `tests/test_dixon_coles.py` - contract tests for `predict_lambdas` and context semantics.
- `notebooks/01_data_foundation.ipynb` - documented fixture assumptions and tournament structure narrative.
- `notebooks/02_modelos_baseline.ipynb` - documented baseline contract consumed by the simulator.
- `tests/test_notebooks.py` - structural pedagogy, hygiene, production-import, and deterministic-kernel gates that the Phase 3 notebook must extend.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/cdd_mundial/models/dixon_coles.py`: production `predict_lambdas` loader and W/D/L helpers already exist; Phase 3 should consume them, not recreate scoring logic.
- `src/cdd_mundial/data/ingest_fixture.py`: fixture loader already validates 72 group matches, 12 groups A-L, canonical participants, and knockout slot references.
- `src/cdd_mundial/data/contracts.py`: schema layer already defines valid fixture stages and nullable team fields for unresolved knockout slots.

### Established Patterns
- Canonical team identity is slug-based and enforced across the project; simulator inputs should reject unknown teams rather than infer.
- The repo already treats tournament structure as validated data plus pure transformations; Phase 3 should keep rules logic as pure functions where possible.
- Existing model code uses `team_a` / `team_b` semantics with `ctx["neutral"]` controlling host advantage; simulator code should preserve that convention.
- Project notebooks import production packages, do not redefine functions/classes, and enforce Markdown `What and why` -> code -> Markdown `Interpretation`.

### Integration Points
- Phase 3 plugs directly into `predict_lambdas(team_a, team_b, ctx)` from Phase 2.
- Phase 4 will consume Phase 3 outputs for daily reports and snapshots, so simulator outputs need stable, tabular probability artifacts.
- The existing fixture slots (`3CDFGH`, `W74`, `L101`) define the bracket resolution interface for the rules engine.
- `notebooks/03_simulador_torneo.ipynb` will import the public `cdd_mundial.simulation` API and present the same counts/tables tested by the engine and output modules.

</code_context>

<specifics>
## Specific Ideas

- Use the official fixture slot strings as the source of truth for knockout mapping instead of duplicating the bracket in separate constants unless tests prove a normalization layer is necessary.
- Keep host advantage contextual rather than encoding a fake home/away worldview into the state model.
- The first planning task should fetch, pin, and cite the official FIFA 2026 regulations PDF locally because `STATE.md` marks it as an unresolved blocker for tie-break order and best-third assignment.
- Group outputs should be marginal probabilities per team, not full joint state enumerations.
- The notebook should explain the flow end to end, but every reusable computation remains in `src/cdd_mundial/simulation/`.
- The committed notebook keeps outputs from the quick deterministic run; large 10k/100k runs are opt-in through a visible configuration cell.

</specifics>

<deferred>
## Deferred Ideas

- Full joint group outcome tables - deferred beyond Phase 3; not required for roadmap success criteria.
- Explicit extra-time scoring submodel - deferred; Phase 3 uses the compact post-draw advancement approximation instead.
- Richer state snapshots that cache derived standings after every simulated match - deferred unless performance profiling proves recomputation is the bottleneck.

</deferred>

---

*Phase: 03-simulador-del-torneo*
*Context gathered: 2026-06-13*
