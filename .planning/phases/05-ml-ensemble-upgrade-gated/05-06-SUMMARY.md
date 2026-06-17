---
phase: 05-ml-ensemble-upgrade-gated
plan: "06"
subsystem: testing
tags: [cr-01, train-serve-identity, regression-guard, calibration, isotonic, platt, wr-01]

# Dependency graph
requires:
  - phase: 05-05
    provides: "Identidad train/serve en run_ml_comparison (scoring_model = inner_model, final_model eliminado) + regresión CR-01 basada en conteo de fits"
provides:
  - "Guardrail de regresión CR-01 que prueba IDENTIDAD de modelo/distribución por holdout (no conteo de fits): el array que la ml_calibrator.transform recibe al puntuar el holdout es una salida VERBATIM de predict_proba del MISMO modelo cuyo raw alimentó ml_calibrator.fit"
  - "Test permanente test_comparison_guard_fails_on_distribution_mismatch_without_extra_fit que prueba (via pytest.raises) que el guard FALLA ante el probe x^3+renorm del verificador (mismatch sin fit extra) — WR-01 cerrado"
  - "Instrumentación output_to_model/verbatim_output_ids/cal_fit_producer/cal_transform_inputs ahora load-bearing, pareada por identidad de objeto-calibrador (no por índice de secuencia)"
affects: [verificacion-fase-05, gate-promocion, ML-03, ML-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Identidad train/serve por object-id anclada en la salida-verbatim-del-modelo-de-calibración: el array de scoring debe estar en verbatim_output_ids Y su productor == productor del array de fit del MISMO calibrador"
    - "Defensa contra reuse de id() de CPython: pinnear referencias fuertes a todo array rastreado por id durante la vida de la aserción (id estable solo mientras el objeto vive)"

key-files:
  created:
    - ".planning/phases/05-ml-ensemble-upgrade-gated/05-06-SUMMARY.md"
  modified:
    - "tests/test_ml_validation.py"

key-decisions:
  - "[Phase 05]: El guardrail CR-01 prueba identidad de modelo/distribución por holdout (array de scoring == salida verbatim de predict_proba del modelo de calibración-fit), no el proxy de conteo n_models==n_holdouts. El conteo se conserva como aserción COMPLEMENTARIA para seguir atrapando el patrón literal final_model."
  - "[Phase 05]: La corrección es estrictamente de TEST — src/cdd_mundial/models/ml_validation.py NO se tocó (final_model count == 0); la identidad se observa por monkeypatch de MulticlassCalibrator.fit/transform y MulticlassXGBoost.fit/predict_proba, sin costura de observabilidad en src/ (el monkeypatch puro bastó)."

patterns-established:
  - "Anti-WR-01: el guard ancla en el invariante verbatim-output-del-modelo-de-calibración (no en 'id ∈ output_to_model' a secas), de modo que un array DERIVADO (x^3+renorm) cuyo id no está en verbatim_output_ids dispara la falla aunque no se agregue ningún fit()."

requirements-completed: [ML-03, ML-04]

# Metrics
duration: ~25min
completed: 2026-06-17
---

# Phase 5 Plan 06: Fortalecer el guardrail de regresión CR-01 (WR-01) Summary

**El guardrail de regresión CR-01 ahora prueba la IDENTIDAD train/serve real por holdout — el array que el calibrador transforma al puntuar es una salida verbatim de predict_proba del mismo modelo cuyo raw lo calibró — y FALLA ante el probe de mismatch-sin-fit-extra del verificador, restaurando la red de seguridad metodológica de ML-03/ML-04 sin tocar la lógica del gate.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-17
- **Completed:** 2026-06-17
- **Tasks:** 2 (ambas TDD)
- **Files modified:** 1 (`tests/test_ml_validation.py`)

## Accomplishments

- **Task 1 (RED):** congeló como código ejecutable el probe exacto del verificador (`test_PROBE_distortion_without_extra_fit_must_fail`): distorsiona `ml_holdout_raw` con `out**3` + renormalización SOLO en el array de scoring del holdout, SIN agregar ningún `fit()`. Demostró por evidencia que el guard ANTERIOR (conteo `n_models == n_holdouts`) PASA bajo el mismatch — el bug WR-01.
- **Task 2 (GREEN):** reescribió la aserción load-bearing a IDENTIDAD por object-id. Per holdout, el array que `ml_calibrator.transform` recibe al puntuar (línea 439 de `ml_validation.py`) debe ser (a) una salida VERBATIM de `predict_proba` (`id ∈ verbatim_output_ids`) y (b) producida por el MISMO modelo cuyo raw (`ml_fit_raw`) alimentó `ml_calibrator.fit` para ESE holdout (`output_to_model[id(probs)] == cal_fit_producer[id(cal)]`). El conteo `n_models == n_holdouts` se conserva como aserción complementaria.
- **Probe convertido en aserción permanente:** se eliminó el andamiaje RED y se agregó `test_comparison_guard_fails_on_distribution_mismatch_without_extra_fit`, que usa `pytest.raises(AssertionError, match="CR-01 identity violation")` para probar que el guard fortalecido FALLA ante el probe x^3+renorm sin fit extra.
- **Triple invariante verificado:** (1) verde contra el código de producción correcto; (2) rojo contra el probe de mismatch-sin-fit-extra (vía la aserción de no-verbatim); (3) rojo contra el defecto literal `final_model` re-fit (vía la aserción de productor distinto — verificado inyectando transitoriamente el defecto en `src/` y revirtiéndolo).

## Task Commits

Cada tarea fue commiteada atómicamente (solo este plan: `tests/test_ml_validation.py`):

1. **Task 1: RED — congelar el probe WR-01** — `944b29c` (test).
2. **Task 2: GREEN — guard a identidad train/serve por holdout** — `0ee5256` (test).

**Plan metadata:** (este SUMMARY + STATE/ROADMAP) — ver commit `docs(05-06)` final.

## Files Created/Modified

- `tests/test_ml_validation.py` — nuevo helper `_instrument_identity` (instrumentación por object-id de `fit`/`predict_proba` + `MulticlassCalibrator.fit`/`transform`, con probe opcional de distorsión); nuevo helper `_assert_train_serve_identity` (aserción load-bearing de identidad + conteo complementario); `test_comparison_scores_holdout_with_the_same_model_calibrators_were_fit_on` reescrito para usar la aserción de identidad; nuevo `test_comparison_guard_fails_on_distribution_mismatch_without_extra_fit` (probe permanente vía `pytest.raises`). Andamiaje RED `test_PROBE_distortion_without_extra_fit_must_fail` eliminado.
- `src/cdd_mundial/models/ml_validation.py` — **NO modificado** (el monkeypatch puro bastó para observar la identidad; ninguna costura de observabilidad fue necesaria). `final_model` count == 0 confirmado.

## Decisions Made

- **Anclar en la salida-verbatim-del-modelo-de-calibración, no en "id ∈ output_to_model" a secas (execution_notes #1).** Si la instrumentación de distorsión registrara el id del array YA distorsionado, "id ∈ output_to_model" pasaría por la vía equivocada y el guard no mordería el probe. Se mantiene un conjunto separado `verbatim_output_ids` poblado solo con las salidas VERBATIM de `predict_proba`; el array distorsionado deliberadamente NO se registra, así que su id queda fuera del conjunto y la aserción falla — exactamente como debe.
- **Parear por OBJETO-calibrador, no por índice de secuencia (execution_notes #2).** `cal_fit_producer[id(cal)]` mapea cada calibrador a la identidad del modelo cuyo raw lo ajustó; al puntuar, se cruza el array de `transform` de ese MISMO calibrador contra su productor de fit. Un reordenamiento futuro del bucle no desalinea el emparejamiento.
- **No tocar `src/`.** El plan permitía una costura de observabilidad mínima solo si el monkeypatch puro no bastaba. Bastó: monkeypatch de `MulticlassCalibrator.transform` captura el array de scoring del holdout sin alterar comportamiento. Se preserva la garantía de cero cambio de producción (gate, winner, probs servidos idénticos).

## Deviations from Plan

None - plan executed exactly as written. No se aplicaron reglas de desviación (Rules 1-4) sobre el comportamiento de producción. No se tocaron pins de dependencias. WR-02 (asimetría baseline-vs-ML, ~75% filas) queda explícitamente fuera de alcance como decisión del Director, según `<out_of_scope>` del plan.

## Issues Encountered

- **Reuse de `id()` de CPython (resuelto).** El guard fortalecido pasaba en aislamiento pero fallaba en la suite completa: arrays de numpy devueltos por `predict_proba` que quedaban sin referencia eran recolectados y su `id` reciclado por arrays posteriores, corrompiendo `verbatim_output_ids`/`output_to_model`. Fix: pinnear referencias fuertes (`_retained`) a todo array rastreado por id y RETORNARLAS en el dict `captured`, de modo que los ids permanecen únicos durante la aserción (que corre DESPUÉS de que `_instrument_identity` retorna). Tras el fix: 50 passed en la suite completa de Fase 5. Sin impacto en código de producción.
- **Venv frágil en OneDrive (conocido).** Todas las suites se corrieron con `.\.venv\Scripts\python.exe` (el `.\.venv\python.exe` raíz es un stub deshidratado). Coincide con la memoria "venv-onedrive-fragile".

## Verification

Comandos del plan (ejecutados con `.\.venv\Scripts\python.exe`):

- Task 1: `pytest -q tests/test_ml_validation.py -k "PROBE_distortion or same_model" -x` -> **2 passed** (probe demuestra que el guard de conteo no muerde).
- Task 2 (identidad): `pytest -q tests/test_ml_validation.py -k "same_model or guard_fails" -x` -> **2 passed** (verde contra producción; rojo-vía-pytest.raises contra el probe).
- Task 2 verify 1: `pytest -q tests/test_ml_validation.py tests/test_ml_calibration.py -x` -> **29 passed**.
- Task 2 verify 2: `pytest -q tests/test_ml_validation.py tests/test_ml_features.py tests/test_ml_selection.py -k "ml or selection or comparison or same_model or guard_fails" -x` -> **42 passed**.
- Suite Phase 5 enfocada completa: `pytest -q tests/test_ml_validation.py tests/test_ml_calibration.py tests/test_ml_features.py tests/test_ml_selection.py` -> **50 passed**.
- Defecto literal `final_model` (inyección transitoria en `src/`, luego revertida): el guard fortalecido FALLA con `AssertionError: CR-01 identity violation: the holdout-scoring array was produced by a DIFFERENT model ... (re-fit final_model)` — RED correcto por IDENTIDAD, no solo por conteo. `src/` revertido (diff vacío, `final_model` count == 0).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **WR-01 cerrado.** El último gap de la Fase 5 (VERIFICATION status `gaps_found`, 3/4) está resuelto: el guardrail de regresión CR-01 prueba la identidad de modelo/distribución que su docstring afirma, y falla ante el probe de mismatch-sin-fit-extra que el verificador usó para confirmar WR-01.
- **Listo para re-verificación de la Fase 05.** El verificador debería reconfirmar el cuarto must_have (antes PARTIAL): "una regresión que recalibra con un productor y puntúa con otro falla por test automatizado antes de afectar el veredicto del gate".
- **Sin cambio de producción.** Gate, winner y probs servidos idénticos; `run_ml_comparison` intacto. La red de seguridad metodológica de ML-03/ML-04 está restaurada sin reabrir el resto de la fase.
- **Nota abierta (out-of-scope, decisión del Director):** WR-02 — el candidato ML compite en el gate con ~75% de las filas pre-cutoff (inner_fit) vs baseline 100%. Jesús debería registrarlo explícitamente (documentar la limitación en el reporte del gate o adoptar un patrón out-of-fold). NO bloquea la fase.

## Self-Check: PASSED

- Archivos verificados en disco: `05-06-SUMMARY.md`, `tests/test_ml_validation.py` — FOUND.
- Commits verificados en git: `944b29c` (Task 1), `0ee5256` (Task 2) — FOUND.
- `src/cdd_mundial/models/ml_validation.py` sin diff respecto a HEAD; `final_model` count == 0.

---
*Phase: 05-ml-ensemble-upgrade-gated*
*Completed: 2026-06-17*
