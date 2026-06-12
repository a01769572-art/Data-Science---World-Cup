# Phase 2: Modelos Baseline (Elo + Dixon-Coles) - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Construir los modelos estructurales que producen **λ (goles esperados)** y **P(W/D/L)** a partir del histórico martj42:

1. **Elo dinámico custom** — recomputado desde cero sobre los 49,405 partidos históricos con K por tipo de torneo, ventaja de anfitrión condicional a sede, y multiplicador de margen. Entrega `elo_ratings.parquet` con el rating current de cada selección.
2. **Dixon-Coles (Poisson bivariado)** — ajustado sobre el histórico con decaimiento temporal exponencial; expone el contrato `predict_lambdas(team_a, team_b, ctx) -> (λ_home, λ_away)`. Entrega también probabilidades W/D/L derivadas de la matriz de marcadores.
3. **Validación temporal** — log-loss, Brier y RPS sobre 4 torneos holdout; el baseline debe vencer a los naïve (uniforme, solo-ranking-FIFA).
4. **Notebook didáctico** — deriva la corrección ρ, la función de log-likelihood y el gradiente; estructura obligatoria MD→código→MD.

**Entregable de contrato (Phase 3 lo consume):** `predict_lambdas(team_a, team_b, ctx)` congelado al final de esta fase.

</domain>

<decisions>
## Implementation Decisions

### Elo dinámico custom (MODEL-01)

- **D-01: K por tipo de torneo** — Valores fijos de la literatura World Football Elo (WFE). No se optimiza K en esta fase para priorizar velocidad de entrega antes del 27-jun.
  - Amistosos internacionales: K = 20
  - Clasificatorias y torneos confederados menores: K = 40
  - Copa Confederaciones, Copa América, Eurocopa, Copa Africana, Copa Asiática: K = 60
  - Copa del Mundo (grupos, eliminatorias): K = 60
  *(Ajustar la tabla si el formato WFE publicado usa valores distintos — seguir la fuente canónica WFE.)*

- **D-02: Ventaja de anfitrión** — Constante aditiva fija **solo para MEX, USA y CAN** cuando juegan en el Mundial 2026 (sede en sus países). Partidos fuera del torneo se tratan como neutrales con ventaja = 0. El valor de la constante sigue la convención WFE (~+100 puntos Elo al equipo local).

- **D-03: Multiplicador de margen de victoria** — Fórmula WFE estándar:
  `margin_factor = log(|diff_goles| + 1) * (2.2 / (Δ_Elo_winner * 0.001 + 2.2))`
  Suaviza goleadas sin sobreponderar; la corrección por Δ_Elo evita que equipos muy superiores ganen puntos excesivos por margen.

- **D-04: Punto de inicio de ratings** — 1000 puntos para todos al comienzo (o usar snapshot de eloratings.net como warm-start opcional si la recomputación desde cero tarda demasiado — decisión de implementación del planner).

- **D-05: Shootout / penales** — El resultado de registro (resultado oficial de 90+ext min, sin contar penales) se usa para la actualización de Elo. Los penales NO cambian el marcador de goles para Elo (confirmar con campo `shootout` de martj42).

### Dixon-Coles (MODEL-02 / MODEL-03)

- **D-06: Decaimiento temporal** — Exponencial, siguiendo el paper original: `w(t) = exp(-ξ * Δt)` con `ξ` tal que el half-life sea ~2 años (≈ 0.0018 por día). Este valor es el estándar de la literatura Dixon-Coles y es justificable en el notebook.

- **D-07: Frontera de entrenamiento** — **TODO el histórico disponible hasta hoy**, incluyendo los partidos del Mundial 2026 ya jugados. No hay leakage: el entrenamiento es previo a cada ejecución del pronóstico diario y los partidos usados son resultado conocido, no futuro.

- **D-08: Corrección ρ de marcadores bajos** — Implementar la corrección Dixon-Coles original para (0-0), (1-0), (0-1), (1-1). El valor de ρ se estima por MLE junto con los parámetros de ataque/defensa.

- **D-09: Contrato `predict_lambdas`** — Firma congelada:
  ```python
  def predict_lambdas(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
      """
      Returns (lambda_a, lambda_b): expected goals for team_a and team_b.
      ctx keys: neutral (bool), date (datetime), tournament_type (str)
      team IDs are canonical slugs from teams.csv.
      """
  ```
  Phase 3 (simulador) se construye contra esta firma — **no modificar sin versionar**.

- **D-10: Probabilidades W/D/L** — Derivadas integrando la matriz de marcadores P(i, j) hasta un máximo razonable (e.g., goles 0-10 por equipo), con la corrección ρ aplicada. **NO** se usa un logistic sobre Elo para W/D/L en esta fase — la distribución sale del modelo de goles.

### Validación temporal (MODEL-04)

- **D-11: Holdouts** — 4 torneos fijos:
  1. Copa del Mundo 2018 (64 partidos)
  2. Copa del Mundo 2022 (64 partidos)
  3. Eurocopa 2024 (51 partidos)
  4. Copa América 2024 (32 partidos)
  El modelo se ajusta con datos **anteriores** a cada torneo holdout (corte estricto por fecha de inicio).

- **D-12: Métricas** — log-loss (principal), Brier score, RPS. Reportar también vs. baselines naïve: distribución uniforme (33/33/33), solo-Elo (sin Dixon-Coles), solo-ranking-FIFA.

- **D-13: Gate de aceptación** — El baseline pasa si vence a TODOS los baselines naïve en log-loss promediado sobre los 4 holdouts. Si no pasa, se documenta y se continúa de todas formas (el ML de Phase 5 puede mejorar).

### Notebooks didácticos

- **D-14: Nivel matemático** — **Derivar matemática core**: la corrección ρ de Dixon-Coles, la función de log-likelihood completa, y el gradiente analítico (o al menos la estructura de la optimización). Nivel ingeniería/maestría. Diferenciador de portafolio.
- **D-15: Estructura de notebook** — Obligatoria: celda MD (qué/por qué) → celda código → celda MD (interpretación). Igual que Phase 1. Los notebooks importan funciones de `cdd_mundial.*`, no reimplementan lógica.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Datos de entrada (Phase 1 outputs)
- `data/processed/matches_historical.parquet` — Base histórica 49,405 partidos, esquema pandera validado
- `data/external/teams.csv` — Tabla canónica de 48 selecciones con slugs estables
- `data/external/team_aliases.csv` — Alias por fuente (martj42, eloratings, fifa, fixture, odds)
- `data/external/elo_snapshot.parquet` — Snapshot Elo actual de eloratings.net (warm-start opcional para MODEL-01)
- `data/external/fixture_2026.csv` — 104 partidos con match IDs, grupos, kickoffs UTC, sedes

### Contratos de código existentes
- `src/cdd_mundial/data/contracts.py` — Esquemas Pandera; el modelo debe respetar los tipos canónicos
- `src/cdd_mundial/data/identities.py` — Resolver slugs → IDs canónicos; usar para normalizar equipo input
- `src/cdd_mundial/data/ingest_martj42.py` — Semántica de columnas: `home_score`/`away_score` son FT+ET sin penales; `shootout` indica si hubo tanda

### Referencias metodológicas
- Paper original Dixon-Coles (1997): "Modelling Association Football Scores and Inefficiencies in the British Football Betting Market" — referencia canónica para corrección ρ, MLE, y decaimiento temporal
- World Football Elo Ratings methodology: https://www.eloratings.net/about — K-factors por tipo de torneo, multiplicador de margen, fórmula de ventaja local

### Requerimientos
- `.planning/REQUIREMENTS.md` §Modelos baseline — MODEL-01, MODEL-02, MODEL-03, MODEL-04
- `.planning/ROADMAP.md` §Phase 2 — Success criteria y dependencias

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/cdd_mundial/data/identities.py`: `resolve_team(name, source)` — normaliza nombres a slugs canónicos; usar en predict_lambdas para validar inputs
- `src/cdd_mundial/data/contracts.py`: Pandera schemas con `strict=True, coerce=True` — el modelo debe producir DataFrames que pasen estos contratos
- `src/cdd_mundial/data/provenance.py`: `record_provenance(path, metadata)` — usar para registrar artefactos de modelo (elo_ratings.parquet, dc_params.json)
- `src/cdd_mundial/data/http.py`: HTTP helper con timeouts y reintentos — ya disponible si se necesita descargar datos externos

### Established Patterns
- **Inmutabilidad de raw**: `data/raw/` nunca se toca; parámetros de modelo → `data/processed/models/` o `data/external/`
- **Test con fixtures**: `tests/fixtures/` contiene partidos comprometidos para tests sin red; el modelo debe tener tests unitarios con datos comprometidos
- **Cobertura de identidades**: cualquier función que acepte nombres de equipo DEBE rechazar nombres desconocidos/ambiguos (patrón establecido en Phase 1)
- **Notebooks ejecutables**: el notebook debe correr limpio con `jupyter nbconvert --to notebook --execute`

### Integration Points
- **→ Phase 3 (simulador)**: `predict_lambdas(team_a, team_b, ctx)` es EL punto de integración. Phase 3 se construye con un stub de esta función; la firma no puede cambiar post-Phase 2.
- **→ Phase 4 (pipeline diario)**: el Elo necesita actualizarse tras cada jornada con los resultados reales; el diseño debe permitir re-ajuste incremental (o re-fit completo desde raw, que es más simple y reproducible)
- **→ Phase 5 (ML)**: el Elo rating diferencial y λ de Dixon-Coles son features ML-01; la API debe ser importable desde el módulo sin re-ajustar el modelo

</code_context>

<specifics>
## Specific Ideas

- El multiplicador de margen WFE tiene la corrección por Δ_Elo (`2.2 / (Δ_Elo * 0.001 + 2.2)`) — incluir esta versión completa, no solo `log(diff+1)`.
- La ventaja de anfitrión para MEX/USA/CAN es específica del Mundial 2026 — puede ser un flag en `ctx` o una tabla de sedes.
- El notebook debe incluir un diagrama de calibración (reliability diagram) sobre los holdouts para visualizar si las probabilidades W/D/L son honestas.
- La tasa de empates Dixon-Coles debe caer en el rango 24–28% para partidos neutrales entre equipos de nivel similar — incluir esto como check de sanidad en el notebook.

</specifics>

<deferred>
## Deferred Ideas

- **Optimización de K**: grid-search o scipy.optimize de K por categoría de torneo sobre los holdouts — aplazado al cierre de Phase 2 si hay tiempo, o Phase 5/post-mortem.
- **Re-entrenamiento incremental (online Elo)**: actualizar solo los partidos nuevos sin re-correr todo el histórico — aplazado a Phase 4/6 si el re-fit completo es demasiado lento.
- **De-margin multi-bookmaker / método Shin**: evaluación de fuentes de cuotas adicionales — aplazado a v2 (EVAL-V2-03).
- **Valor de plantilla (Transfermarkt) como feature**: aplazado a v2 (DATA-V2-01).

</deferred>

---

*Phase: 02-modelos-baseline*
*Context gathered: 2026-06-12*
