---
phase: 05-ml-ensemble-upgrade-gated
verified: 2026-06-16T00:00:00Z
status: gaps_found
score: 3/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/4
  gaps_closed:
    - "Gate pre-registrado alimentado con log-losses de holdout calibrados sobre la distribucion realmente puntuada (criterio #3): identidad train/serve restaurada en run_ml_comparison (scoring_model = inner_model, final_model eliminado)."
    - "Comparacion empirica isotonic-vs-Platt descrita sobre la distribucion que luego se transforma (criterio #4): mismo root cause CR-01 resuelto en el codigo de produccion."
  gaps_remaining:
    - "El guardrail de regresion CR-01 no prueba el invariante de identidad de modelo/distribucion que su docstring afirma; solo cuenta fits por holdout (proxy fragil) — WR-01 confirmado empiricamente."
  regressions: []
gaps:
  - truth: "Una regresion que vuelva a calibrar con un productor de probabilidades y puntuar con otro falla por test automatizado antes de afectar el veredicto del gate."
    status: partial
    reason: >
      El test de regresion CR-01
      (test_comparison_scores_holdout_with_the_same_model_calibrators_were_fit_on)
      construye instrumentacion de identidad (output_to_model, fit_inputs) pero la
      DESCARTA: su unica asercion derivada de ella es `assert fit_models` (no-vacio).
      El invariante efectivamente probado es el conteo `n_models == n_holdouts`
      (exactamente un fit por holdout), un PROXY de la identidad train/serve, no la
      identidad misma. Verificado empiricamente: re-introduje un mismatch
      train/serve que NO agrega una llamada fit() — distorsiono ml_holdout_raw
      (elevado al cubo y renormalizado) de modo que la distribucion transformada por
      los calibradores difiere de aquella sobre la que fueron ajustados — y el test
      PASA (1 passed). El guard solo atrapa re-introducciones que agregan un fit()
      (el patron literal final_model, que si dispara 8 != 4), no la clase general de
      defecto que su docstring promete cubrir ("the array fed into the holdout-scoring
      transform came from the *same* model instance"). El comentario lineas 472-473
      menciona un wrapper de _ensemble_probs "to capture the ml array used for holdout
      scoring" que nunca se implementa, confirmando que el rastreo de scoring quedo a
      medias.
    artifacts:
      - path: "tests/test_ml_validation.py"
        issue: >
          Lineas 493-510: fit_models solo se asevera no-vacio; jamas se compara
          contra el id del modelo que produjo ml_holdout_raw. La asercion load-bearing
          (n_models == n_holdouts) es un conteo de fits, no una prueba de identidad
          modelo-de-calibracion == modelo-de-scoring por holdout.
    missing:
      - "Capturar el id del modelo que produce ml_holdout_raw (el array de scoring del holdout) por cada holdout y aseverar que coincide con el id del modelo cuyas salidas alimentaron ml_calibrator.fit / ens_calibrator.fit para ESE holdout."
      - "Instrumentar por-holdout (no agregado sobre los cuatro) para que el invariante se verifique holdout a holdout, atrapando un mismatch de distribucion aunque el conteo de fits no cambie."
      - "Sustituir `assert fit_models` (no-vacio) por la comparacion real scoring-model-id == calibration-fit-model-id; el conteo n_models == n_holdouts puede quedar como asercion complementaria, no como la unica."
deferred: []
---

# Phase 5: ML + Ensemble (upgrade gated) Verification Report

**Phase Goal:** Un ensemble ML calibrado mejora medible y honestamente al baseline — o el resultado negativo queda documentado como hallazgo; el baseline sigue publicando en paralelo en todo momento.
**Verified:** 2026-06-16
**Status:** gaps_found
**Re-verification:** Si — tras cierre de brecha CR-01 (plan 05-05, commits 3f1e504/7ff5724)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Matriz de features point-in-time sin leakage temporal (shift(1)); FIFA-ranking point-in-time documentado | ✓ VERIFIED | Inalterado por el cierre de brecha (cambio estrictamente local a `run_ml_comparison`). `ml_features.py` y su suite intactos; `test_ml_features.py` verde dentro de las 49 pruebas. Sin regresion. |
| 2 | Clasificador XGBoost 3 clases (depth<=3-4, ~<=10 features) con la misma validacion temporal que el baseline | ✓ VERIFIED | `MulticlassXGBoost` + `run_ml_validation` sin cambios; reusa `HOLDOUTS`/`log_loss`/`brier`/`rps` del baseline. `test_ml_validation.py` (harness ML) verde. Sin regresion. |
| 3 | Gate pre-registrado: el ensemble solo reemplaza al baseline si lo vence en log-loss en los 4 holdouts; resultado negativo documentado; baseline sigue publicando | ✓ VERIFIED | **CR-01 cerrado en el codigo de produccion.** `run_ml_comparison` paso 4 (lineas 425-444) ahora asigna `scoring_model = inner_model`; el re-fit de `final_model` fue eliminado por completo (grep `final_model` en `src/` → 0 coincidencias). Tracé las cuatro dependencias de distribucion: `ml_calibrator` se ajusta sobre `ml_fit_raw` (de `inner_model`) y transforma `ml_holdout_raw` (de `inner_model`); `weight` y `ens_calibrator` operan sobre la misma distribucion. El gate (`evaluate_ml_gate`, puro y correcto) consume ahora insumos honestamente calibrados. Doble publicacion + fallback explicito al baseline intactos (D-13/D-14). |
| 4 | Calibracion isotonica vs Platt comparada empiricamente en folds temporales y elegida por evidencia | ✓ VERIFIED | Mismo root cause CR-01 resuelto: `select_best_calibration` se evalua sobre la distribucion de `inner_model` y el calibrador elegido se aplica a las salidas del MISMO `inner_model` en el holdout. La evidencia describe ahora la distribucion realmente puntuada. `calibration_max_date < cutoff` sigue probado (anti-leakage estructural intacto). |

**Score:** 3/4 truths verified

Nota: los criterios #1-#4 anteriores son los cuatro Success Criteria del ROADMAP. La cuarta fila de gaps NO es un quinto criterio del roadmap sino el tercer must_have del plan de cierre 05-05 ("una regresion … falla por test automatizado"), que el plan agrego para blindar el fix. Es un must_have plan-specific que no reduce el alcance del roadmap; se evalua por su redaccion literal y resulta PARTIAL.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/cdd_mundial/models/ml_validation.py` | `run_ml_comparison` con identidad train/serve | ✓ VERIFIED | `scoring_model = inner_model` (l.433); `final_model` ausente; campos de auditoria `scoring_model`/`n_inner_fit`/`n_inner_cal` (l.468-470). Sin diff respecto al commit (restaurado tras experimentos). |
| `tests/test_ml_validation.py` | Regresion CR-01 que demuestra identidad de productor raw fit==serve | ⚠️ STUB-de-invariante | El test existe, corre y atrapa el defecto LITERAL (final_model → 8 != 4), pero NO prueba el invariante de identidad de su docstring; pasa ante un mismatch de distribucion sin fit extra (WR-01, verificado empiricamente). |
| `tests/test_ml_calibration.py` | Cobertura del flujo corregido (contrato de distribucion valida) | ✓ VERIFIED | Dos pruebas nuevas (mass-preservation + la eleccion describe la distribucion aplicada). Verdes. Margen magico 0.02 (IN-03) es cosmetico. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `ml_validation.py` (calibradores fit) | `ml_validation.py` (holdout scoring) | Mismo `inner_model` produce fit-raw y serve-raw | ✓ WIRED | `scoring_model = inner_model`; `ml_holdout_raw = scoring_model.predict_proba(...)` transformado por `ml_calibrator` ajustado sobre `ml_fit_raw` del mismo `inner_model`. |
| `ml_validation.py` | `ml_calibration.py` | calibrador elegido se ajusta y transforma probs del mismo productor | ✓ WIRED | `select_best_calibration` + `MulticlassCalibrator.fit/transform` sobre arrays de `inner_model`. |
| `ml_validation.py` | `ml_xgboost.py` | un solo modelo produce fit-raw y holdout-raw | ✓ WIRED | Un `MulticlassXGBoost` por holdout; sin segundo modelo. |
| `tests/test_ml_validation.py` | `ml_validation.py` | guardrail de identidad train/serve para CR-01 | ⚠️ PARTIAL | El test se conecta y corre, pero el assert load-bearing es un conteo de fits, no la comparacion de identidad scoring==calibration por holdout. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Suite Phase 5 completa pasa | `pytest tests/test_ml_validation.py test_ml_calibration.py test_ml_features.py test_ml_selection.py` | 49 passed in 10.24s | ✓ PASS |
| Live selection/pipeline ML no regresiona | `pytest tests/test_ml_selection.py tests/test_live_pipeline.py -k "ml or selection"` | 10 passed | ✓ PASS |
| `final_model` eliminado del codigo de produccion | grep `final_model` en `src/` | 0 coincidencias | ✓ PASS |
| Guard CR-01 atrapa el defecto LITERAL (final_model re-fit) | inyectar re-fit final_model + `pytest -k same_model` | 1 failed (8 != 4) — RED correcto | ✓ PASS |
| Guard CR-01 atrapa mismatch SIN fit extra (invariante real) | distorsionar `ml_holdout_raw` (x^3, renorm) + `pytest -k same_model` | **1 passed — el guard NO dispara** | ✗ FAIL (WR-01 confirmado) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ML-01 | 05-01 | Pipeline de features point-in-time | ✓ SATISFIED | Criterio #1 VERIFIED; sin cambios en el cierre. |
| ML-02 | 05-02 | XGBoost 3-clases con validacion temporal del baseline | ✓ SATISFIED | Criterio #2 VERIFIED; sin cambios. |
| ML-03 | 05-02, 05-03, 05-04, 05-05 | Ensemble + gate pre-registrado + dual publication | ✓ SATISFIED | Criterio #3 VERIFIED: gate consume insumos honestamente calibrados tras cerrar CR-01. La cobertura de regresion del invariante queda parcial (gap separado), pero el deliverable ML-03 en si es metodologicamente valido. |
| ML-04 | 05-03, 05-05 | Calibracion isotonic vs Platt empirica en folds temporales | ✓ SATISFIED | Criterio #4 VERIFIED: evidencia y distribucion puntuada coinciden. |

Los cuatro IDs (ML-01..ML-04) estan contabilizados a traves de los planes 05-01..05-05; REQUIREMENTS.md los mapea a Phase 5 sin huerfanos (Coverage 29/29). El plan de cierre 05-05 declara `requirements: [ML-03, ML-04]` y `decision_ids: [D-11, D-12, D-13]` — todos rastreables.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `tests/test_ml_validation.py` | 493-510 | Guard de regresion prueba un proxy de conteo, no el invariante de identidad documentado (WR-01) | ⚠️ Warning | El blindaje de CR-01 es mas debil de lo que su docstring afirma; un futuro mismatch de distribucion sin fit extra pasaria silencioso. No corrompe el codigo actual (que esta correcto), pero deja el gate sin red de seguridad real. |
| `tests/test_ml_validation.py` | 471-485 | Instrumentacion output_to_model/fit_inputs construida y descartada; wrapper de _ensemble_probs prometido en comentario nunca implementado | ℹ️ Info | Codigo de test muerto que sugiere una verificacion que no ocurre; engaña al mantenedor. |
| `src/cdd_mundial/models/ml_validation.py` | 382-385 | `_select_ml_holdout` invocado dos veces por holdout (WR-03 del review) | ℹ️ Info | Trabajo duplicado, no defecto de correctitud; el hermano `run_ml_validation` ya lo hace en una sola llamada. |
| `src/cdd_mundial/models/ml_validation.py` | 433, 342-365 | Modelo servido entrenado con ~75% de filas pre-cutoff vs baseline 100% (WR-02 del review) | ℹ️ Info (decision del Director) | Observacion metodologica: el fix prioriza identidad train/serve sobre uso maximo de datos, introduciendo asimetria baseline-vs-ML en el gate. Documentado en docstring l.357-359 pero no como limitacion del veredicto. Ver nota abajo. |
| `src/cdd_mundial/models/ml_calibration.py` | 150-153 | Rama if/else isotonic/sigmoid identica (IN-01) | ℹ️ Info | Codigo muerto cosmetico. |
| `src/cdd_mundial/models/ml_calibration.py` | 37 | sklearn privado `_SigmoidCalibration` | ℹ️ Info | Fragilidad ante upgrade de patch sklearn; sin smoke test que lo fije. |

### Observacion metodologica para el Director (WR-02)

El fix cierra CR-01 puntuando el holdout con `inner_model` (entrenado sobre `inner_fit` ≈ 75% de las filas pre-cutoff) en lugar de re-ajustar sobre el 100%. Esto es metodologicamente defendible — prioriza la identidad train/serve, sin la cual el gate seria deshonesto — pero tiene un coste real no mitigado: el candidato ML/ensemble compite en el gate con ~25% menos datos (y precisamente el 25% mas reciente, el mas informativo para el holdout inmediato) contra un baseline Dixon-Coles point-in-time que usa toda la historia. El gate podria rechazar un candidato ML que, entrenado con todas las filas pre-cutoff, si venceria al baseline. No es un bug — los must_haves literales (identidad train/serve, comparacion honesta de distribuciones) se cumplen — pero el "honestamente" del goal de fase tiene esta asimetria como matiz. Esto NO bloquea la fase; es una decision informada que el Director (Jesus) deberia registrar explicitamente (documentar la limitacion en el reporte del gate, o adoptar el patron out-of-fold que preserva ambas propiedades). Se reporta como hallazgo metodologico, no como gap.

### Human Verification Required

Ninguna verificacion humana es necesaria para la determinacion de este gap. El defecto del guardrail (WR-01) es observable y decisivo por evidencia empirica directa (probe de mismatch sin fit extra → test pasa). El resto del fix se confirma por lectura de codigo + suites verdes.

### Gaps Summary

El cierre de brecha 05-05 logró su objetivo principal: **CR-01 esta genuinamente resuelto en el codigo de produccion.** `run_ml_comparison` ya no mezcla distribuciones — el `final_model` re-ajustado fue eliminado (0 coincidencias en `src/`), `scoring_model = inner_model`, y las cuatro dependencias de calibracion/peso/scoring trazan a un unico productor por holdout. Los criterios #3 (gate pre-registrado) y #4 (isotonic-vs-Platt empirico) — antes FAILED/PARTIAL por CR-01 — estan ahora honestamente satisfechos: el gate decide sobre insumos calibrados para la distribucion realmente puntuada, y la evidencia de seleccion describe esa misma distribucion. Los criterios #1 y #2 no se tocaron y siguen VERIFIED (49 pruebas verdes, sin regresion). El baseline sigue publicando en paralelo (doble publicacion + fallback intactos).

Queda UN gap, exactamente el que el code review anticipó (WR-01): **el tercer must_have del plan 05-05 — "una regresion que vuelva a calibrar con un productor de probabilidades y puntuar con otro falla por test automatizado antes de afectar el veredicto del gate" — NO se cumple genuinamente.** Lo verifiqué empiricamente: el guard solo atrapa re-introducciones que agregan una llamada `fit()` (el patron literal `final_model`, que dispara 8 != 4). Cuando re-introduje un mismatch train/serve que NO agrega un fit — distorsionando `ml_holdout_raw` para que la distribucion transformada por los calibradores difiera de aquella sobre la que se ajustaron — el test PASA. La elaborada instrumentacion `output_to_model`/`fit_inputs` se construye y se descarta (`fit_models` solo se asevera no-vacio); la asercion load-bearing `n_models == n_holdouts` es un proxy de conteo, no la prueba de identidad que el docstring promete. El comentario que anuncia un wrapper de `_ensemble_probs` "to capture the ml array used for holdout scoring" describe codigo que nunca se escribio.

Importa porque el goal de la fase es metodologico ("mejora … HONESTAMENTE"): el codigo actual es correcto, pero la red de seguridad que debia impedir la silenciosa reaparicion del defecto que invalidó la verificacion anterior no protege la clase general del defecto. Es un WARNING, no un BLOCKER del deliverable: ML-03/ML-04 son honestamente validos hoy. La correccion es mecanica (capturar el id del modelo que produce `ml_holdout_raw` por holdout y compararlo con el id del modelo cuyas salidas alimentaron la calibracion para ese holdout) y esta acotada a `tests/test_ml_validation.py`.

---

_Verified: 2026-06-16_
_Verifier: Claude (gsd-verifier)_
