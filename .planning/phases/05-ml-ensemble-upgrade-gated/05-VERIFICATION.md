---
phase: 05-ml-ensemble-upgrade-gated
verified: 2026-06-17T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "WR-01: el guardrail de regresion CR-01 ahora prueba la IDENTIDAD de modelo/distribucion por holdout (no un conteo de fits). Confirmado empiricamente: el probe x^3+renorm SIN fit extra ahora HACE FALLAR el guard (AssertionError 'CR-01 identity violation'), y el guard permanece GREEN contra el codigo de produccion correcto."
  gaps_remaining: []
  regressions: []
deferred: []
human_verification: []
---

# Phase 5: ML + Ensemble (upgrade gated) Verification Report

**Phase Goal:** Un ensemble ML calibrado mejora medible y honestamente al baseline — o el resultado negativo queda documentado como hallazgo; el baseline sigue publicando en paralelo en todo momento.
**Verified:** 2026-06-17
**Status:** passed
**Re-verification:** Si — tras cierre de la brecha WR-01 (plan 05-06, commits 944b29c/0ee5256/b8e46a6 + fix de flake 29d3b90)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Matriz de features point-in-time sin leakage temporal (shift(1)) | ✓ VERIFIED | Inalterado por el cierre (05-06 es estrictamente de TEST: solo `tests/test_ml_validation.py`). `test_ml_features.py` verde dentro de las 50 pruebas de la suite Phase 5. Sin regresion. |
| 2 | Clasificador XGBoost 3 clases (depth<=3-4, ~<=10 features) con la misma validacion temporal que el baseline | ✓ VERIFIED | `MulticlassXGBoost` + `run_ml_validation`/`run_ml_comparison` sin cambios; reusa `HOLDOUTS`/`log_loss`/`brier`/`rps` del baseline. Suite verde. Sin regresion. |
| 3 | Gate pre-registrado: el ensemble solo reemplaza al baseline si lo vence en log-loss en los 4 holdouts; resultado negativo documentado; baseline sigue publicando | ✓ VERIFIED | Codigo de produccion correcto (CR-01 cerrado en 05-05: `scoring_model = inner_model`, `final_model` count==0). **La red de seguridad ahora es genuina:** el guard de regresion (`test_comparison_scores_holdout_with_the_same_model_calibrators_were_fit_on` via `_assert_train_serve_identity`) prueba identidad de objeto por holdout — `output_to_model[id(probs)] == cal_fit_producer[id(cal)]` Y `id(probs) ∈ verbatim_output_ids`. El sibling `test_comparison_guard_fails_on_distribution_mismatch_without_extra_fit` prueba via `pytest.raises` que el guard FALLA el probe x^3+renorm sin fit extra. `evaluate_ml_gate` puro/correcto; doble publicacion + fallback intactos (D-13/D-14). |
| 4 | Calibracion isotonica vs Platt comparada empiricamente en folds temporales y elegida por evidencia | ✓ VERIFIED | Mismo root cause CR-01 resuelto en produccion: `select_best_calibration` se evalua sobre la distribucion de `inner_model` y el calibrador elegido transforma las salidas del MISMO `inner_model` en el holdout. El guard fortalecido blinda que la evidencia describe la distribucion realmente puntuada. `calibration_max_date < cutoff` sigue probado (anti-leakage). |

**Score:** 4/4 truths verified

Nota: las cuatro filas son los cuatro Success Criteria del ROADMAP. El cuarto must_have que el plan de cierre (antes 05-05, reforzado por 05-06) agrego para blindar el fix — "una regresion que recalibra con un productor y puntua con otro falla por test automatizado antes de afectar el veredicto del gate" — era el unico gap remanente (PARTIAL → ahora VERIFIED). Refuerza #3 y #4; no reduce ni amplia el alcance del roadmap.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/cdd_mundial/models/ml_validation.py` | `run_ml_comparison` con identidad train/serve; gate intacto | ✓ VERIFIED | `scoring_model = inner_model` (l.433); `ml_holdout_raw = scoring_model.predict_proba(...)` (l.438) transformado por `ml_calibrator` ajustado sobre `ml_fit_raw` del mismo `inner_model` (l.406-408). `final_model` count == 0. NO modificado por 05-06 (correccion fue de solo-test). |
| `tests/test_ml_validation.py` | Regresion CR-01 que prueba identidad de productor raw fit==serve (no conteo) | ✓ VERIFIED | `_assert_train_serve_identity` (l.563-623): asercion load-bearing compara `output_to_model.get(probs_id) == producer` y `probs_id ∈ verbatim_output_ids`, pareada por objeto-calibrador. El conteo `n_models == len(HOLDOUTS)` queda como asercion COMPLEMENTARIA (l.619-623). Probe permanente `test_comparison_guard_fails_on_distribution_mismatch_without_extra_fit` (l.654-677) via `pytest.raises`. |
| `tests/test_ml_calibration.py` | Cobertura del flujo corregido | ✓ VERIFIED | Verde dentro de las 50 pruebas. Sin cambios en 05-06. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `ml_validation.py` (calibradores fit) | `ml_validation.py` (holdout scoring) | Mismo `inner_model` produce fit-raw y serve-raw | ✓ WIRED | `scoring_model = inner_model`; `ml_holdout = ml_calibrator.transform(scoring_model.predict_proba(x_holdout))`. |
| `tests/test_ml_validation.py` | `ml_calibration.py` | monkeypatch a `MulticlassCalibrator.fit/transform` captura `id(probs)` por llamada y cruza contra `cal_fit_producer` | ✓ WIRED | `tracking_cal_fit` (l.522-528) registra `cal_fit_producer[id(self)] = output_to_model.get(id(probs))`; `tracking_cal_transform` (l.530-534) registra `(id(self), id(probs))`. |
| `tests/test_ml_validation.py` | `ml_xgboost.py` | `predict_proba` tracking mapea `id(out) -> id(modelo)`; salida de scoring debe trazar al modelo de calibracion-fit | ✓ WIRED | `tracking_predict` (l.481-487) puebla `verbatim_output_ids`/`output_to_model`. El probe `distorting_predict` envuelve POR ENCIMA del tracker (l.507-520), de modo que el array distorsionado es DERIVADO y su id queda fuera de `verbatim_output_ids` — evitando la trampa de execution_notes #1. |
| `tests/test_ml_validation.py` | `ml_validation.py` | guardrail de identidad train/serve por holdout (no conteo) | ✓ WIRED | Asercion load-bearing es la comparacion de identidad por objeto-calibrador; verificada RED contra el probe y GREEN contra produccion. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Suite Phase 5 completa pasa | `.\.venv\Scripts\python.exe -m pytest -q tests/test_ml_validation.py tests/test_ml_calibration.py tests/test_ml_features.py tests/test_ml_selection.py -x` | 50 passed in 12.47s | ✓ PASS |
| Tests CR-01 nombrados pasan | `pytest -q -k "same_model or guard_fails" -v` | 2 passed | ✓ PASS |
| `final_model` ausente del codigo de produccion | Grep `final_model` en `ml_validation.py` | 0 coincidencias | ✓ PASS |
| Guard atrapa mismatch SIN fit extra (invariante real, WR-01) | Invocacion directa de `_instrument_identity(distort=True)` + `_assert_train_serve_identity` | RAISED 'CR-01 identity violation' con `models_per_run == 4` (sin fit extra) | ✓ PASS |
| Guard permanece GREEN contra produccion correcta | Invocacion directa de `_instrument_identity(distort=False)` + asercion | PASSED (no raise) | ✓ PASS |

El spot-check decisivo: el probe x^3+renorm que en la verificacion ANTERIOR pasaba el guard (1 passed = bug WR-01) ahora lo hace FALLAR por la rama de no-verbatim (`probs_id not in verbatim_output_ids`), con el conteo de fits intacto en 4. La identidad — no el conteo — es lo que muerde.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ML-01 | 05-01 | Pipeline de features point-in-time | ✓ SATISFIED | Criterio #1 VERIFIED; sin cambios en el cierre. |
| ML-02 | 05-02 | XGBoost 3-clases con validacion temporal del baseline | ✓ SATISFIED | Criterio #2 VERIFIED; sin cambios. |
| ML-03 | 05-02..05-06 | Ensemble + gate pre-registrado + dual publication | ✓ SATISFIED | Criterio #3 VERIFIED: gate consume insumos honestamente calibrados Y la red de seguridad de regresion ahora prueba la identidad train/serve genuinamente. |
| ML-04 | 05-03, 05-05, 05-06 | Calibracion isotonic vs Platt empirica en folds temporales | ✓ SATISFIED | Criterio #4 VERIFIED: evidencia y distribucion puntuada coinciden, blindado por el guard de identidad. |

Los cuatro IDs (ML-01..ML-04) estan mapeados a Phase 5 en REQUIREMENTS.md (lineas 35-38, 98-101) sin huerfanos (Coverage 29/29). El plan 05-06 declara `requirements: [ML-03, ML-04]` y `decision_ids: [D-11, D-12, D-13]` — todos rastreables.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `tests/test_ml_validation.py` | 461-467, 483-484, 526, 531-532 | Referencias fuertes (`_retained`) para pinnear ids contra reuse de CPython | ℹ️ Info | No es defecto — es la mitigacion documentada del flake full-suite-only (id-reuse). Tecnica correcta; commit 29d3b90 pinea OBJETOS modelo/calibrador, no solo arrays. |
| `src/cdd_mundial/models/ml_validation.py` | 433, 342-365 | Modelo servido entrenado con ~75% de filas pre-cutoff vs baseline 100% (WR-02) | ℹ️ Info (decision del Director) | Asimetria baseline-vs-ML metodologicamente defendible (prioriza identidad train/serve). Documentada en docstring y en 05-06-SUMMARY. Fuera de alcance per 05-06; NO bloquea 4/4. Ver nota abajo. |
| `src/cdd_mundial/models/ml_validation.py` | 382-385 | `_select_ml_holdout`/split posiblemente invocado dos veces por holdout (WR-03) | ℹ️ Info | Trabajo duplicado, no defecto de correctitud. |

Sin anti-patrones de severidad Blocker ni Warning. El WARNING de la verificacion anterior (guard como proxy de conteo) esta resuelto.

### Observacion metodologica para el Director (WR-02 — no bloquea)

El gate puntua el holdout con `inner_model` (entrenado sobre `inner_fit` ≈ 75% de las filas pre-cutoff) en lugar de re-ajustar sobre el 100%. Esto prioriza la identidad train/serve — sin la cual el gate seria deshonesto — pero el candidato ML/ensemble compite con ~25% menos datos (y el 25% mas reciente) contra un baseline Dixon-Coles que usa toda la historia. El gate podria rechazar un candidato ML que, con todas las filas pre-cutoff, si venceria al baseline. No es un bug: los must_haves literales se cumplen. Es una decision informada que el Director (Jesus) deberia registrar explicitamente (documentar la limitacion en el reporte del gate, o adoptar un patron out-of-fold que preserve ambas propiedades). Se reporta como hallazgo metodologico, no como gap ni como bloqueo de la fase.

### Human Verification Required

Ninguna verificacion humana es necesaria para la determinacion de este resultado. El cierre de WR-01 se confirma por evidencia empirica directa (probe de mismatch sin fit extra → guard RAISES 'CR-01 identity violation'; produccion correcta → guard GREEN) y por lectura del codigo de test/produccion. WR-02 es una recomendacion de registro para el Director, no un test humano que condicione el veredicto.

### Gaps Summary

Sin gaps. El plan de cierre 05-06 resolvio el unico gap remanente (WR-01): el guardrail de regresion CR-01 — que en la verificacion anterior era un proxy de conteo (`n_models == n_holdouts`) y pasaba ante un mismatch de distribucion sin fit extra — ahora prueba la **identidad de objeto** por holdout. La asercion load-bearing (`_assert_train_serve_identity`) cruza el array que `ml_calibrator.transform` recibe al puntuar contra (a) el conjunto de salidas verbatim de `predict_proba` y (b) el modelo cuyas salidas alimentaron `ml_calibrator.fit`, pareando por objeto-calibrador (no por indice de secuencia, evitando la fragilidad de execution_notes #2). El probe x^3+renorm del verificador ahora HACE FALLAR el guard — verificado por invocacion directa (RAISED 'CR-01 identity violation', `models_per_run == 4` sin fit extra) y por el test permanente via `pytest.raises`. El guard permanece GREEN contra el codigo de produccion correcto. El fix de flake (commit 29d3b90) pinea referencias fuertes a los OBJETOS modelo/calibrador para evitar el reuse de id de CPython, eliminando el falso positivo full-suite-only. La correccion fue estrictamente de test: `src/` sin diff, `final_model` count == 0, gate intacto. Los criterios #1-#2 nunca se tocaron; #3-#4 ya estaban honestamente satisfechos en produccion y ahora cuentan con la red de seguridad que su docstring promete. Suite Phase 5: 50 passed. Phase goal cumplido al 4/4.

---

_Verified: 2026-06-17_
_Verifier: Claude (gsd-verifier)_
