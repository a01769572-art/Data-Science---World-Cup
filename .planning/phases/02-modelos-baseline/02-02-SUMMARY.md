---
phase: 02-modelos-baseline
plan: 02
subsystem: models
tags: [elo, wfe, ordered-logit, spearman, provenance, pandera, scipy]

# Dependency graph
requires:
  - phase: 02-modelos-baseline
    plan: 01
    provides: load_matches() con outcome_90/outcome_idx, TournamentKTable (K WFE 60/50/40/30/20), metrics RPS/Brier
  - phase: 01-fundacion-datos
    provides: historical_matches.parquet (49,405 partidos), elo_current.parquet (snapshot eloratings.net), teams.csv, provenance.py
provides:
  - elo.py: expected_score/margin_factor/elo_update (WFE + margen 538 con rama de empate), recompute_elo, ratings_asof, snapshot_ratings, materialize_elo + CLI
  - baselines.py: uniform_wdl, OrderedLogit, fit_solo_elo (MLE L-BFGS-B), solo_elo_probs — comparadores del gate D-13
  - data/processed/models/elo_history.parquet: rating pre/post point-in-time por equipo y partido (insumo Phase 5 ML-01)
  - data/processed/models/elo_ratings.parquet: snapshot actual recomputado (MODEL-01), Spearman 0.979 vs eloratings.net
  - EloHistorySchema en contracts.py (strict+coerce, k_factor isin {20,30,40,50,60})
affects: [02-03 dixon-coles, 02-04 validacion, 03 simulador, 05 ml]

# Tech tracking
tech-stack:
  added: []
  patterns: [recompute secuencial determinista (date, match_id) con estado dict, MLE con reparametrizacion libre (c1, d, log_s) sin bounds, defaultdict para ratings point-in-time con default 1000]

key-files:
  created:
    - src/cdd_mundial/models/elo.py
    - src/cdd_mundial/models/baselines.py
    - tests/test_elo.py
    - tests/test_baselines.py
    - data/metadata/elo_history.parquet.provenance.json
    - data/metadata/elo_ratings.parquet.provenance.json
  modified:
    - src/cdd_mundial/data/contracts.py

key-decisions:
  - "Ventaja local +100 aplicada a home_team_id cuando neutral==False en TODO el historico (decision del Director, OQ1) — la restriccion MEX/USA/CAN de D-02 aplica solo a prediccion 2026"
  - "Margen de victoria = variante FiveThirtyEight con rama de empate factor 1.0 (pitfall 1: la formula cruda congelaria 23% de partidos), documentado con atribucion en docstring"
  - "Baseline solo-Elo = ordered logit (resuelve OQ4 con la recomendacion del RESEARCH): MLE sobre (c1, d, log_s) libres con c2=c1+exp(d), scale=exp(log_s)"
  - "Cold-start 1000 sobre todo el historico (D-04 resuelto): warm-start inviable, el snapshot solo cubre 48 de 336 equipos; validacion por rangos (Spearman), nunca niveles absolutos"

requirements-completed: [MODEL-01]

# Metrics
duration: 9min
completed: 2026-06-12
---

# Phase 2 Plan 02: Elo dinámico + baselines comparadores Summary

**Elo WFE custom recomputado secuencialmente desde 1000 sobre los 49,405 partidos (K por torneo, +100 local no neutral, margen 538 con rama de empate, shootout=empate) con Spearman 0.979 vs eloratings.net, más el baseline solo-Elo ordered logit del gate D-13**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-12T14:47:00Z
- **Completed:** 2026-06-12T14:56:36Z
- **Tasks:** 3 (2 en TDD RED/GREEN)
- **Files modified:** 7 (+ 2 parquet regenerables no versionados)

## Accomplishments

- Matemática Elo verificada contra valores a mano: update 1-0 neutral K=60 → 1520.7944; empate 1700 vs 1300 → 1683.6364 (el empate SÍ mueve ratings, pitfall 1); shootout 3-3 produce el mismo delta que un empate (D-05); +100 local eleva We sobre 0.5
- Recomputación secuencial completa: 49,405 partidos, 336 equipos, top = España (coincide con el #1 de eloratings.net); corre en segundos sin numba
- **Gate duro MODEL-01: Spearman 0.979 ≥ 0.9** entre el Elo recomputado (cold-start 1000) y el snapshot independiente de eloratings.net sobre las 48 selecciones del Mundial — comparación por rangos, nunca niveles (pitfall 2/9)
- Artefactos materializados con provenance: `elo_history.parquet` (98,810 filas long-format, point-in-time para Phase 5) y `elo_ratings.parquet` (snapshot EloRatingsSchema), ambos con manifiesto sha256 que incluye el checksum del parquet de entrada (T-02-05/06)
- Baseline solo-Elo: ordered logit recupera (c1=-120, c2=80, scale=200) desde 20,000 outcomes sintéticos seed 42 dentro de tolerancias; probabilidades suman 1, monótonas en dr
- Suite completa: 133 tests verdes (120 previos + 13 nuevos), ruff limpio

## Task Commits

Each task was committed atomically:

1. **Task 1: Matemática Elo WFE + recomputación** - `a7e27e1` (test, RED) + `a051324` (feat, GREEN)
2. **Task 2: Materialización + schemas + Spearman** - `d7739f5` (feat)
3. **Task 3: Baselines uniforme + solo-Elo** - `9436b94` (test, RED) + `1432928` (feat, GREEN)

## Files Created/Modified

- `src/cdd_mundial/models/elo.py` - Matemática WFE (verbatim del RESEARCH), `recompute_elo`, `ratings_asof` (default 1000 vía defaultdict), `snapshot_ratings`, `materialize_elo`, `verify_elo_materialization`, CLI argparse
- `src/cdd_mundial/models/baselines.py` - `uniform_wdl`, `OrderedLogit` (frozen, invariantes c1<c2 y scale>0), `solo_elo_probs` (clip 1e-12), `fit_solo_elo` (L-BFGS-B)
- `src/cdd_mundial/data/contracts.py` - `EloHistorySchema(CanonicalSchema)` con check one_row_per_team_per_match
- `tests/test_elo.py` - 9 tests (7 unit + 2 data_acceptance con Spearman)
- `tests/test_baselines.py` - 4 tests (incluida recuperación sintética seed 42)
- `data/metadata/elo_*.parquet.provenance.json` - 2 manifiestos con sha256
- `data/processed/models/elo_history.parquet`, `elo_ratings.parquet` - materializados en disco, NO versionados (data/processed/ gitignored); **regenerar con `python -m cdd_mundial.models.elo`**

## Decisions Made

- **+100 local en todo el histórico no neutral (OQ1):** la reconciliación WFE del Director — el flag `neutral` validado del parquet decide; D-02 (solo MEX/USA/CAN) aplica únicamente a la predicción 2026
- **Margen 538 con rama de empate = 1.0:** atribución documentada en docstring (NO es la tabla G de eloratings.net); evita congelar el 22.7% de partidos empatados
- **Ordered logit para solo-Elo (OQ4):** 3 parámetros, reparametrización libre garantiza invariantes sin bounds; ValueError ruidoso si el optimizador no converge
- **Cold-start 1000 (D-04):** el snapshot eloratings solo cubre 48/336 equipos — warm-start inviable; la validación es por correlación de rangos

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] `snapshot_ratings` necesita `source_version` como parámetro**
- **Found during:** Task 2
- **Issue:** El plan especifica la firma `snapshot_ratings(history)` pero exige `source_version = source_version del parquet de entrada` — el history long-format no porta esa columna
- **Fix:** Firma `snapshot_ratings(history, source_version)`; `materialize_elo` la extrae del parquet de entrada y falla si hay más de una versión
- **Files modified:** src/cdd_mundial/models/elo.py
- **Verification:** EloRatingsSchema.validate pasa; test data_acceptance verde
- **Commit:** d7739f5

**2. [Rule 3 - Blocking] Nombre real de los manifiestos provenance**
- **Found during:** Task 2
- **Issue:** El frontmatter del plan lista `data/metadata/elo_history.provenance.json`, pero `write_provenance_manifest` (API existente, no modificable) nombra `{local_path.name}.provenance.json` → `elo_history.parquet.provenance.json`
- **Fix:** Se respeta la convención existente del repo (igual que `historical_matches.parquet.provenance.json` de Phase 1)
- **Files modified:** ninguno (solo rutas de artefactos)
- **Verification:** ambos manifiestos existen con campo sha256
- **Commit:** d7739f5

**3. [Rule 1 - Bug] Import sin uso en test RED**
- **Found during:** Task 3 (GREEN)
- **Issue:** `import pytest` quedó sin uso en tests/test_baselines.py (ruff F401)
- **Fix:** Import eliminado
- **Files modified:** tests/test_baselines.py
- **Verification:** ruff limpio, 4 tests verdes
- **Commit:** 1432928

---

**Total deviations:** 3 auto-fixed (1 missing critical, 1 blocking, 1 bug). **Impact:** ajustes mecánicos sin scope creep; ningún cambio arquitectural.

**Nota (rama anticipada por el plan):** `data/processed/` está gitignored, así que los 2 parquet NO van al repo — el plan lo preveía ("si lo está, commitear solo los manifiestos y documentar la regeneración"). Regeneración determinista: `.\.venv\python.exe -m cdd_mundial.models.elo` (orden date, match_id + sha256 del input en el manifiesto, T-02-06).

## TDD Gate Compliance

Tasks 1 y 3 siguieron RED→GREEN: commits `test(...)` (a7e27e1, 9436b94) preceden a sus `feat(...)` (a051324, 1432928). Ambos RED fallaron por colección (módulo inexistente). Sin fase REFACTOR (GREEN salió limpio bajo ruff salvo el F401 corregido dentro del propio ciclo de Task 3). Task 2 no es TDD (materialización sobre datos reales con tests de aceptación).

## Verification Results

- `pytest tests/test_elo.py tests/test_baselines.py -x -q` → 13 passed (unit + data_acceptance)
- `python -m cdd_mundial.models.elo --verify-only` → JSON `{"matches": 49405, "teams": 336, "top_team": "spain", "top_rating": 1601.98}` (teams > 300 ✓)
- `pytest -q` (suite completa) → 133 passed
- Spearman recomputado vs eloratings.net (48 selecciones) = **0.9787** ≥ 0.9

## Threat Model Compliance

- T-02-05 (tampering parquet): EloHistorySchema/EloRatingsSchema strict+coerce al escribir Y al leer (`verify_elo_materialization` re-valida); sha256 en manifiestos ✓
- T-02-06 (reproducibilidad): orden determinista (date, match_id) heredado de load_matches; sha256 del input en notes; CLI `--verify-only` ✓
- T-02-07 (deriva silenciosa): gate data_acceptance Spearman ≥ 0.9 vs snapshot independiente ✓
- T-02-08 (secretos): accepted — artefactos solo contienen ratings derivados de datos CC0

## Issues Encountered

None — más allá de las 3 desviaciones auto-corregidas arriba.

## Known Stubs

None — todas las funciones operan sobre datos reales; los artefactos están materializados y validados.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- El contrato para 02-04 quedó exactamente como el plan lo especifica: `ratings_asof(history, date)` (default 1000), `uniform_wdl()`, `OrderedLogit(c1, c2, scale)`, `fit_solo_elo(dr, outcome_idx)`, `solo_elo_probs(dr, model)`
- 02-03 (Dixon-Coles, Wave 2 paralela) no depende de este plan; 02-04 (gate D-13) ya tiene sus dos comparadores naïve listos
- `elo_history.parquet` point-in-time queda disponible como feature ML-01 de Phase 5

---
*Phase: 02-modelos-baseline*
*Completed: 2026-06-12*

## Self-Check: PASSED

Los 8 archivos clave existen en disco (4 código/tests + 2 parquet + 2 manifiestos) y los 5 commits de tareas (a7e27e1, a051324, d7739f5, 9436b94, 1432928) están en el historial.
