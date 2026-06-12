# Phase 2: Modelos Baseline — Discussion Log

**Phase:** 02 — Modelos Baseline (Elo + Dixon-Coles)
**Date:** 2026-06-12
**Facilitator:** Antigravity (gsd-discuss-phase)
**Duration:** ~5 min (modo exprés — deadline 27-jun)

## Areas Selected

El usuario seleccionó discutir: **Parámetros del Elo dinámico custom**.
Las otras 3 áreas (decaimiento Dixon-Coles, frontera de entrenamiento, nivel matemático de notebooks) se resolvieron en preguntas compactas adicionales tras el área seleccionada.

---

## Area 1: Parámetros del Elo dinámico custom

### Q1: ¿Cómo definimos los valores de K por tipo de torneo?
- Options presented: Optimización (scipy/grid-search) | Valores fijos WFE | Híbrido init WFE + ajuste fino
- **Selected:** Valores de la literatura World Football Elo como punto de partida fijo
- **Rationale del usuario:** Más rápido de implementar; deadline 27-jun

### Q2: ¿Cómo tratamos la ventaja local en el Elo?
- Options presented: Sin ventaja en partidos neutrales (ventaja = 0) | Ventaja anfitrión solo MEX/USA/CAN
- **Selected:** Ventaja de anfitrión solo para MEX/USA/CAN — constante aditiva fija
- **Notes:** Aplica solo durante el Mundial 2026 en sedes de los países anfitriones

### Q3: ¿Qué fórmula para el multiplicador de margen de victoria?
- Options presented: Fórmula WFE estándar log(|diff|+1) × factor | Sin multiplicador | Lineal simple con cap
- **Selected:** Fórmula WFE estándar con corrección por Δ_Elo

---

## Additional Compact Questions

### Q4: Dixon-Coles — ¿Función de decaimiento temporal?
- Options presented: Exponencial ~2 años half-life (paper original) | Ventana fija 4 años | Sin decaimiento
- **Selected:** Decaimiento exponencial, ξ estándar de la literatura (half-life ~2 años)

### Q5: Dixon-Coles — ¿Frontera de entrenamiento?
- Options presented: Todo el histórico hasta hoy (incl. partidos Mundial 2026 jugados) | Excluir partidos 2026 | Corte fijo 2026-06-10
- **Selected:** Todo el histórico hasta hoy — sin leakage porque el entrenamiento es previo al pronóstico

### Q6: Notebooks — ¿Nivel de derivación matemática?
- Options presented: Derivar matemática core (corrección ρ, log-likelihood, gradiente) | Solo code + interpretación
- **Selected:** Derivar matemática core — nivel ingeniería/maestría, diferenciador de portafolio

---

## Decisions Captured

| ID | Decision | Value |
|----|----------|-------|
| D-01 | K por torneo | Valores fijos WFE (no optimizar en Phase 2) |
| D-02 | Ventaja local | Constante aditiva solo MEX/USA/CAN en Mundial 2026 |
| D-03 | Multiplicador margen | log(\|diff\|+1) × factor WFE con corrección Δ_Elo |
| D-06 | Decaimiento temporal DC | Exponencial, half-life ~2 años (ξ ≈ 0.0018/día) |
| D-07 | Frontera entrenamiento | Todo el histórico hasta fecha de ejecución |
| D-14 | Profundidad matemática | Derivar ρ, log-likelihood y gradiente en notebook |

## Deferred Ideas

- Optimización de K por holdout (aplazado a Phase 2 cierre o post-mortem)
- Re-entrenamiento incremental online (aplazado a Phase 4/6)
- De-margin multi-bookmaker / Shin (v2)
- Valor de plantilla Transfermarkt (v2)

## Agent Discretion Items

- Punto de inicio de ratings Elo (1000 para todos vs. warm-start desde eloratings snapshot) — planner decide
- Cap de goles en integración matriz DC (0-10 o similar) — planner decide
- Estructura de archivos de parámetros del modelo (JSON, pickle, parquet) — planner decide
