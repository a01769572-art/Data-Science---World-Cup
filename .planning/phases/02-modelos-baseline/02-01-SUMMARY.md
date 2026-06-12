---
phase: 02-modelos-baseline
plan: 01
subsystem: models
tags: [elo, dixon-coles, scipy, scikit-learn, rps, brier, pandera, kfactor]

# Dependency graph
requires:
  - phase: 01-fundacion-datos
    provides: historical_matches.parquet validado (49,405 partidos), contracts.py (HistoricalMatchesSchema), patron identities.py de fallo ruidoso
provides:
  - Paquete cdd_mundial.models con tournaments/loading/metrics
  - TournamentKTable: clasificador torneo->K-factor WFE (60/50/40/30/20) con fallo ruidoso
  - data/external/tournament_k_factors.csv: tabla revisada de los 200 strings reales
  - load_matches(): cargador canonico con date datetime, outcome_90 y outcome_idx (ET/shootout => empate 90')
  - rps() y brier_multiclass() verificadas contra valores a mano
  - Wave 0: scipy/sklearn/matplotlib/seaborn/joblib instalados y pineados
affects: [02-02 elo, 02-03 dixon-coles, 02-04 validacion, 03 simulador, 05 ml]

# Tech tracking
tech-stack:
  added: [scipy~=1.17, scikit-learn~=1.9, matplotlib~=3.10, seaborn==0.13.2, joblib>=1.4]
  patterns: [tabla CSV revisada + from_csv + excepcion nombrada con fallo ruidoso, validar pandera ANTES de mutar columnas, TDD RED/GREEN por feature]

key-files:
  created:
    - src/cdd_mundial/models/__init__.py
    - src/cdd_mundial/models/tournaments.py
    - src/cdd_mundial/models/loading.py
    - src/cdd_mundial/models/metrics.py
    - data/external/tournament_k_factors.csv
    - tests/test_tournaments.py
    - tests/test_loading.py
    - tests/test_metrics.py
  modified:
    - pyproject.toml
    - tests/test_repository.py
    - .gitignore

key-decisions:
  - "Tabla K canonica WFE de 5 niveles (60/50/40/30/20): continentales = 50, no 60 como decia D-01 literal — D-01 mismo ordena seguir la fuente canonica (pitfall 3)"
  - "Nations Leagues (UEFA y CONCACAF) clasifican como qualifier_major K=40, anotadas A2 segun assumption log del RESEARCH"
  - "La lista continental usa los 7 strings exactos del plan; predecesores historicos (CONCACAF Championship, NAFC/CCCF) quedan en other K=30 — impacto marginal por decaimiento temporal"
  - "src/cdd_mundial/models/ requiere negacion en .gitignore porque la regla models/ (artefactos generados) capturaba el paquete fuente"

patterns-established:
  - "Clasificadores de dominio: tabla CSV revisada + clase from_csv + lookup exacto + excepcion LookupError nombrada (replica identities.py)"
  - "Cargadores canonicos: Schema.validate() antes de cualquier mutacion; conversion de date una sola vez; orden deterministico (date, match_id)"

requirements-completed: [MODEL-01, MODEL-04]

# Metrics
duration: 14min
completed: 2026-06-12
---

# Phase 2 Plan 01: Fundaciones de modelos baseline Summary

**Paquete cdd_mundial.models con clasificador torneo→K WFE sobre los 200 strings reales, cargador canónico con outcome de 90' (ET/shootout ⇒ empate) y métricas RPS/Brier exactas, más las 5 dependencias Wave 0 pineadas**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-12T14:28:03Z
- **Completed:** 2026-06-12T14:42:11Z
- **Tasks:** 3 (2 en TDD RED/GREEN)
- **Files modified:** 11

## Accomplishments

- Wave 0 desbloqueada: scipy 1.17.1, scikit-learn 1.9.0, matplotlib 3.11.0, seaborn 0.13.2 y joblib 1.5.3 instalados en el venv y pineados en pyproject (sin penaltyblog/statsmodels)
- Los 200 strings de torneo del parquet real mapean a K ∈ {20,30,40,50,60}; strings desconocidos lanzan `UnknownTournamentError` (test data_acceptance de cobertura total verde)
- `load_matches()` etiqueta los partidos con ET/penales como empate de 90' (regla D-05/pitfall 6) y entrega fechas datetime ordenadas determinísticamente
- RPS y Brier multiclase devuelven valores exactos contra casos a mano (5/18 y 2/3 para el pronóstico uniforme)
- Suite completa: 120 tests verdes (107 previos + 13 nuevos), ruff limpio

## Task Commits

Each task was committed atomically:

1. **Task 1: Dependencias Wave 0** - `29e4d1e` (chore)
2. **Task 2: Clasificador torneo→K** - `3321f4e` (test, RED) + `4293292` (feat, GREEN)
3. **Task 3: load_matches + métricas** - `241915e` (test, RED) + `941ccfd` (feat, GREEN)

## Files Created/Modified

- `src/cdd_mundial/models/__init__.py` - Init del paquete (solo docstring; re-exports llegan en 02-03)
- `src/cdd_mundial/models/tournaments.py` - `TournamentKTable` + `UnknownTournamentError` + `K_CATEGORIES`
- `src/cdd_mundial/models/loading.py` - `load_matches()` + `OUTCOME_LABELS`
- `src/cdd_mundial/models/metrics.py` - `rps()` + `brier_multiclass()` (verbatim del RESEARCH)
- `data/external/tournament_k_factors.csv` - 200 filas revisadas (1 wc, 7 continental, 20 qualifier_major, 171 other, 1 friendly)
- `tests/test_tournaments.py` / `tests/test_loading.py` / `tests/test_metrics.py` - 13 tests nuevos
- `pyproject.toml` - 5 dependencias Wave 0 añadidas
- `tests/test_repository.py` - guard de pins actualizado con las 5 entradas
- `.gitignore` - negación `!src/cdd_mundial/models/`

## Decisions Made

- **Tabla K canónica WFE (continentales = 50):** D-01 literal decía 60 para continentales, pero la cláusula de D-01 ordena seguir la fuente canónica WFE, que usa 60/50/40/30/20 (pitfall 3 del RESEARCH). El plan ya lo resolvía así.
- **Nations Leagues → K=40 (nota A2):** asunción A2 del RESEARCH, anotada en la columna `note` del CSV.
- **Predecesores continentales en other (30):** `CONCACAF Championship` (predecesor del Gold Cup) y similares no están en la lista exacta del plan; quedan en K=30. Impacto marginal: partidos antiguos con peso temporal casi nulo. Revisable en 02-02 si el Spearman vs eloratings lo sugiere.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Guard de pins de pyproject desactualizado**
- **Found during:** Task 1 (dependencias Wave 0)
- **Issue:** `tests/test_repository.py::test_python_and_tournament_safe_dependency_pins` asserta el conjunto EXACTO de dependencias; añadir las 5 nuevas rompía la suite (criterio de aceptación exige suite verde)
- **Fix:** Añadidas las 5 entradas nuevas al set `expected` del test (el guard sigue protegiendo los pins del torneo)
- **Files modified:** tests/test_repository.py
- **Verification:** suite completa 107/107 verde tras el fix
- **Committed in:** 29e4d1e (Task 1 commit)

**2. [Rule 3 - Blocking] Regla `models/` del .gitignore capturaba el paquete fuente**
- **Found during:** Task 2 (commit GREEN)
- **Issue:** `.gitignore` ignora `models/` (artefactos generados de modelo) en cualquier nivel, lo que bloqueaba `git add src/cdd_mundial/models/`
- **Fix:** Negación `!src/cdd_mundial/models/` añadida bajo la regla, con comentario; `models/` sigue ignorando el directorio de artefactos
- **Files modified:** .gitignore
- **Verification:** `git check-ignore` exit 1 sobre los archivos del paquete; `tests/test_repository.py` 6/6 verde (la línea `models/` sigue presente)
- **Committed in:** 4293292 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Ambos fixes eran prerequisitos mecánicos para commitear el trabajo planeado. Sin scope creep.

## TDD Gate Compliance

Tasks 2 y 3 siguieron RED→GREEN: commits `test(...)` (3321f4e, 241915e) preceden a sus `feat(...)` (4293292, 941ccfd). Ambos RED fallaron por colección (módulo inexistente) antes de implementar. No hubo fase REFACTOR (el código GREEN salió limpio bajo ruff).

## Verification Results

- `pytest tests/test_tournaments.py tests/test_loading.py tests/test_metrics.py -x -q` → 13 passed
- `pytest -q` (suite completa) → 120 passed
- `TournamentKTable.from_csv().k_factor('FIFA World Cup')` → imprime `60`
- `ruff check` sobre los archivos nuevos → All checks passed

## Issues Encountered

None — más allá de las 2 desviaciones auto-corregidas arriba.

## Known Stubs

None — todas las funciones operan sobre datos reales; el re-export de `predict_lambdas` en `__init__.py` se difiere deliberadamente al plan 02-03 (instrucción explícita del plan).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 2 desbloqueada: Elo (02-02) y Dixon-Coles (02-03) pueden correr en paralelo consumiendo `load_matches()`, `TournamentKTable` y `metrics`
- Los contratos de interfaz del plan (firmas de `k_factor`, `load_matches`, `rps`, `brier_multiclass`) quedaron exactamente como se especificaron — los planes 02-02/03/04 los consumen a ciegas

---
*Phase: 02-modelos-baseline*
*Completed: 2026-06-12*

## Self-Check: PASSED

Todos los archivos creados existen en disco y los 5 commits de tareas estan en el historial.
