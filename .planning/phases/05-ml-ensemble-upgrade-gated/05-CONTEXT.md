# Phase 05: ML + Ensemble (upgrade gated) - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Construir una capa ML reproducible y un ensemble calibrado que compitan honestamente contra el baseline ya operativo, sin interrumpir la publicacion diaria del sistema actual.

El alcance incluye:
1. Definir y materializar un dataset de entrenamiento point-in-time para clasificacion 3-way por partido.
2. Entrenar un clasificador ML acotado y evaluarlo con la misma validacion temporal estricta del baseline.
3. Evaluar tres candidatos: baseline, ML solo y ensemble.
4. Calibrar los candidatos ML/ensemble y aplicar un gate de promocion honesto.
5. Si gana el upgrade, integrarlo en publicacion dual junto al baseline, no como reemplazo inmediato.

</domain>

<decisions>
## Implementation Decisions

### Dataset y features v1
- **D-01:** El dataset ML v1 tiene una fila por partido y target 3-way canonico (`0=home_win`, `1=draw`, `2=away_win`), calculado estrictamente pre-kickoff.
- **D-02:** El nucleo obligatorio de features v1 combina senales crudas point-in-time con salidas estructurales del baseline. El set fijado es de 12 features:
  - `elo_diff`
  - `is_host_home`
  - `days_rest_diff`
  - `form_points_diff_last_5`
  - `goal_diff_per_match_diff_last_5`
  - `goals_for_per_match_diff_last_5`
  - `goals_against_per_match_diff_last_5`
  - `lambda_home_dc`
  - `lambda_away_dc`
  - `p_home_win_dc`
  - `p_draw_dc`
  - `p_away_win_dc`
- **D-03:** La ventana de forma reciente y rollings es fija de `last_5`. No se mezclan ventanas `last_3` y `last_5` en v1.
- **D-04:** Si alguno de los dos equipos tiene menos de 5 partidos previos disponibles al kickoff, no se genera fila ML para ese partido. En inferencia, esos casos caen por definicion al baseline.
- **D-05:** El dataset canonico de entrenamiento XGBoost no lleva normalizacion ni escalado. Las variables se conservan en sus unidades naturales.
- **D-06:** `form_points_diff_last_5` se define como diferencia home-away del promedio de puntos por partido en los ultimos 5 juegos (`3/1/0`).
- **D-07:** Los rollings de goles se definen como promedios por partido en los ultimos 5 juegos; no sumas crudas ni pesos por recencia en v1.

### Ranking FIFA point-in-time
- **D-08:** La serie historica de ranking FIFA point-in-time es una feature opcional gated. Se incorpora solo si se consigue una fuente reproducible, limpia y sin leakage temporal.
- **D-09:** La ausencia de esa serie no bloquea la Fase 5. Si no se consigue, la omision debe quedar documentada explicitamente en research, plan y resultados.

### Topologia de candidatos y calibracion
- **D-10:** La comparacion metodologica de la fase debe incluir tres candidatos: baseline estructural, ML solo y ensemble.
- **D-11:** La calibracion se evalua por candidato, no solo al final. El ML solo y el ensemble deben entrar a la comparacion final en su mejor version calibrada.
- **D-12:** La comparacion de calibracion es empirica entre isotonic y Platt/sigmoid bajo validacion temporal estricta. No se asume isotonic superior por defecto.

### Gate y promocion operativa
- **D-13:** La promocion del upgrade sigue siendo gated: solo se promueve un candidato si realmente mejora al baseline en log-loss sobre los holdouts definidos por la fase.
- **D-14:** Si el upgrade gana el gate, entra en publicacion dual junto al baseline. El baseline permanece como linea operativa estable en vez de ser reemplazado de inmediato.

### Schema logico del dataset ML v1

| Variable | Descripcion | Unidades | Fuente BD |
|---|---|---:|---|
| `elo_diff` | Diferencia de Elo pre-partido: `elo_home_pre - elo_away_pre` con semantica point-in-time | puntos Elo | `data/processed/live/` derivado de historico + live via `src/cdd_mundial/live/materialization.py` y `elo_history.parquet` |
| `is_host_home` | Indicador de si el equipo listado como `home` juega con condicion de anfitrion real | `0/1` | `data/external/fixture_2026.csv` + reglas de localia del proyecto |
| `days_rest_diff` | Diferencia de descanso antes del partido: `days_rest_home - days_rest_away` | dias | `data/processed/historical_matches.parquet` + fixture/live results |
| `form_points_diff_last_5` | Diferencia del promedio de puntos por partido en los ultimos 5 juegos | puntos por partido | calculada sobre historico canonico + live canonical rows |
| `goal_diff_per_match_diff_last_5` | Diferencia del promedio reciente de diferencial de gol por partido en ultimos 5 juegos | goles por partido | calculada sobre historico canonico + live canonical rows |
| `goals_for_per_match_diff_last_5` | Diferencia del promedio reciente de goles anotados por partido en ultimos 5 juegos | goles por partido | calculada sobre historico canonico + live canonical rows |
| `goals_against_per_match_diff_last_5` | Diferencia del promedio reciente de goles recibidos por partido en ultimos 5 juegos | goles por partido | calculada sobre historico canonico + live canonical rows |
| `lambda_home_dc` | Goles esperados del equipo `home` segun Dixon-Coles pre-kickoff | goles esperados | `src/cdd_mundial/models/dixon_coles.py` |
| `lambda_away_dc` | Goles esperados del equipo `away` segun Dixon-Coles pre-kickoff | goles esperados | `src/cdd_mundial/models/dixon_coles.py` |
| `p_home_win_dc` | Probabilidad de victoria del equipo `home` derivada de Dixon-Coles | probabilidad `0-1` | `wdl_from_lambdas(...)` en `src/cdd_mundial/models/dixon_coles.py` |
| `p_draw_dc` | Probabilidad de empate derivada de Dixon-Coles | probabilidad `0-1` | `wdl_from_lambdas(...)` en `src/cdd_mundial/models/dixon_coles.py` |
| `p_away_win_dc` | Probabilidad de victoria del equipo `away` derivada de Dixon-Coles | probabilidad `0-1` | `wdl_from_lambdas(...)` en `src/cdd_mundial/models/dixon_coles.py` |
| `target_outcome_idx` | Variable objetivo 3-way del partido | clase discreta | `src/cdd_mundial/models/loading.py` |

### the agent's Discretion
- Elegir la implementacion concreta del materializador del dataset ML, siempre que preserve la disciplina point-in-time y el fallback explicito al baseline cuando falte cobertura `last_5`.
- Elegir hiperparametros razonables y conservadores para el primer XGBoost, siempre que la complejidad permanezca acotada y auditables por holdout.
- Elegir el formato exacto de artefactos intermedios y de evaluacion, siempre que sean reproducibles y trazables.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning y alcance
- `.planning/ROADMAP.md` - objetivo, dependencias y criterios de exito de la Phase 5.
- `.planning/REQUIREMENTS.md` - `ML-01` a `ML-04` definen el alcance funcional y el gate de calibracion/ensemble.
- `.planning/PROJECT.md` - restricciones globales de reproducibilidad, pedagogia y valor metodologico del proyecto.
- `.planning/STATE.md` - estado actual del proyecto y decisiones arrastradas desde fases previas.

### Contratos y artefactos baseline ya existentes
- `src/cdd_mundial/models/loading.py` - target 3-way canonico y semantica de outcome a 90 minutos.
- `src/cdd_mundial/models/dixon_coles.py` - contrato productivo de `predict_lambdas`, `wdl_from_lambdas` y artefactos DC.
- `src/cdd_mundial/models/validation.py` - harness de validacion temporal sobre holdouts, metrica principal y materializacion productiva del baseline.
- `src/cdd_mundial/live/materialization.py` - materializacion reproducible point-in-time y refresh cronologico de history + live rows.
- `src/cdd_mundial/live/pipeline.py` - punto de integracion operativo con la corrida diaria oficial.

### Datos de entrada y cobertura
- `data/processed/historical_matches.parquet` - historico canonico que alimenta features y target.
- `data/external/fixture_2026.csv` - fixture oficial y soporte para `is_host_home` / calendario.
- `data/external/results_2026.csv` - resultados vivos canonicos que alimentan la ruta point-in-time.
- `data/processed/models/elo_history.parquet` - historial Elo pre-partido reutilizable para construir `elo_diff`.
- `data/processed/models/dc_params_*.json` - artefacto productivo DC desde el que se derivan lambdas/probabilidades base.

### Tests y precedentes
- `tests/test_live_pipeline.py` - invariantes de refresh cronologico y orden oficial materialization -> model selection -> simulate -> publish.
- `tests/test_validation_temporal.py` - precedentes de evaluacion temporal del baseline.
- `tests/test_baselines.py` - comparadores baseline ya existentes.
- `notebooks/02_modelos_baseline.ipynb` - narrativa didactica del baseline y sus checks de sanidad.
- `notebooks/04_primer_pronostico_pipeline.ipynb` - patron de notebook como orquestacion sobre APIs productivas.

### Documentacion externa oficial
- `https://xgboost.readthedocs.io/en/stable/python/python_api.html` - API oficial de XGBoost; manejo de `missing=np.nan` y tipos de features.
- `https://xgboost.readthedocs.io/en/stable/treemethod.html` - tree methods oficiales; base de la decision de no normalizar para el dataset canonico XGBoost.
- `https://scikit-learn.org/stable/modules/calibration.html` - documentacion oficial de calibracion probabilistica; tradeoff isotonic vs sigmoid/Platt y soporte multiclass.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/cdd_mundial/live/materialization.py`: ya materializa history + live rows de forma cronologica y reproducible; es el mejor punto de apoyo para un dataset ML point-in-time.
- `src/cdd_mundial/models/loading.py`: ya define el target canonico y la semantica de empate a 90 minutos; el dataset ML no debe redefinirla.
- `src/cdd_mundial/models/dixon_coles.py`: ya expone lambdas y probabilidades estructurales reutilizables como features.
- `src/cdd_mundial/models/validation.py`: ya contiene el patron correcto de holdouts y comparacion por log-loss/Brier/RPS.

### Established Patterns
- El proyecto favorece materializacion reproducible, fechada y auditable sobre atajos de exploracion.
- Las decisiones point-in-time y anti-leakage son mas importantes que exprimir cobertura total del dataset.
- Los notebooks importan codigo productivo; la logica autoritativa vive en `src/`.
- El baseline es el comparador y fallback operativo oficial; la fase ML no puede degradar esa estabilidad.

### Integration Points
- El dataset ML debe salir de una ruta que consuma el historico canonico y, cuando aplique, el estado live ya materializado.
- La evaluacion ML debe acoplarse al mismo calendario de holdouts que `models/validation.py`.
- Si un candidato gana el gate, la integracion operativa ocurre via publicacion dual dentro del pipeline live, no por reemplazo inmediato.

</code_context>

<specifics>
## Specific Ideas

- El primer XGBoost debe mantenerse pequeno y auditable: pocas features, profundidad acotada y comparacion honesta por holdout.
- La ausencia de ranking FIFA point-in-time no se debe ocultar ni maquillar; se documenta como feature opcional no disponible si aplica.
- El dataset ML v1 debe ser legible por humanos: unidades naturales, sin escalado y con semantica explicita de cada columna.

</specifics>

<deferred>
## Deferred Ideas

- Serie historica reproducible de ranking FIFA si aparece una fuente limpia y point-in-time.
- Features adicionales por recencia ponderada, ventanas multiples o proxies mas sofisticadas; fuera de v1 mientras no prueben mejora real.
- Promocion directa del ensemble como reemplazo unico del baseline; diferida a evidencia operacional posterior a la publicacion dual.

</deferred>

---

*Phase: 05-ml-ensemble-upgrade-gated*
*Context gathered: 2026-06-15*
