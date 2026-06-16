# Phase 05: ML + Ensemble (upgrade gated) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 05-ml-ensemble-upgrade-gated
**Areas discussed:** matriz de features v1, ranking FIFA point-in-time, topologia del ensemble, calibracion, promocion al pipeline en vivo

---

## Matriz de features v1

| Option | Description | Selected |
|--------|-------------|----------|
| A | `elo_diff + forma reciente + rolling de goles + host + descanso` | |
| B | Lo anterior mas salidas estructurales del baseline (`lambda_home`, `lambda_away`, `p_win/draw/loss` DC) | x |
| C | Solo senales crudas sin salidas del baseline | |

**User's choice:** B
**Notes:** El dataset queda como meta-modelo sobre senales crudas y baseline estructural. Luego se fijo un set de 12 features.

---

## Ventana de forma reciente

| Option | Description | Selected |
|--------|-------------|----------|
| A | `last_5` fijo | x |
| B | `last_3` fijo | |
| C | `last_3` y `last_5` | |

**User's choice:** A
**Notes:** Se priorizo estabilidad e interpretabilidad para v1.

---

## Subdecisiones del dataset

| Option | Description | Selected |
|--------|-------------|----------|
| A | Fila ML solo si ambos equipos tienen al menos 5 partidos previos; si no, fallback al baseline | x |
| A | Sin normalizacion para el dataset canonico XGBoost | x |
| B | `form_points` como promedio de puntos por partido | x |
| B | rollings de goles como promedios por partido | x |

**User's choice:** `1 - A, 2 - A, 3 - B, 4 - B`
**Notes:** Se adopto integramente el bundle recomendado.

---

## Ranking FIFA point-in-time

| Option | Description | Selected |
|--------|-------------|----------|
| A | Requerimiento duro: construir serie historica y usarla obligatoriamente | |
| B | Feature opcional gated; no bloquea la fase | x |
| C | Sustitucion explicita por proxies existentes | |

**User's choice:** B
**Notes:** Si no aparece una fuente reproducible y limpia, la omision se documenta sin bloquear la fase.

---

## Topologia del ensemble

| Option | Description | Selected |
|--------|-------------|----------|
| A | ML compite solo; ensemble despues si agrega valor | |
| B | Ensemble desde el inicio | |
| C | Comparar baseline vs ML solo vs ensemble | x |

**User's choice:** C
**Notes:** Se eligio la comparacion metodologicamente mas honesta.

---

## Calibracion

| Option | Description | Selected |
|--------|-------------|----------|
| A | Calibrar solo el candidato final | |
| B | Calibrar ML solo y ensemble por separado | x |
| C | No calibrar en v1 | |

**User's choice:** B
**Notes:** La comparacion isotonic vs Platt queda dentro de validacion temporal estricta.

---

## Promocion al pipeline en vivo

| Option | Description | Selected |
|--------|-------------|----------|
| A | Reemplazo directo si gana el ensemble | |
| B | Publicacion dual baseline + ensemble | x |
| C | Shadow only | |

**User's choice:** B
**Notes:** Se reduce riesgo operativo y se conserva continuidad del baseline.

---

## the agent's Discretion

- Elegir implementacion concreta del materializador del dataset ML.
- Elegir hiperparametros conservadores del primer XGBoost.
- Elegir formato exacto de artefactos intermedios y de evaluacion.

## Deferred Ideas

- Serie historica reproducible de ranking FIFA si aparece una fuente limpia.
- Features adicionales con ventanas multiples o ponderacion por recencia.
- Promocion directa del ensemble como reemplazo unico del baseline.
