# Phase 2: Modelos Baseline (Elo + Dixon-Coles) - Research

**Researched:** 2026-06-12
**Domain:** Modelado estructural de fútbol (Elo dinámico + Poisson bivariado Dixon-Coles) con validación temporal
**Confidence:** HIGH (datos y entorno verificados en vivo; fórmulas canónicas verificadas contra fuentes; 4 ambigüedades de decisión flageadas explícitamente)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Elo dinámico custom (MODEL-01)

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

#### Dixon-Coles (MODEL-02 / MODEL-03)

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

#### Validación temporal (MODEL-04)

- **D-11: Holdouts** — 4 torneos fijos:
  1. Copa del Mundo 2018 (64 partidos)
  2. Copa del Mundo 2022 (64 partidos)
  3. Eurocopa 2024 (51 partidos)
  4. Copa América 2024 (32 partidos)
  El modelo se ajusta con datos **anteriores** a cada torneo holdout (corte estricto por fecha de inicio).

- **D-12: Métricas** — log-loss (principal), Brier score, RPS. Reportar también vs. baselines naïve: distribución uniforme (33/33/33), solo-Elo (sin Dixon-Coles), solo-ranking-FIFA.

- **D-13: Gate de aceptación** — El baseline pasa si vence a TODOS los baselines naïve en log-loss promediado sobre los 4 holdouts. Si no pasa, se documenta y se continúa de todas formas (el ML de Phase 5 puede mejorar).

#### Notebooks didácticos

- **D-14: Nivel matemático** — **Derivar matemática core**: la corrección ρ de Dixon-Coles, la función de log-likelihood completa, y el gradiente analítico (o al menos la estructura de la optimización). Nivel ingeniería/maestría. Diferenciador de portafolio.
- **D-15: Estructura de notebook** — Obligatoria: celda MD (qué/por qué) → celda código → celda MD (interpretación). Igual que Phase 1. Los notebooks importan funciones de `cdd_mundial.*`, no reimplementan lógica.

### Claude's Discretion

- D-04 explícitamente delega al planner la elección entre recomputación cold-start (1000) y warm-start con snapshot de eloratings.net.
- Specifics: la ventaja de anfitrión MEX/USA/CAN "puede ser un flag en `ctx` o una tabla de sedes" — elección de implementación.

### Specific Ideas (del CONTEXT)

- El multiplicador de margen WFE tiene la corrección por Δ_Elo (`2.2 / (Δ_Elo * 0.001 + 2.2)`) — incluir esta versión completa, no solo `log(diff+1)`.
- La ventaja de anfitrión para MEX/USA/CAN es específica del Mundial 2026 — puede ser un flag en `ctx` o una tabla de sedes.
- El notebook debe incluir un diagrama de calibración (reliability diagram) sobre los holdouts para visualizar si las probabilidades W/D/L son honestas.
- La tasa de empates Dixon-Coles debe caer en el rango 24–28% para partidos neutrales entre equipos de nivel similar — incluir esto como check de sanidad en el notebook.

### Deferred Ideas (OUT OF SCOPE)

- **Optimización de K**: grid-search o scipy.optimize de K por categoría de torneo sobre los holdouts — aplazado al cierre de Phase 2 si hay tiempo, o Phase 5/post-mortem.
- **Re-entrenamiento incremental (online Elo)**: actualizar solo los partidos nuevos sin re-correr todo el histórico — aplazado a Phase 4/6 si el re-fit completo es demasiado lento.
- **De-margin multi-bookmaker / método Shin**: evaluación de fuentes de cuotas adicionales — aplazado a v2 (EVAL-V2-03).
- **Valor de plantilla (Transfermarkt) como feature**: aplazado a v2 (DATA-V2-01).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODEL-01 | Elo dinámico custom (K por torneo, ventaja local, margen de victoria) recomputado desde histórico | Fórmula WFE canónica verificada (K, We, W=0.5 en shootouts); fórmula de margen D-03 verificada como variante FiveThirtyEight; datos verificados (49,405 partidos, 1872→2026-06-10, flag `neutral`, semántica shootout); 48 selecciones con ≥25 partidos recientes; pitfalls de empates con multiplicador cero y escala de inicialización documentados |
| MODEL-02 | Dixon-Coles con corrección ρ, decaimiento temporal, contrato `predict_lambdas` | Especificación completa del modelo (parametrización, τ, cotas de ρ, NLL ponderada, gradiente analítico); estrategia de optimización scipy L-BFGS-B verificada viable; inconsistencia numérica en D-06 (ξ vs half-life) detectada y con resolución recomendada; truncamiento efectivo del histórico por peso justificado |
| MODEL-03 | W/D/L derivadas de la matriz de marcadores DC | Algoritmo de matriz P(i,j) 0–10 con τ aplicada a 4 celdas + renormalización; check de sanidad verificado numéricamente: λ=μ=1.25, ρ=0 ⇒ P(empate)≈27% (dentro de 24–28%) |
| MODEL-04 | Validación temporal contra 4 holdouts con log-loss, Brier, RPS | Los 4 holdouts verificados presentes en el parquet con conteos exactos (64/64/51/32 — cuidado con 'Copa América qualification'); patrón fit-at-cutoff; RPS y Brier multiclase custom (sklearn no los cubre); gap de datos para baseline solo-ranking-FIFA detectado y flageado |
</phase_requirements>

## Summary

Esta fase es factible con bajo riesgo técnico: los datos de entrada están materializados y verificados en vivo (49,405 partidos hasta 2026-06-10, los 4 torneos holdout presentes con los conteos exactos esperados, las 48 selecciones con cobertura reciente abundante), y el stack matemático (scipy MLE + numpy vectorizado) es la herramienta estándar para Dixon-Coles. El trabajo es esencialmente implementación custom deliberada (Elo y DC son el contenido pedagógico core, decisión ya tomada en el stack del proyecto), no investigación de librerías.

Los riesgos reales son cuatro ambigüedades/inconsistencias en las decisiones del CONTEXT que el planner debe resolver explícitamente antes de codificar: (1) D-02 leído literalmente elimina la ventaja local de TODO el histórico, lo que contradice el success criterion "ventaja local condicional a sede neutral" — se recomienda la reconciliación estándar WFE; (2) D-06 contiene dos números mutuamente inconsistentes (ξ=0.0018/día implica half-life de ~385 días, no ~2 años); (3) la tabla K de D-01 difiere de la canónica WFE (continentales = 50, no 60) y D-01 mismo ordena seguir la fuente canónica; (4) el baseline solo-ranking-FIFA de D-12 no tiene datos ingestados en Phase 1. Además, la fórmula de margen de D-03 es la de FiveThirtyEight (no la tabla G de eloratings.net) y produce actualización CERO en empates si se aplica ingenuamente — pitfall crítico documentado abajo.

El entorno necesita un Wave 0: scipy, scikit-learn, matplotlib, seaborn y joblib NO están instalados en el venv (verificado hoy). El harness de tests existente aplica gates estructurales automáticos a TODOS los notebooks (strings literales "What and why" / "Interpretation", sin celdas de código vacías, kernel `python3`) — el notebook de Phase 2 los hereda sin configuración adicional.

**Primary recommendation:** Implementar `cdd_mundial.models` (elo.py, dixon_coles.py, baselines.py, metrics.py, validation.py) con MLE vectorizada + gradiente analítico en scipy L-BFGS-B, patrón fit-at-cutoff para los 5 ajustes (4 holdouts + producción), y resolver las 4 ambigüedades de decisión en el primer plan antes de escribir código de modelo.

## Project Constraints (from CLAUDE.md)

Directivas accionables que los planes DEBEN respetar:

1. **Pins de stack**: pandas `~=2.3.3` (NUNCA 3.x), numpy 2.x (<2.5), scipy 1.17.x, scikit-learn 1.9.0, matplotlib 3.10.9, seaborn 0.13.2, pandera 0.31.x con `import pandera.pandas as pa`. No tocar pins a mitad de torneo.
2. **Dixon-Coles custom con scipy** — penaltyblog 1.11.0 SOLO como benchmark de verificación, nunca importado en `src/` (deps transitivas pesadas: plotly, pulp, etc.).
3. **Elo custom** (~60 líneas) — ninguna librería implementa la variante World Football Elo.
4. **RPS custom** (~10 líneas, suma acumulada) — no existe en sklearn; `pb.metrics.rps` solo como cross-check.
5. **Visualización solo matplotlib/seaborn**; prohibido plotly/Streamlit.
6. **`data/raw/` inmutable**; transformaciones → archivos nuevos con metadatos de extracción.
7. **Reproducibilidad**: semillas fijas, artefactos de modelo versionados por fecha (`joblib.dump` con filename fechado; nunca `pickle` directo).
8. **Estructura didáctica obligatoria** en todos los notebooks: MD (qué/por qué) → código → MD (interpretación).
9. **Repo GitHub público** — sin claves; el gate anti-secretos de notebooks ya existe en tests.
10. **GSD workflow**: cambios de archivos solo dentro de comandos GSD.
11. **numba prohibido** (pin numpy <2.5); vectorización numpy pura.
12. **`cv="prefit"` prohibido** en sklearn (no aplica a esta fase — calibración es Phase 5, pero no introducirlo).

## Architectural Responsibility Map

El proyecto es un pipeline batch local (no hay tiers web); las capas relevantes son:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Carga/validación de datos históricos | Capa de datos (`cdd_mundial.data`, ya existe) | — | Contratos pandera y resolución de identidades ya implementados en Phase 1; los modelos los CONSUMEN, no los reimplementan |
| Recomputación Elo + tabla K por torneo | Capa de modelos (`cdd_mundial.models.elo` + `tournaments`) | Artefactos en `data/processed/models/` | Lógica secuencial por naturaleza; produce trayectoria histórica + snapshot actual |
| Ajuste Dixon-Coles + `predict_lambdas` | Capa de modelos (`cdd_mundial.models.dixon_coles`) | — | MLE scipy; expone EL contrato congelado que consume Phase 3 |
| Derivación W/D/L de matriz de marcadores | Capa de modelos (`dixon_coles`) | — | D-10: sale del modelo de goles, función pura sobre (λ, μ, ρ) |
| Baselines naïve (uniforme, solo-Elo) | Capa de modelos (`baselines`) | — | Comparadores del gate D-13; solo-Elo necesita mapeo Elo→W/D/L propio |
| Métricas (log-loss, Brier, RPS) | Capa de evaluación (`metrics`) | sklearn para log_loss | RPS y Brier multiclase custom; log_loss de sklearn |
| Splits temporales + reporte holdout | Capa de evaluación (`validation`) | — | Patrón fit-at-cutoff; 4 cortes estrictos por fecha de inicio de torneo |
| Derivaciones matemáticas + reliability diagram | Capa didáctica (`notebooks/02_*.ipynb`) | matplotlib/seaborn | Importa de `cdd_mundial.models`; NO define funciones (gate estructural) |
| Persistencia de artefactos + provenance | Capa de datos (`provenance.py` existente) | — | `ProvenanceRecord` + `write_provenance_manifest` ya existen |

## Standard Stack

### Core (ya instalado — verificado en venv hoy)

| Library | Version | Purpose | Estado |
|---------|---------|---------|--------|
| Python | 3.12.13 (`.venv\python.exe`, base Anaconda) | Runtime | [VERIFIED: ejecutado hoy] |
| pandas | 2.3.3 | Carga parquet, manipulación | [VERIFIED: import en venv] |
| numpy | 2.4.6 | Vectorización NLL, matriz de marcadores | [VERIFIED: import en venv] |
| pandera | 0.31.x | Contratos de artefactos nuevos | [VERIFIED: contracts.py funciona] |
| pytest / nbformat / nbclient | 8.4.2 / 5.10.4 / 0.11.0 | Tests + gates de notebook | [VERIFIED: import en venv] |

### Por instalar en Wave 0 (FALTAN en el venv — verificado hoy)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| scipy | ~=1.17 | `optimize.minimize(method="L-BFGS-B")` para MLE de DC; `stats.poisson` para PMFs | Herramienta estándar para MLE Dixon-Coles [VERIFIED: PyPI 2026-06-11, research de stack previo] |
| scikit-learn | ~=1.9 | `log_loss` multiclase, `calibration_curve` para reliability diagram | Métricas auditadas [VERIFIED: PyPI 2026-06-11] |
| matplotlib | ~=3.10 | Visuales del notebook | Constraint de proyecto [VERIFIED: PyPI 2026-06-11] |
| seaborn | ==0.13.2 | Visuales del notebook | Última release; compatible pandas 2.3.x [VERIFIED: PyPI 2026-06-11] |
| joblib | latest | Persistencia de artefactos de modelo fechados | Estándar sklearn-ecosystem [CITED: CLAUDE.md stack] |
| statsmodels | ~=0.14 (OPCIONAL) | GLM Poisson independiente como peldaño pedagógico/benchmark | Opcional, no en path de producción |
| penaltyblog | ==1.11.0 (OPCIONAL, solo verificación) | Cross-check de λ de DC y RPS | NUNCA en `src/`; si falla la instalación en Windows, omitir el cross-check (es opcional) |

**Installation (Wave 0):**

```powershell
# 1. Añadir a pyproject.toml [project] dependencies:
#    "scipy~=1.17", "scikit-learn~=1.9", "matplotlib~=3.10", "seaborn==0.13.2", "joblib>=1.4"
# 2. Reinstalar editable:
.\.venv\python.exe -m pip install -e ".[dev]"
# 3. Opcional (verificación, no pin en pyproject):
.\.venv\python.exe -m pip install penaltyblog==1.11.0 statsmodels
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DC custom scipy | penaltyblog `DixonColesGoalModel` | Solo si colapsa el timeline; se pierde neutral-aware, pesos por torneo y el contenido pedagógico (decisión ya tomada en stack) |
| Gradiente analítico | Jacobiano numérico de L-BFGS-B | Numérico funciona pero con ~500–700 parámetros cada gradiente cuesta cientos de evaluaciones → minutos por fit × 5 fits; el analítico (requerido por D-14 de todas formas) baja cada fit a segundos |
| Ordered logit para solo-Elo→W/D/L | Binning empírico de P(empate) por diferencia Elo | Ambos válidos; ordered logit es ~3 parámetros con scipy y más limpio de documentar — discreción del planner |

## Architecture Patterns

### System Architecture Diagram

```
data/processed/historical_matches.parquet ──► load_matches() [valida HistoricalMatchesSchema]
        │                                          (date: str → datetime; etiqueta outcome 90' usando
        │                                           result_after_extra_time/shootout_winner_team_id)
        │
        ├──► [Elo path] recompute_elo(matches, k_table, home_adv)   ── secuencial, ~49k filas
        │         │
        │         ├──► data/processed/models/elo_history.parquet   (rating post-partido por equipo/fecha
        │         │                                                  → point-in-time para Phase 5 ML-01)
        │         ├──► data/processed/models/elo_ratings.parquet   (snapshot actual; cross-check de rangos
        │         │                                                  vs data/processed/elo_current.parquet)
        │         └──► baselines.solo_elo_wdl(dr) ─────────────┐
        │                                                       │
        ├──► [DC path] fit_dixon_coles(matches, cutoff_date, ξ) │  ── scipy L-BFGS-B, NLL ponderada
        │         │                                             │     + gradiente analítico
        │         ├──► dc_params (att/def por equipo, c, γ, ρ) ─┼──► data/processed/models/dc_params_{fecha}.json
        │         │                                             │
        │         └──► predict_lambdas(team_a, team_b, ctx) ────┼──► [CONTRATO CONGELADO → Phase 3]
        │                       │                               │
        │                       └──► score_matrix(λ,μ,ρ) + τ ───┼──► P(W/D/L) [MODEL-03]
        │                                                       │
        └──► [Validación] para cada holdout en {WC18, WC22, EU24, CA24}:
                  fit con cutoff = inicio del torneo ──► predecir partidos del torneo
                  ──► metrics.{log_loss, brier_mc, rps} vs {uniforme, solo-Elo}
                  ──► reporte gate D-13 + reliability diagram (notebook)
```

### Recommended Project Structure

```
src/cdd_mundial/models/
├── __init__.py          # re-exporta predict_lambdas y APIs públicas
├── tournaments.py       # clasificación tournament(str) → categoría K {wc, continental, qualifier, other, friendly}
├── elo.py               # expected_score, margin_factor, update, recompute_elo(matches) → history df
├── dixon_coles.py       # neg_log_lik + grad, fit(cutoff), DixonColesModel, predict_lambdas, score_matrix, wdl
├── baselines.py         # uniform_wdl(), solo_elo_wdl(dr) (ordered logit o binning)
├── metrics.py           # rps(), brier_multiclass(); log_loss se importa de sklearn
└── validation.py        # HOLDOUTS const, fit-at-cutoff loop, tabla comparativa, gate D-13

tests/
├── test_elo.py                  # updates a mano, shootout=draw, margen, K table cobertura total
├── test_dixon_coles.py          # recuperación de parámetros sintéticos, cotas ρ, matriz suma 1, τ
├── test_metrics.py              # RPS contra valores conocidos a mano, Brier multiclase
├── test_validation_temporal.py  # cortes estrictos (ningún partido de entrenamiento ≥ cutoff)
└── fixtures/                    # mini-dataset comprometido para fits smoke sin red

notebooks/02_modelos_baseline.ipynb   # derivaciones D-14 + reliability diagram + checks de sanidad
data/processed/models/                # artefactos: elo_history, elo_ratings, dc_params_{fecha}
data/external/tournament_k_factors.csv  # registro revisado torneo→K (patrón Phase 1 de tablas revisadas)
```

### Pattern 1: Fit-at-cutoff (el patrón central de MODEL-04)

**What:** Una sola función de ajuste parametrizada por fecha de corte; la validación son 4 invocaciones + 1 de producción.
**When to use:** Todos los ajustes — garantiza por construcción que no hay leakage temporal.

```python
# Patrón: la misma función sirve para backtest y producción
def fit_dixon_coles(matches: pd.DataFrame, cutoff: pd.Timestamp, xi: float) -> DixonColesModel:
    train = matches[matches["date"] < cutoff]
    weights = np.exp(-xi * (cutoff - train["date"]).dt.days.to_numpy())
    train = train[weights > 1e-4]          # truncamiento numéricamente neutro (ver pitfall 7)
    ...
# Holdouts (fechas de inicio verificadas en el parquet hoy):
HOLDOUTS = {
    "wc2018":  ("FIFA World Cup", "2018-06-14"),
    "wc2022":  ("FIFA World Cup", "2022-11-20"),
    "euro2024": ("UEFA Euro", "2024-06-14"),
    "copa2024": ("Copa América", "2024-06-20"),   # string exacto con tilde; ver pitfall 5
}
```

### Pattern 2: Contrato congelado con resolución de identidades

**What:** `predict_lambdas` valida slugs contra `teams.csv` y falla ruidosamente con desconocidos (patrón establecido en Phase 1 con `UnknownTeamError`).
**When to use:** El wrapper público; internamente el modelo opera sobre índices enteros de equipo.

```python
# El contrato D-09 — los team IDs YA son slugs canónicos; validar pertenencia, no resolver alias
def predict_lambdas(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    # ctx: {"neutral": bool, "date": datetime, "tournament_type": str}
    # neutral=False ⇒ team_a es el local/anfitrión y recibe el efecto γ (DC) — documentar la convención
    ...
```

**Nota de diseño**: en 2026 solo MEX/USA/CAN tendrán `neutral=False`. La convención "team_a = local cuando neutral=False" debe quedar documentada en el docstring porque Phase 3 la consume a ciegas.

### Pattern 3: Gates estructurales de notebook (heredados automáticamente)

`tests/test_notebooks.py` parametriza sobre TODOS los `notebooks/*.ipynb` [VERIFIED: leído hoy]:
- Cada celda de código DEBE estar precedida por markdown que contenga el string literal **"What and why"** y seguida por markdown que contenga **"Interpretation"**.
- Sin celdas de código vacías; sin material que parezca secreto (escanea también outputs renderizados); kernel `python3`.
- Los fragmentos prohibidos (`def `, `class `, `import requests`...) hoy solo se aplican al notebook de Phase 1, pero la convención del proyecto (D-15) es la misma: el notebook de Phase 2 importa de `cdd_mundial.models`, no define funciones. Recomendación: extender ese gate al notebook 02 en los tests de fase.
- Debe ejecutar limpio con `jupyter nbconvert --to notebook --execute`.

### Anti-Patterns to Avoid

- **Logistic sobre Elo para W/D/L del baseline principal**: prohibido por D-10 — el empate sale de la matriz DC. (El mapeo Elo→W/D/L SÍ se necesita, pero solo para el baseline comparador solo-Elo.)
- **Re-resolver alias dentro del modelo**: los inputs ya son slugs canónicos; `TeamResolver` es para fuentes externas, no para el contrato.
- **Optimizar sin cotas en ρ**: la τ puede volverse negativa (probabilidad negativa) fuera del rango válido — usar `bounds` de L-BFGS-B.
- **Ajustar UNA vez y evaluar los 4 holdouts con el mismo fit**: leakage directo (el fit de producción vio WC2018...CA24). Cada holdout requiere su propio fit-at-cutoff.
- **Definir funciones en el notebook**: viola D-15 y el patrón del repo.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PMF/CDF Poisson | factoriales a mano | `scipy.stats.poisson.pmf` | Estabilidad numérica en colas |
| Optimización MLE | descenso de gradiente propio | `scipy.optimize.minimize(method="L-BFGS-B", jac=grad)` | Línea de búsqueda, convergencia, bounds — todo resuelto |
| log-loss multiclase | implementación propia | `sklearn.metrics.log_loss` | Clipping de probabilidades y casos borde auditados |
| Curva de calibración | binning manual frágil | `sklearn.calibration.calibration_curve` (por outcome, one-vs-rest) | Estándar y suficiente para el reliability diagram |
| Lectura/escritura parquet | serialización propia | `pandas.to_parquet/read_parquet` (pyarrow) | Ya es el estándar del repo |
| Validación de esquemas | asserts ad-hoc | pandera `CanonicalSchema` (heredar de `contracts.py`) | Patrón Phase 1: strict=True, coerce=True |
| Persistencia de modelo | pickle directo | `joblib.dump/load` con filename fechado | Constraint de CLAUDE.md |

**Hand-roll deliberado (decisiones de stack ya tomadas, son el contenido pedagógico):** Elo WFE, Dixon-Coles (NLL, τ, gradiente), RPS (~10 líneas), Brier multiclase (~3 líneas — `brier_score_loss` de sklearn es binario [ASSUMED: no verificado si 1.9 añadió soporte multiclase; el custom de 3 líneas es trivialmente correcto y evita la duda]).

## Common Pitfalls

### Pitfall 1: La fórmula de margen D-03 produce actualización CERO en empates (CRÍTICO)

**What goes wrong:** `log(|diff_goles| + 1)` con diff=0 da `log(1) = 0` ⇒ `margin_factor = 0` ⇒ los empates NUNCA mueven el Elo. Un empate entre un equipo top y uno débil debe transferir puntos (W−We ≠ 0); con multiplicador 0 el sistema queda ciego a ~23% de los partidos (tasa de empate histórica verificada: 22.7%).
**Why it happens:** La fórmula de D-03 es el multiplicador MOV de **FiveThirtyEight NFL Elo** (`LN(ABS(PD)+1) * 2.2/((ELOW−ELOL)*0.001+2.2)`, con ELOW−ELOL = Elo pre-partido del ganador menos el del perdedor) [VERIFIED: WebSearch — Chief Delphi + fivethirtyeight.com/features/introducing-nfl-elo-ratings], diseñada para un deporte casi sin empates. NO es la fórmula de eloratings.net (que usa la tabla discreta G: 1 / 1.5 / (11+N)/8) [VERIFIED: Wikipedia World Football Elo Ratings].
**How to avoid:** Definir explícitamente la rama de empate. Recomendación: `margin_factor = 1.0` cuando diff=0 (sin ajuste MOV ni de autocorrelación — no hay "ganador" que defina Δ_Elo_winner). Documentar en el notebook que la fórmula es la variante 538 adaptada, con atribución correcta.
**Warning signs:** Tras la recomputación, equipos con muchos empates tienen ratings idénticos a su inicialización en tramos largos; correlación de rangos vs snapshot eloratings sospechosamente baja.

### Pitfall 2: D-02 leído literalmente borra la ventaja local de todo el histórico

**What goes wrong:** "Partidos fuera del torneo se tratan como neutrales con ventaja = 0" ⇒ recomputar 49k partidos sin ventaja local. El 73.6% de los partidos históricos NO son neutrales [VERIFIED: parquet hoy]; ignorar la ventaja sesga We sistemáticamente (los locales ganan más) e infla los ratings de equipos que juegan mucho en casa. Además contradice el success criterion #1 del ROADMAP ("ventaja local condicional a sede neutral") y la metodología WFE (+100 al local en todo partido no neutral).
**How to avoid:** Reconciliación recomendada (ver Open Question 1): histórico → +100 al `home_team_id` cuando `neutral == False` (estándar WFE, usa el flag ya validado del parquet); predicción 2026 → solo MEX/USA/CAN reciben el bono (todos los demás partidos del Mundial son neutrales aunque haya "home team" nominal). Esto satisface D-02 en su intención (el bono 2026 es solo para anfitriones) y el success criterion a la vez.
**Warning signs:** Spearman vs eloratings.net < 0.9 en las 48 selecciones.

### Pitfall 3: La tabla K de D-01 difiere de la canónica WFE — y D-01 ordena seguir la canónica

**What goes wrong:** D-01 asigna K=60 a torneos continentales; la fuente canónica WFE usa: 60 Mundial, **50 continentales + intercontinentales (Confederaciones)**, 40 clasificatorias y torneos mayores, **30 resto**, 20 amistosos [VERIFIED: Wikipedia World Football Elo Ratings; eloratings.net/about es JS-rendered y no extraíble directamente].
**How to avoid:** D-01 incluye la cláusula "seguir la fuente canónica WFE" — usar la tabla de 5 niveles (60/50/40/30/20). La categoría 30 ("otros torneos": CECAFA, Merdeka, King's Cup, Nations League grupos... [ASSUMED: la asignación exacta de Nations League es K=40 como "torneo mayor"]) es necesaria: el parquet tiene **200 strings de torneo distintos** [VERIFIED] y la tabla de D-01 no cubre la cola larga.
**Warning signs:** Tests de cobertura fallan porque un string de torneo no mapea a categoría.

### Pitfall 4: D-06 es internamente inconsistente — ξ=0.0018/día NO es half-life de 2 años

**What goes wrong:** half-life = ln(2)/ξ. Con ξ=0.0018/día ⇒ 385 días ≈ **1.05 años**, no ~2 años. Half-life de 2 años ⇒ ξ ≈ **0.00095/día**. (El 0.0018/día sí coincide con el óptimo del paper DC 1997: ξ=0.0065 por media-semana ÷ 3.5 ≈ 0.00186/día [ASSUMED: conversión de unidades del paper, verificar en el paper al implementar].)
**How to avoid:** No elegir a ciegas: el harness fit-at-cutoff hace trivial un mini-grid ξ ∈ {0.00095, 0.0018} (¿quizá 0.0035?) evaluado por log-loss en los 4 holdouts (~minutos con gradiente analítico). Reportar la elección en el notebook con la aritmética del half-life corregida. Para selecciones (≈10–12 partidos/año vs ~50 de clubes) memorias más largas suelen ser defendibles — otro motivo para el mini-grid.
**Warning signs:** Documentar "half-life 2 años" junto a "ξ=0.0018" en el notebook sin notar la contradicción — un revisor de portafolio lo detectará.

### Pitfall 5: Strings de torneo con tilde y el falso conteo de Copa América 2024

**What goes wrong:** Filtrar `tournament.str.startswith("Copa Am")` para el holdout da **34** partidos porque arrastra 2 de "Copa América qualification" (mar-2024) [VERIFIED: hoy]. El holdout D-11 son exactamente los **32** con string exacto `"Copa América"` y fecha ≥ 2024-06-20. Además los strings llevan tildes UTF-8 — comparaciones con strings sin tilde fallan silenciosamente.
**How to avoid:** Igualdad exacta de string + corte por fecha de inicio del torneo; test que afirme los conteos 64/64/51/32.

### Pitfall 6: Marcadores martj42 incluyen tiempo extra — el resultado de 90' es irrecuperable

**What goes wrong:** `home_score/away_score` son FT+ET [VERIFIED: CONTEXT + semántica ingest]. 677 partidos tienen `result_after_extra_time=True` (los mismos 677 con shootout) [VERIFIED]. Para esos partidos el resultado de 90' fue empate, pero el marcador registrado puede no serlo.
**How to avoid:** (a) **Etiquetas de outcome** (Elo W y evaluación holdout): si `result_after_extra_time` o `shootout_winner_team_id` no nulo ⇒ outcome = empate (consistente con D-05 y con WFE, que cuenta shootouts como empate W=0.5 [VERIFIED: Wikipedia]). Ojo: el margen de goles para el multiplicador en esos partidos es el de ET — si el outcome es empate, usar rama de empate (factor 1), ignorando el marcador ET. (b) **Goles para entrenar DC**: los 677 (1.4%) inflan levemente λ; recomendación: incluirlos y documentar la aproximación (alternativa: excluirlos del fit DC — discreción del planner; el efecto es marginal).
**Warning signs:** Un partido decidido en penales contado como victoria en el Elo o en el log-loss del holdout.

### Pitfall 7: MLE con ~670 parámetros y jacobiano numérico = fits de 10+ minutos × 5

**What goes wrong:** Histórico completo tiene 336 equipos ⇒ ~675 parámetros; L-BFGS-B sin `jac` aproxima el gradiente con ~676 evaluaciones por iteración.
**How to avoid:** (a) Gradiente analítico — D-14 lo pide derivado de todas formas; la parte Poisson es trivial (`∂ℓ/∂log λ = w·(x − λ)` acumulado por equipo) y la τ solo aporta términos en los 4 marcadores bajos. (b) Truncar el set de entrenamiento donde `w < 1e-4` (con ξ=0.0018 ⇒ ~14 años ⇒ ~15k partidos, menos equipos) — numéricamente idéntico al "todo el histórico" de D-07 (los pesos descartados son < 0.0001) y debe documentarse así en el notebook. (c) Identifiabilidad: imponer Σatt=0, Σdef=0 (reparametrización con n−1 libres, o centrado con penalización suave) — la NLL tiene dirección plana sin esto y la convergencia se degrada.
**Warning signs:** `minimize` agota iteraciones sin converger; parámetros att/def con deriva conjunta arbitraria.

### Pitfall 8: ρ fuera de su rango válido produce probabilidades negativas

**What goes wrong:** τ es válida solo si `max(−1/λ, −1/μ) ≤ ρ ≤ min(1/(λμ), 1)` [CITED: Dixon & Coles 1997]. Fuera, P(0,0) o P(1,1) pueden ser negativas.
**How to avoid:** `bounds=[(-0.2, 0.2)]` para ρ en L-BFGS-B (los λ típicos ~0.5–3 hacen ese rango seguro; el ρ ajustado en fútbol es pequeño, típicamente |ρ|<0.1 [ASSUMED]). Test: matriz de marcadores con todos los valores ≥ 0 y suma 1 tras renormalizar.

### Pitfall 9: Inicialización en 1000 desplaza la escala absoluta vs eloratings.net

**What goes wrong:** Elo conserva aproximadamente el promedio inicial: con todos en 1000, la media queda ~1000 mientras eloratings.net se centra ~1500. Comparar valores absolutos contra `data/processed/elo_current.parquet` "falla" aunque el modelo sea correcto. El warm-start con el snapshot NO es viable como sustituto del histórico completo: solo cubre 48 equipos de 336 [VERIFIED: parquet 48×6].
**How to avoid:** Cold-start 1000 sobre todo el histórico (es barato: la recomputación secuencial de 49k filas corre en segundos). Validar por **correlación de rangos (Spearman)** y por diferencias relativas entre las 48 selecciones, no por niveles absolutos. Solo las DIFERENCIAS de Elo importan para We y para la feature de Phase 5.

### Pitfall 10: El baseline solo-ranking-FIFA no tiene datos

**What goes wrong:** D-12 lista solo-ranking-FIFA como baseline, pero Phase 1 no ingirió rankings FIFA históricos point-in-time (no hay artefacto; no es ningún DATA-0x) [VERIFIED: data/external y data/processed listados hoy].
**How to avoid:** El success criterion del ROADMAP y la frase operativa del gate solo exigen "uniforme, solo-Elo". Recomendación: gate D-13 = {uniforme, solo-Elo}; solo-ranking-FIFA como stretch opcional vía kagglehub (existe un dataset Kaggle de rankings FIFA 1992–presente, p.ej. `cashncarry/fifaworldranking` [ASSUMED: handle no verificado en vivo]) solo si sobra tiempo. Ver Open Question 3.

### Pitfall 11: Columna `date` es string en el contrato pandera

**What goes wrong:** `HistoricalMatchesSchema` tipa `date` como `str` [VERIFIED: contracts.py]; aritmética de fechas sin `pd.to_datetime` explota o, peor, compara lexicográficamente.
**How to avoid:** `load_matches()` convierte una sola vez al cargar; los pesos exponenciales usan `.dt.days`.

## Code Examples

Patrones verificados contra el paper DC 1997 y la metodología WFE (Wikipedia):

### Elo: actualización de un partido (WFE + margen 538 de D-03)

```python
# Fuente: eloratings.net via Wikipedia (We, +100, W=0.5 shootout) + FiveThirtyEight (margen, D-03)
import numpy as np

def expected_score(elo_a: float, elo_b: float, home_bonus_a: float) -> float:
    dr = (elo_a + home_bonus_a) - elo_b
    return 1.0 / (10 ** (-dr / 400.0) + 1.0)

def margin_factor(goal_diff: int, elo_winner: float, elo_loser: float) -> float:
    if goal_diff == 0:                      # empate: sin ajuste MOV (pitfall 1)
        return 1.0
    autocorr = 2.2 / ((elo_winner - elo_loser) * 0.001 + 2.2)
    return np.log(abs(goal_diff) + 1.0) * autocorr

def elo_update(elo_a, elo_b, score_a, score_b, k, home_bonus_a, drew_after_et=False):
    if drew_after_et:                       # shootout ⇒ empate (D-05 / WFE)
        w_a, gd = 0.5, 0
    else:
        w_a = 1.0 if score_a > score_b else (0.5 if score_a == score_b else 0.0)
        gd = abs(score_a - score_b)
    we_a = expected_score(elo_a, elo_b, home_bonus_a)
    if gd == 0:
        g = 1.0
    elif w_a == 1.0:
        g = margin_factor(gd, elo_a, elo_b)
    else:
        g = margin_factor(gd, elo_b, elo_a)
    delta = k * g * (w_a - we_a)
    return elo_a + delta, elo_b - delta
```

### Dixon-Coles: τ y NLL ponderada vectorizada

```python
# Fuente: Dixon & Coles (1997), ecuaciones 4.2-4.3
from scipy.stats import poisson

def tau_log(x, y, lam, mu, rho):
    """log τ vectorizado; solo (0,0),(0,1),(1,0),(1,1) difieren de 0."""
    t = np.ones_like(lam)
    t = np.where((x == 0) & (y == 0), 1.0 - lam * mu * rho, t)
    t = np.where((x == 0) & (y == 1), 1.0 + lam * rho, t)
    t = np.where((x == 1) & (y == 0), 1.0 + mu * rho, t)
    t = np.where((x == 1) & (y == 1), 1.0 - rho, t)
    return np.log(t)

def neg_log_lik(params, x, y, home_idx, away_idx, is_home, w, n_teams):
    att, dfn = params[:n_teams], params[n_teams:2*n_teams]
    c, gamma, rho = params[-3], params[-2], params[-1]
    log_lam = c + att[home_idx] - dfn[away_idx] + gamma * is_home   # is_home = ~neutral
    log_mu  = c + att[away_idx] - dfn[home_idx]
    lam, mu = np.exp(log_lam), np.exp(log_mu)
    # log Poisson sin el término factorial (constante en params)
    ll = w * (tau_log(x, y, lam, mu, rho) + x*log_lam - lam + y*log_mu - mu)
    return -ll.sum()
# Identifiabilidad: imponer sum(att)=0, sum(dfn)=0 (reparam n-1 libres o penalización).
# Optimización: scipy.optimize.minimize(neg_log_lik, x0, jac=grad, method="L-BFGS-B",
#               bounds=[...; rho ∈ (-0.2, 0.2)])
# Gradiente analítico (D-14): parte Poisson  ∂ℓ/∂c = Σ w(x-λ) + w(y-μ);
#   ∂ℓ/∂att_i = Σ_{i ataca} w(goles-λ_del_lado); la τ añade términos solo en marcadores ≤1.
```

### W/D/L desde la matriz de marcadores (MODEL-03)

```python
# Fuente: práctica estándar DC; convención filas = goles de team_a
def wdl_from_lambdas(lam, mu, rho, max_goals=10):
    g = np.arange(max_goals + 1)
    P = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
    P[0, 0] *= 1 - lam * mu * rho
    P[0, 1] *= 1 + lam * rho
    P[1, 0] *= 1 + mu * rho
    P[1, 1] *= 1 - rho
    P /= P.sum()                       # renormaliza el truncamiento (masa residual ~1e-7 con λ≈1.5)
    p_win  = np.tril(P, -1).sum()      # team_a anota más
    p_draw = np.trace(P)
    p_loss = np.triu(P, 1).sum()
    return p_win, p_draw, p_loss
# Check de sanidad (verificado numéricamente hoy): λ=μ=1.25, ρ=0 ⇒ p_draw ≈ 0.27 ∈ [0.24, 0.28]
```

### RPS (custom, ~10 líneas) y Brier multiclase

```python
# RPS: Constantinou & Fenton (2012), estándar en forecasting de fútbol
def rps(probs: np.ndarray, outcome_idx: np.ndarray) -> float:
    """probs: (n, 3) en orden [win, draw, loss]; outcome_idx: (n,) en {0,1,2}."""
    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(np.eye(3)[outcome_idx], axis=1)
    return float(((cum_p - cum_o) ** 2).sum(axis=1).mean() / 2)   # / (K-1), K=3

def brier_multiclass(probs, outcome_idx):
    return float(((probs - np.eye(3)[outcome_idx]) ** 2).sum(axis=1).mean())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Poisson independiente (Maher 1982) | DC con corrección ρ de marcadores bajos | DC 1997 — sigue siendo el baseline estándar de la industria | La corrección ρ es exactamente el contenido pedagógico D-08/D-14 |
| Ajuste por equipos solo-liga | DC con flag de sede neutral para selecciones | Práctica estándar en modelado de torneos | γ se aplica solo cuando `neutral=False` — clave para Mundial |
| `cv="prefit"` en sklearn | `FrozenEstimator` | sklearn 1.6+ | NO aplica a esta fase (calibración = Phase 5); no introducirlo |

**Deprecated/outdated:**
- `import pandera as pa` (legacy) → usar `import pandera.pandas as pa` (ya es el patrón del repo, verificado en contracts.py).
- numba para acelerar el fit: prohibido por stack (pin numpy <2.5); el gradiente analítico + truncamiento por peso lo hace innecesario.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | El óptimo del paper DC 1997 es ξ=0.0065 por media-semana (⇒ ~0.0019/día) | Pitfall 4 | Bajo — el mini-grid sobre holdouts decide empíricamente de todas formas; verificar en el paper al escribir el notebook |
| A2 | UEFA Nations League clasifica como "torneo mayor" K=40 en WFE | Pitfall 3 | Bajo — 658 partidos; mover entre 30/40 cambia ratings marginalmente |
| A3 | Existe dataset Kaggle de rankings FIFA point-in-time (`cashncarry/fifaworldranking` u otro) | Pitfall 10 | Bajo si el gate se fija en {uniforme, solo-Elo}; el baseline FIFA queda como stretch |
| A4 | ρ ajustado en fútbol internacional es pequeño (|ρ|<0.1) y el bound (−0.2, 0.2) no satura | Pitfall 8 | Bajo — si satura en el bound, ampliar y re-verificar validez de τ |
| A5 | `sklearn.metrics.brier_score_loss` sigue siendo solo binario en 1.9 | Don't Hand-Roll | Nulo — el custom de 3 líneas es correcto independientemente |
| A6 | Manejo exacto de empates en el MOV de 538 (su código NFL usa `max(pd,1)`-style) | Pitfall 1 | Nulo — se recomienda definición propia documentada (factor 1 en empates), no replicar 538 |

## Open Questions

1. **¿Ventaja local en la recomputación histórica del Elo? (D-02 vs success criterion #1)**
   - What we know: D-02 literal = ventaja 0 fuera del Mundial 2026; el success criterion exige "ventaja local condicional a sede neutral"; el 73.6% del histórico no es neutral; WFE canónico aplica +100 al local no neutral.
   - What's unclear: si la intención del Director era realmente recomputar sin ventaja local histórica.
   - Recommendation: histórico con +100 cuando `neutral==False`; en 2026 solo MEX/USA/CAN. Satisface ambos textos. **Confirmar con el usuario en el plan** (decisión de 1 línea, impacto alto en calidad de ratings).

2. **ξ del decaimiento temporal (D-06 auto-inconsistente)**
   - What we know: 0.0018/día ⇒ half-life 385 días; half-life 2 años ⇒ ξ≈0.00095/día. Ambos números aparecen en D-06 como si fueran equivalentes.
   - Recommendation: mini-grid {0.00095, 0.0018} (+0.0035 opcional) por log-loss en holdouts — minutos de cómputo, resuelve la ambigüedad con evidencia y enriquece el notebook. NO es la "optimización de K" diferida (esa es de Elo).

3. **Alcance del gate D-13: ¿incluye solo-ranking-FIFA?**
   - What we know: ROADMAP/success criterion #4 dice "(uniforme, solo-Elo)"; D-12/D-13 añaden FIFA; no hay datos FIFA point-in-time ingestados.
   - Recommendation: gate = {uniforme, solo-Elo}; FIFA como stretch opcional con ingest kagglehub si sobra tiempo. Confirmar al planear.

4. **Mapeo solo-Elo → W/D/L para el baseline comparador**
   - What we know: D-12 exige el baseline pero no define cómo un sistema 2-outcome produce 3 probabilidades.
   - Recommendation: ordered logit sobre dr (2 cutpoints + escala, MLE con scipy sobre el set de entrenamiento de cada cutoff) o binning empírico de P(empate|dr). Discreción del planner; documentar en notebook.

5. **¿Excluir los 677 partidos con ET del entrenamiento de goles DC?**
   - Recommendation: incluir y documentar (efecto ~1.4% de filas); discreción del planner.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv (`.venv\python.exe`) | todo | ✓ | 3.12.13 (Anaconda base) | — |
| pandas / numpy / pyarrow | datos, NLL | ✓ | 2.3.3 / 2.4.6 / (funcional) | — |
| pandera | contratos | ✓ | 0.31.x (contracts.py opera) | — |
| pytest / nbformat / nbclient | tests, gates notebook | ✓ | 8.4.2 / 5.10.4 / 0.11.0 | — |
| **scipy** | MLE DC, poisson | **✗** | — | Ninguno — **bloqueante, instalar en Wave 0** |
| **scikit-learn** | log_loss, calibration_curve | **✗** | — | log-loss custom posible pero innecesario — instalar |
| **matplotlib / seaborn** | notebook, reliability diagram | **✗** | — | Ninguno (constraint de proyecto) — instalar |
| **joblib** | persistencia modelos | **✗** | — | json para dc_params; instalar igualmente |
| statsmodels | benchmark GLM opcional | ✗ | — | Omitir (opcional) |
| penaltyblog | cross-check opcional | ✗ | — | Omitir cross-check si la instalación falla en Windows |
| `data/processed/historical_matches.parquet` | todo | ✓ | 49,405×16, hasta 2026-06-10 | — |
| `data/processed/elo_current.parquet` | cross-check Elo | ✓ | 48×6 | — |
| `data/external/teams.csv` (+aliases) | slugs canónicos | ✓ | 48 WC teams | — |
| Git repo | commits | ✓ | HEAD 455e909 | — |

**Missing dependencies con fallback:** statsmodels, penaltyblog (ambos opcionales — omitir sin pérdida).
**Missing dependencies sin fallback (bloquean — Wave 0):** scipy, scikit-learn, matplotlib, seaborn, joblib. Resolución: actualizar `[project] dependencies` en pyproject.toml + `.\.venv\python.exe -m pip install -e ".[dev]"`.

**Correcciones de nombres vs CONTEXT.md (el planner DEBE usar los reales):**
- `data/processed/historical_matches.parquet` (CONTEXT dice "matches_historical.parquet") [VERIFIED]
- `data/processed/elo_current.parquet` (CONTEXT dice "data/external/elo_snapshot.parquet") [VERIFIED]
- API de provenance: `ProvenanceRecord` + `write_provenance_manifest(record)` (CONTEXT dice "record_provenance(path, metadata)") [VERIFIED: provenance.py]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 (instalado; markers: network, manual, data_acceptance) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.\.venv\python.exe -m pytest tests/test_elo.py tests/test_dixon_coles.py tests/test_metrics.py -x -q` |
| Full suite command | `.\.venv\python.exe -m pytest -q` (suite offline completa) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-01 | Update Elo a mano conocido; shootout ⇒ W=0.5; empate mueve rating (≠0); cobertura K para los 200 strings de torneo; Spearman vs snapshot ≥ umbral | unit + data_acceptance | `pytest tests/test_elo.py -x -q` | ❌ Wave 0 |
| MODEL-02 | Recuperación de parámetros en datos sintéticos; ρ dentro de bounds; `predict_lambdas` rechaza slugs desconocidos; firma del contrato intacta | unit | `pytest tests/test_dixon_coles.py -x -q` | ❌ Wave 0 |
| MODEL-03 | Matriz suma 1, sin celdas negativas; P(empate)∈[0.24,0.28] para λ=μ≈1.25 | unit | `pytest tests/test_dixon_coles.py -x -q` | ❌ Wave 0 |
| MODEL-04 | Conteos holdout exactos 64/64/51/32; ningún partido de entrenamiento ≥ cutoff; RPS contra valores a mano; gate vs baselines reportado | unit + integration | `pytest tests/test_validation_temporal.py tests/test_metrics.py -x -q` | ❌ Wave 0 |
| DOC-01 | Estructura didáctica del notebook 02 | existente (auto-paramétrico) | `pytest tests/test_notebooks.py -x -q` | ✅ (cubre nuevos notebooks automáticamente) |

### Sampling Rate

- **Per task commit:** quick run del módulo tocado (`pytest tests/test_<modulo>.py -x -q`)
- **Per wave merge:** `.\.venv\python.exe -m pytest -q`
- **Phase gate:** suite completa verde + notebook ejecuta limpio con `jupyter nbconvert --to notebook --execute notebooks/02_modelos_baseline.ipynb` antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] Dependencias: scipy/scikit-learn/matplotlib/seaborn/joblib en pyproject + `pip install -e ".[dev]"`
- [ ] `tests/test_elo.py` — MODEL-01
- [ ] `tests/test_dixon_coles.py` — MODEL-02/03 (incluye fixture sintética de recuperación de parámetros con semilla fija)
- [ ] `tests/test_metrics.py` — RPS/Brier contra valores calculados a mano
- [ ] `tests/test_validation_temporal.py` — MODEL-04 (cortes estrictos, conteos holdout)
- [ ] `data/external/tournament_k_factors.csv` (o módulo `tournaments.py` con listas explícitas) + test de cobertura de los 200 strings

## Security Domain

Fase de cómputo local sin superficie web/red (no hay ingestas nuevas obligatorias). ASVS L1 aplicable de forma mínima:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (sin servicios) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | pandera (contratos en frontera de pipeline) + rechazo de slugs desconocidos en `predict_lambdas` (patrón `UnknownTeamError` de Phase 1) |
| V6 Cryptography | no (solo integridad) | sha256 de provenance.py existente para artefactos — no inventar crypto |
| V14 Config/Supply chain | yes | Pins de versión en pyproject; no añadir deps fuera de la lista Wave 0 |

### Known Threat Patterns for este stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Deserialización de pickles no confiables | Tampering | `joblib.load` SOLO sobre artefactos propios versionados en el repo/dirs del proyecto |
| Fuga de secretos en notebooks renderizados | Information Disclosure | Gate existente `test_notebook_contains_no_secret_material` (escanea también outputs) — corre automático sobre el notebook 02 |
| Mutación silenciosa de datos de entrenamiento | Tampering | raw inmutable + checksums provenance (patrón Phase 1); artefactos de modelo con manifest |

## Sources

### Primary (HIGH confidence)

- Codebase y datos verificados en vivo 2026-06-12: `historical_matches.parquet` (49,405×16; holdouts 64/64/51/32; tasa de empate 22.7%; 677 shootouts; 200 torneos; 336 equipos; 48 WC teams todos con ≥25 partidos desde 2022-06), `elo_current.parquet` (48×6), `contracts.py`, `identities.py`, `provenance.py`, `test_notebooks.py`, `pyproject.toml`, venv (Python 3.12.13; scipy/sklearn/matplotlib/seaborn AUSENTES).
- Dixon & Coles (1997), "Modelling Association Football Scores..." — τ, cotas de ρ, MLE ponderada, decaimiento exponencial [CITED: referencia canónica del CONTEXT; fórmulas de training data consistentes con el paper].
- CLAUDE.md stack research (PyPI JSON verificado 2026-06-11) — versiones scipy 1.17.x, sklearn 1.9.0, matplotlib 3.10.9, seaborn 0.13.2, penaltyblog 1.11.0.

### Secondary (MEDIUM-HIGH confidence)

- Wikipedia "World Football Elo Ratings" [WebFetch 2026-06-12] — tabla K canónica (60/50/40/30/20), G discreto, +100 local, We, shootout = empate (W=0.5). (eloratings.net/about es JS-rendered, no extraíble directo — Wikipedia documenta la misma metodología.)
- FiveThirtyEight NFL Elo MOV multiplier [WebSearch 2026-06-12: Chief Delphi, fivethirtyeight.com/features/introducing-nfl-elo-ratings, github.com/fivethirtyeight/nfl-elo-game] — confirma que la fórmula D-03 es la variante 538 (Δ_Elo = winner−loser pre-partido) y el problema de empates.

### Tertiary (LOW confidence — flageado en Assumptions Log)

- Conversión de unidades del ξ del paper DC (A1); asignación K de Nations League (A2); handle del dataset Kaggle de rankings FIFA (A3); magnitud típica de ρ (A4).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — entorno sondeado en vivo hoy; versiones verificadas ayer vía PyPI en el research de stack del proyecto
- Architecture: HIGH — patrones derivados del código Phase 1 real leído hoy; fórmulas DC/WFE verificadas contra fuentes
- Pitfalls: HIGH — los 5 críticos (empate-cero, D-02, tabla K, ξ, Copa América) verificados con datos/fuentes; el resto MEDIUM-HIGH
- Decisiones abiertas: 4 ambigüedades del CONTEXT requieren resolución del planner/usuario (Open Questions 1–4) — no son gaps de research sino inconsistencias del insumo

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (dominio estable: paper de 1997 y metodología WFE no cambian; solo los datos se actualizan a diario por diseño)
