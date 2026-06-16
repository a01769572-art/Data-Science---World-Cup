---
phase: 05-ml-ensemble-upgrade-gated
plan: "05"
subsystem: testing
tags: [xgboost, calibration, isotonic, platt, log-loss, gate, train-serve-identity]

# Dependency graph
requires:
  - phase: 05-03
    provides: "run_ml_comparison + evaluate_ml_gate + MulticlassCalibrator (calibracion isotonic/Platt/none + seleccion empirica)"
  - phase: 05-04
    provides: "Integracion live opt-in (ml_selection/pipeline) que consume el veredicto del gate"
provides:
  - "Identidad train/serve explicita y verificable dentro de run_ml_comparison: el holdout se puntua con el MISMO modelo (inner_model) sobre cuyas probabilidades se ajustaron calibradores y peso de ensemble"
  - "Regresion automatizada CR-01 (exactamente un modelo por holdout) que falla si se reintroduce el mismatch train/serve"
  - "Cobertura de calibracion enfocada al flujo reparado (contrato de probabilidad valida + la evidencia de seleccion describe la distribucion realmente puntuada)"
  - "Campos de auditoria scoring_model / n_inner_fit / n_inner_cal en el reporte por holdout"
affects: [verificacion-fase-05, gate-promocion, ML-03, ML-04, live-selection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Train/serve identity: el productor de probabilidades raw usado para fit/seleccion de calibracion es el mismo que produce las probabilidades raw del holdout que esos calibradores transforman"
    - "Regresion por identidad de instancia: instrumentar predict_proba/fit por object-id para probar identidad de modelo, no solo validez estructural"

key-files:
  created: []
  modified:
    - "src/cdd_mundial/models/ml_validation.py"
    - "tests/test_ml_validation.py"
    - "tests/test_ml_calibration.py"

key-decisions:
  - "[Phase 05]: CR-01 cerrado puntuando el holdout con inner_model (el modelo de fit/calibracion), eliminando el re-fit de final_model; los mapas isotonic/sigmoid por clase y el peso del ensemble se aplican a la misma distribucion sobre la que se ajustaron, asi que las entradas del gate quedan honestamente calibradas (T-05-13)."
  - "[Phase 05]: La prueba de regresion CR-01 prueba IDENTIDAD de modelo (un solo fit por holdout via instrumentacion por object-id), no solo validez de distribucion; cualquier segundo modelo entre fit-de-calibracion y scoring del holdout vuelve a fallar el test."

patterns-established:
  - "Anti-CR-01: el reporte por holdout registra scoring_model y los conteos inner_fit/inner_cal para que la identidad train/serve sea auditable desde el artefacto."

requirements-completed: [ML-03, ML-04]

# Metrics
duration: 18min
completed: 2026-06-16
---

# Phase 5 Plan 05: Cierre de CR-01 (identidad train/serve en run_ml_comparison) Summary

**El gate de promocion y la comparacion isotonic-vs-Platt vuelven a ser metodologicamente validos: el holdout se puntua con el mismo modelo cuyas probabilidades alimentaron calibradores y peso de ensemble, y una regresion automatizada bloquea cualquier reaparicion del mismatch.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-16 (sesion de ejecucion 05-05)
- **Completed:** 2026-06-16
- **Tasks:** 2 (ambas TDD)
- **Files modified:** 3

## Accomplishments
- **Defecto CR-01 eliminado en `run_ml_comparison`:** se retiro el re-fit de `final_model` sobre todas las filas pre-cutoff; el holdout ahora se puntua con `inner_model` (el modelo sobre cuyas salidas `ml_calibrator`, `ens_calibrator` y `weight` fueron seleccionados/ajustados). Las probabilidades calibradas que ve el gate provienen de la misma distribucion sobre la que se aprendieron los mapas — comparacion honesta baseline-vs-ml-vs-ensemble restaurada.
- **Auditabilidad:** el reporte por holdout ahora expone `scoring_model="inner_calibration_model"`, `n_inner_fit` y `n_inner_cal`, de modo que la identidad train/serve es verificable desde el artefacto JSON, no solo desde el codigo.
- **Regresion CR-01 (RED -> GREEN demostrado):** test que instrumenta `MulticlassXGBoost.fit/predict_proba` por object-id y exige exactamente un modelo por holdout. Contra el codigo defectuoso reportaba `8 != 4` (inner + final por holdout); con el arreglo pasa. Prueba IDENTIDAD de modelo, no validez estructural.
- **Cobertura de calibracion enfocada al flujo reparado:** dos pruebas nuevas en `test_ml_calibration.py` que congelan (a) que un calibrador ajustado sobre la distribucion de un productor preserva masa al aplicarse a filas posteriores del MISMO productor, y (b) que la eleccion empirica isotonic/Platt/none describe la distribucion que realmente se puntua.

## Task Commits

Cada tarea fue commiteada atomicamente:

1. **Task 1: Reparar identidad train/serve en run_ml_comparison** - `3f1e504` (fix) — incluye la fuente corregida y la regresion CR-01 en `test_ml_validation.py` (TDD RED demostrado contra el codigo defectuoso antes del arreglo, luego GREEN).
2. **Task 2: Cobertura de calibracion enfocada al flujo reparado** - `7ff5724` (test).

**Plan metadata:** (este SUMMARY + STATE/ROADMAP/REQUIREMENTS) — ver commit `docs(05-05)` final.

_Nota TDD: el ciclo RED/GREEN se ejecuto y verifico; al ser una correccion localizada cuyo guardrail vive en uno de los archivos de la Tarea 1, fix + test se consolidan en `3f1e504` con evidencia RED registrada abajo (Issues Encountered)._

## Files Created/Modified
- `src/cdd_mundial/models/ml_validation.py` — `run_ml_comparison` puntua el holdout con `inner_model` (paso 4 reescrito); docstring actualizado a la invariante T-05-13; nuevos campos de auditoria `scoring_model`/`n_inner_fit`/`n_inner_cal` en el reporte por holdout.
- `tests/test_ml_validation.py` — nueva regresion `test_comparison_scores_holdout_with_the_same_model_calibrators_were_fit_on` (un modelo por holdout, identidad por object-id).
- `tests/test_ml_calibration.py` — `test_calibrator_applied_to_same_producers_later_rows_stays_valid` y `test_calibration_choice_describes_the_distribution_it_is_applied_to`.

## Decisions Made
- **Direccion de reparacion: puntuar con `inner_model`, no re-derivar desde `final_model`.** El gap report ofrecia dos rutas (puntuar con el modelo interno, o re-derivar calibradores/peso desde las predicciones held-out del final_model). Se eligio la ruta localizada y mas simple recomendada por el reporte: puntuar con `inner_model`. Trade-off aceptado: el modelo servido usa ~75% de las filas pre-cutoff (inner_fit) en vez del 100%; a cambio se garantiza identidad train/serve sin maquinaria adicional de re-derivacion. Coherente con T-05-13 ("Enforce same-producer train/serve identity").
- **El test prueba identidad, no forma.** Siguiendo el `<action>` de la Tarea 2 ("prove identity, not just shape or row-sum validity"), la regresion cuenta instancias de modelo por holdout en vez de comparar distribuciones, atrapando el defecto en su raiz.

## Deviations from Plan

None - plan executed exactly as written. No se aplicaron reglas de desviacion (Rules 1-4). No se tocaron pins de dependencias (pandas ~=2.3.3, xgboost ~=3.2). Las warnings WR-01..WR-06 e IN-* del code review quedan fuera de alcance de este plan de cierre (solo CR-01) y no se modificaron.

## Issues Encountered
- **Venv fragil en OneDrive (conocido).** El comando del plan `.\.venv\python.exe -m pytest` falla: el `python.exe` raiz del venv no carga `Lib/site-packages` (su `sys.path` lo omite — sintoma de deshidratacion OneDrive). El interprete funcional es `.\.venv\Scripts\python.exe`, que si resuelve site-packages (pytest 8.4.2, pandas 2.3.3, numpy 2.4.6, sklearn 1.9.0, xgboost 3.2.0 verificados). Todas las suites se corrieron con `Scripts\python.exe`. Sin impacto en codigo; coincide con la memoria "venv-onedrive-fragile".
- **Evidencia RED de CR-01:** contra el codigo defectuoso la regresion fallaba con `AssertionError: expected exactly one model per holdout (train==serve), got 8 == 4` (inner_model + final_model por cada uno de los 4 holdouts). Tras el arreglo: GREEN.

## Verification

Comandos del plan (ejecutados con `.\.venv\Scripts\python.exe`):

- Task 1: `pytest -q tests/test_ml_validation.py -k "comparison or gate" -x` -> **8 passed**.
- Task 2 (a): `pytest -q tests/test_ml_validation.py tests/test_ml_calibration.py -x` -> **28 passed**.
- Task 2 (b): `pytest -q tests/test_ml_selection.py tests/test_live_pipeline.py -k "ml or selection" -x` -> **10 passed**.
- Confianza adicional (suite Phase 5 del reporte de verificacion): `pytest -q test_ml_validation test_ml_calibration test_ml_features test_ml_selection` -> **49 passed** (46 originales + 3 nuevos CR-01).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- **CR-01 cerrado.** ML-03 (gate pre-registrado) y ML-04 (calibracion isotonic-vs-Platt empirica) vuelven a estar honestamente satisfechos: las entradas del gate y la evidencia de seleccion describen ahora la distribucion realmente puntuada en el holdout.
- **Listo para re-verificacion de la Fase 05.** El verificador deberia reconfirmar los criterios #3 y #4 (antes PARTIAL/FAILED por CR-01). El veredicto negativo/positivo del gate, sea cual sea, ahora se calcula sobre insumos validos (D-13: el resultado negativo sigue siendo de primera clase y el baseline sigue publicando).
- **Sin reapertura del resto de la fase.** Feature pipeline, clasificador XGBoost e integracion live quedaron intactos; el cambio es estrictamente local a `run_ml_comparison` mas las dos suites de prueba.
- Warnings del code review (WR-01..WR-06, IN-01..IN-06) permanecen abiertos pero fuera de alcance de este cierre.

## Self-Check: PASSED

- Archivos verificados en disco: `05-05-SUMMARY.md`, `ml_validation.py`, `test_ml_validation.py`, `test_ml_calibration.py` — todos FOUND.
- Commits verificados en git: `3f1e504` (Task 1), `7ff5724` (Task 2) — ambos FOUND.

---
*Phase: 05-ml-ensemble-upgrade-gated*
*Completed: 2026-06-16*
