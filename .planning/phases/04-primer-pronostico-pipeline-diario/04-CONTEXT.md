# Phase 04: Primer Pronostico + Pipeline Diario - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Construir el pipeline oficial de publicacion diaria del baseline ya operativo: ingestar el estado real del torneo, refrescar el estado/modelo reproducible, re-simular solo lo que falta, congelar un snapshot oficial append-only pre-kickoff y generar un reporte publicable derivado de ese snapshot.

El alcance incluye:
1. Ingesta canónica de resultados 2026 con fallback manual no bloqueado por scrapers.
2. Corrida oficial reproducible por script/comando, con notebook solo como interfaz.
3. Snapshot append-only versionado en git con metadata suficiente para auditoría.
4. Reporte HTML estático diario derivado del snapshot oficial.
5. Tracker de calibración en vivo contra benchmark de mercado, con unidad base por partido.

</domain>

<decisions>
## Implementation Decisions

### Resultados en vivo
- **D-01:** `results_2026.csv` es la fuente canónica y versionable de resultados jugados para la corrida diaria. Cualquier scraper externo solo puede validar o asistir; nunca sustituye la autoridad del CSV.
- **D-02:** El sistema puede re-simular en cualquier momento cuando cambie el estado real del torneo, pero el snapshot oficial publicable se genera una vez por jornada o antes del bloque relevante de partidos y se commitea append-only antes del kickoff correspondiente.
- **D-03:** `results_2026.csv` se mantiene minimalista, con solo las columnas necesarias para construir `TournamentState`. La metadata operativa vive en artefactos separados.
- **D-04:** Si existe scraper auxiliar, se usa como verificación contra el CSV canónico. Si hay discrepancias, la corrida oficial falla o exige corrección explícita; no publica silenciosamente.
- **D-05:** Si `results_2026.csv` está incompleto para partidos ya jugados, el pipeline falla por defecto. Solo puede continuar con override explícito y trazable.

### Refresh del modelo y corrida oficial
- **D-06:** La corrida oficial usa modo mixto: el modo publicable rehace/refresca desde artefactos canónicos y estado observado, mientras que un modo rápido incremental puede existir solo para exploración, nunca como publicación oficial.
- **D-07:** El pipeline oficial vive en script/comando reproducible; el notebook de Jupyter puede dispararlo e inspeccionarlo, pero no define por sí solo el proceso oficial.

### Snapshot append-only
- **D-08:** Cada snapshot oficial es rico: incluye probabilidades por equipo, pronósticos del bloque próximo y metadata suficiente para reconstruir exactamente la corrida oficial.
- **D-09:** Cada snapshot vive en una carpeta propia append-only con varios archivos separados, no en un único archivo monolítico.
- **D-10:** `metadata.json` debe incluir obligatoriamente el commit hash del código usado para generar el snapshot.
- **D-11:** Por defecto, la publicación oficial exige worktree limpio. Si el repo está dirty, solo continúa con override explícito y `metadata.json` debe registrar `dirty=true` y los archivos modificados relevantes.
- **D-12:** Los datos canónicos del snapshot siempre se versionan; el reporte renderizado se guarda además cuando la corrida corresponda a una publicación oficial.
- **D-13:** `model_version` sigue un esquema semántico por familia + fecha + commit corto, por ejemplo `baseline-v1-2026-06-14-abc1234`.

### Reporte diario
- **D-14:** El reporte oficial de la fase es un HTML estático generado automáticamente. Puede combinar `matplotlib`/`seaborn` y componentes `Plotly` cuando eso mejore claridad o exploración.
- **D-15:** El HTML diario incluye obligatoriamente resumen ejecutivo, pronósticos del bloque próximo, probabilidades del torneo, evolución temporal y una nota metodológica corta. La sección detallada de grupos queda opcional según la jornada.
- **D-16:** La parte superior del HTML diario usa un resumen mixto: KPIs clave y un primer bloque visual combinando próximos partidos y probabilidades destacadas del torneo.
- **D-17:** La evolución temporal compara cada snapshot tanto contra el snapshot inmediatamente anterior como contra el primer snapshot publicado del proyecto.

### Tracker de calibración vs mercado
- **D-18:** El tracker de calibración en vivo guarda datos canónicos por partido; las vistas por jornada son agregaciones derivadas para visualización.
- **D-19:** El benchmark de mercado es un agregado canónico de múltiples bookmakers válidos, no una casa fija ni una selección oportunista.
- **D-20:** La referencia principal del benchmark usa la mediana de probabilidades de-margined entre bookmakers válidos; el promedio simple se conserva como diagnóstico auxiliar.
- **D-21:** Para evaluación y comparación en vivo, el benchmark principal se congela con la cuota capturada al momento de publicar el snapshot oficial, no con una captura posterior.
- **D-22:** El reporte diario muestra métricas acumuladas de calibración y una serie temporal de evolución; no se limita a un agregado por jornada sin detalle base.

### the agent's Discretion
- Elegir el layout exacto de carpetas y nombres de archivos dentro de cada snapshot, siempre que preserve append-only, separación entre metadata y tablas, y lectura clara por humanos y scripts.
- Elegir el balance exacto entre visuales `matplotlib`/`seaborn` y `Plotly` dentro del HTML, siempre que el resultado final siga siendo estático, publicable y reproducible.
- Elegir qué elementos de grupos incluir dinámicamente según la relevancia competitiva de la jornada, sin convertir esa sección en obligatoria para todas las corridas.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and scope
- `.planning/ROADMAP.md` - Phase 4 goal, hard deadline before 2026-06-27, and the success criteria for the one-command daily pipeline, append-only snapshots, reporting, and live calibration.
- `.planning/REQUIREMENTS.md` - `DATA-06`, `LIVE-01` through `LIVE-04`, and `DOC-02` define the concrete acceptance surface for this phase.
- `.planning/PROJECT.md` - project-level reproducibility constraints, portfolio/publication goals, and the updated decision that static matplotlib-only output is no longer a hard constraint for this phase.
- `.planning/STATE.md` - current handoff state after Phase 03 completion and carry-forward operational constraints.

### Existing model and simulation contracts
- `src/cdd_mundial/models/dixon_coles.py` - frozen production `predict_lambdas(team_a, team_b, ctx)` contract plus persisted production-model loading behavior.
- `src/cdd_mundial/models/__init__.py` - exported model surface currently consumed by the rest of the project.
- `src/cdd_mundial/models/validation.py` - current production materialization flow for validation/model artifacts; relevant precedent for reproducible dated artifacts and provenance.
- `src/cdd_mundial/simulation/state.py` - canonical `TournamentState` and `PlayedMatchResult` contract the new results-ingestion layer must satisfy.
- `src/cdd_mundial/simulation/engine.py` - deterministic conditioned tournament re-simulation with CRN keyed by `match_id`; Phase 4 must feed this engine rather than replacing it.
- `src/cdd_mundial/simulation/outputs.py` - stable per-team advancement and group-position probability tables already available for snapshots and reports.

### Data and benchmark inputs
- `data/external/fixture_2026.csv` - frozen official fixture with `match_id`, kickoff timestamps, and stage structure; authoritative match skeleton for results ingestion and next-block reporting.
- `data/external/odds_2026_template.csv` - approved manual fallback shape for odds benchmark data.
- `data/processed/odds_2026.parquet` - current canonical de-margined odds benchmark artifact; relevant baseline for market-comparison design.
- `src/cdd_mundial/data/ingest_odds.py` - existing odds benchmark semantics, provider constraints, de-margining logic, and fixture matching rules.
- `data/metadata/odds_provider_policy.json` - policy and storage constraints for bookmaker raw payloads.

### Existing tests and notebooks
- `tests/test_tournament_state.py` - fail-loud expectations around played-result validation and conditioned state construction.
- `tests/test_simulation_engine.py` - guarantees around deterministic conditioned re-simulation and fixed played matches.
- `tests/test_simulation_outputs.py` - guarantees around output table semantics that the snapshot layer should preserve.
- `tests/test_odds.py` - existing benchmark integrity rules that constrain any market-comparison tracker.
- `tests/test_validation_temporal.py` - precedent for log-loss/RPS reporting structure.
- `notebooks/03_simulador_torneo.ipynb` - current notebook pattern for using production APIs rather than redefining logic in notebooks.
- `README.md` - current public-facing framing of the project and roadmap, which Phase 4 publication artifacts must remain consistent with.

### Missing design reference
- `.planning/PROJECT.md` references `PROYECTO_MUNDIAL_2026.md` as a prior design document, but that file was not present in the current workspace during discussion. Downstream planning should not assume it exists unless restored explicitly.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/cdd_mundial/simulation/state.py`: already defines the exact played-results contract and validation behavior needed for `results_2026.csv`.
- `src/cdd_mundial/simulation/engine.py`: already supports conditioned re-simulation with fixed played matches and deterministic CRN streams, so Phase 4 should orchestrate it rather than redesign it.
- `src/cdd_mundial/simulation/outputs.py`: already yields stable tabular probabilities for team-level advancement and group positions.
- `src/cdd_mundial/data/ingest_odds.py`: already contains benchmark ingestion, de-margining, fixture linking, and fallback semantics that can feed the live calibration tracker.
- `src/cdd_mundial/models/validation.py`: already implements dated artifact materialization and provenance-oriented output patterns that can inform snapshot metadata.
- `notebooks/03_simulador_torneo.ipynb`: already demonstrates the repo pattern of notebooks as orchestration/explanation layers over `src/` APIs.

### Established Patterns
- Raw or operationally sensitive inputs are separated from publishable derived artifacts; Phase 4 should keep that split for bookmaker data, results ingestion, snapshots, and reports.
- Production logic belongs in `src/`; notebooks import and orchestrate it rather than defining authoritative behavior.
- Reproducibility matters more than runtime cleverness: deterministic seeds, explicit dated artifacts, and fail-loud validation are already established norms in the repo.
- Public outputs are portfolio artifacts, so publication traces need to be honest, inspectable, and stable over time.

### Integration Points
- The new results ingestion layer must end in `TournamentState.from_results(...)`.
- The refreshed daily run must continue to use `predict_lambdas(...)` from the persisted production model surface.
- Snapshot team tables should derive from `advancement_table(...)` and, when relevant, `group_position_table(...)`.
- Market calibration must consume the canonical odds benchmark semantics already defined in `ingest_odds.py`, rather than inventing a second benchmark format.
- The HTML report should consume the snapshot artifacts, not rerun independent business logic that could drift from the official published snapshot.

</code_context>

<specifics>
## Specific Ideas

- The official publication chain is conceptually: `results_2026.csv` -> validate/construct `TournamentState` -> refresh official model state -> re-simulate future matches only -> write append-only snapshot -> render HTML report -> commit official publication artifacts.
- Snapshot structure should likely resemble `snapshots/<timestamp>/metadata.json`, `team_probabilities.parquet`, `upcoming_match_predictions.parquet`, plus rendered-report files when the run is an official publication.
- The same architecture should support ad hoc exploratory reruns without making those exploratory runs equivalent to official published snapshots.
- The first public/LinkedIn-facing publication should happen as soon as the first end-to-end Phase 4 official run is reproducible, pre-kickoff, and visually understandable; not after waiting for multiple jornadas.

</specifics>

<deferred>
## Deferred Ideas

- Publish after every single match instead of by jornada or relevant match block - deferred because it increases operational noise and snapshot churn beyond the Phase 4 requirement.
- Full interactive dashboard product surface - deferred; the report output for this phase is static HTML, not a persistent app.
- Making incremental model refresh the authoritative publication path - deferred; official runs stay rebuild/re-fit based.

</deferred>

---

*Phase: 04-primer-pronostico-pipeline-diario*
*Context gathered: 2026-06-13*
