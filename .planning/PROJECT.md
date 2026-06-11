# CDD-MUNDIAL — Pronósticos del Mundial 2026

## What This Is

Sistema de ciencia de datos end-to-end que pronostica los resultados del Mundial 2026 (11 jun – 19 jul 2026) mediante machine learning y simulación Monte Carlo. Combina modelos estructurales (Elo dinámico, Dixon-Coles) con ML (XGBoost/scikit-learn) en un ensemble calibrado que alimenta simulaciones del torneo completo (≥10,000 corridas), actualizándose tras cada jornada con resultados reales. Es un proyecto de aprendizaje y portafolio para Jesús (estudiante ITESM), donde Claude actúa como gestor de proyecto y hard coder vía MCP Jupyter, y Jesús como Director que toma decisiones metodológicas y valida críticamente.

## Core Value

Un proyecto de portafolio metodológicamente riguroso y profundamente documentado que enseña ciencia de datos end-to-end real — si los pronósticos fallan pero el proceso es sólido y el aprendizaje quedó capturado, el proyecto cumplió.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Base de datos limpia y unificada de partidos internacionales históricos (Kaggle + Elo ratings + fixture oficial 2026)
- [ ] Tabla maestra canónica de selecciones para mapear todas las fuentes
- [ ] Pipeline de features reproducible (Elo dinámico, forma reciente, ranking FIFA, contexto anfitrión)
- [ ] Modelo Dixon-Coles (Poisson bivariado con decaimiento temporal) que produce goles esperados (λ)
- [ ] Clasificador ML (XGBoost/LightGBM) de 3 clases con validación temporal estricta
- [ ] Ensemble ponderado + calibración isotónica de probabilidades
- [ ] Motor de simulación Monte Carlo con reglas FIFA 2026 completas (48 equipos, 12 grupos, mejores terceros, desempates, penales)
- [ ] Simulación condicional al estado real del torneo (partidos jugados se fijan)
- [ ] Pipeline de actualización por jornada (ingesta resultados → re-cálculo → re-simulación → reporte)
- [ ] Reportes de pronóstico por jornada con matplotlib/seaborn
- [ ] Tracking de calibración en vivo (log-loss acumulado vs. benchmarks)
- [ ] Notebooks con estructura didáctica obligatoria: celda MD documenta → celda código → celda MD interpreta
- [ ] Post-mortem de precisión al final del torneo
- [ ] Notas de aprendizaje en Obsidian (SecondBrain) al cerrar cada fase

### Out of Scope

- Dashboard interactivo (Streamlit/Plotly Dash) — la salida elegida es reportes Python estáticos con matplotlib/seaborn; un dashboard puede ser milestone futuro
- Modelos de deep learning — muestras pequeñas en fútbol internacional; gradient boosting + estructurales es el techo razonable
- Apuestas reales / asesoría de apuestas — las cuotas se usan solo como benchmark académico
- Datos de jugadores individuales (lineups, eventos por partido) — complejidad de extracción alta vs. valor marginal para pronóstico a nivel selección en v1
- Scraping pesado de Transfermarkt en v1 — valor de plantilla es feature P2 opcional

## Context

- **Timing crítico:** el Mundial inició HOY (11 jun 2026). El proyecto se construye en modo exprés durante la fase de grupos y gana valor en eliminatorias. Cada día de retraso = partidos sin pronosticar, pero la simulación condicional sigue siendo válida en cualquier punto del torneo.
- **Documento de diseño previo:** `PROYECTO_MUNDIAL_2026.md` en la raíz del repo contiene el diseño detallado (arquitectura de 3 capas, fuentes de datos priorizadas, cronograma exprés, riesgos). Es la referencia de diseño del proyecto.
- **Formato del torneo:** 48 selecciones, 12 grupos de 4, 104 partidos; avanzan 2 por grupo + 8 mejores terceros a Ronda de 32; sedes en México/EUA/Canadá.
- **Fuentes de datos:** Kaggle `martj42/international-football-results` (~48k partidos desde 1872), eloratings.net (scraping), FIFA rankings, fixture oficial 2026, cuotas como benchmark. Usuario tiene cuenta Kaggle sin API key (configurar token o descarga manual única).
- **Workflow LLM↔humano:** Claude escribe todo el código (notebooks vía MCP Jupyter, módulos .py); Jesús decide alcance/metodología, valida supuestos, detecta leakage, aporta conocimiento futbolístico y ejecuta pasos interactivos (logins, descargas).
- **Validación de modelos:** splits temporales estrictos; conjuntos de validación = Mundiales 2018/2022, Euro 2024, Copa América 2024. Accuracy es métrica engañosa en fútbol — log-loss, Brier/RPS y diagramas de confiabilidad son las métricas reales.
- **Entorno:** Windows 11, VS Code, Python 3.11+ (venv `cdd-mundial`), JupyterLab + MCP Jupyter, git. Gemini API key disponible en `~/.claude/.env` para tareas batch auxiliares.

## Constraints

- **Timeline**: El torneo termina el 19 jul 2026 — el baseline (Elo + Dixon-Coles + Monte Carlo) debe estar publicando pronósticos antes del fin de la fase de grupos (27 jun); el ensemble ML es mejora incremental sobre un sistema ya funcionando
- **Pedagogía**: Estructura de notebook obligatoria en TODOS los notebooks: celda markdown que documenta (qué y por qué) → celda de código → celda markdown que interpreta resultados. El repo es material de estudio
- **Tech stack**: Python + pandas/numpy/scipy/scikit-learn/XGBoost; visualización solo matplotlib/seaborn; parquet para datos procesados; pandera para validación de esquemas
- **Datos**: `data/raw/` es inmutable; toda transformación produce archivos nuevos en `data/processed/` con metadatos de extracción
- **Reproducibilidad**: Todo pronóstico debe poder regenerarse desde raw + código versionado; semillas fijas en simulaciones para reportes
- **Repo**: GitHub público — README de calidad portafolio, sin claves ni datos con licencia restrictiva versionados

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Ensemble 3 capas: estructural (Elo+Dixon-Coles) + ML (XGBoost) + mercado (benchmark) | Baseline interpretable y fuerte; ML como mejora medible; cuotas como vara externa | — Pending |
| Dixon-Coles produce las λ para Monte Carlo (no marcadores directos del clasificador) | El simulador necesita distribuciones de goles, no solo probabilidades 1/X/2 | — Pending |
| Validación temporal estricta (nunca aleatoria) | Evitar leakage temporal — error #1 en pronóstico deportivo | — Pending |
| Simulación condicional al estado real del torneo | El torneo ya empezó; partidos jugados se fijan con resultado real | — Pending |
| Salida = reportes estáticos matplotlib/seaborn (no dashboard) | Decisión del Director; prioriza tiempo de modelado sobre frontend | — Pending |
| Notebooks didácticos (MD→code→MD) como requerimiento duro | Core value es aprendizaje + portafolio; el repo debe enseñar | — Pending |
| GitHub público | Valor de portafolio | — Pending |
| Actualización por jornada (no snapshot único) | Diferenciador del proyecto: pronóstico vivo con tracking de calibración real | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-11 after initialization*
