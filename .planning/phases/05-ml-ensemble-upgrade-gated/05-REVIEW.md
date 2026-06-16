---
phase: 05-ml-ensemble-upgrade-gated
reviewed: 2026-06-16T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/cdd_mundial/models/ml_validation.py
  - tests/test_ml_validation.py
  - tests/test_ml_calibration.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Fase 5: Reporte de Revisión de Código

**Revisado:** 2026-06-16
**Profundidad:** standard
**Archivos revisados:** 3
**Estado:** issues_found

## Resumen

Se revisó adversarialmente el fix de cierre de brecha del plan 05-05, que corrige el
blocker CR-01 (desajuste tren/servicio en `run_ml_comparison`): los calibradores y el
peso del ensemble se ajustaban sobre las probabilidades de `inner_model` pero el holdout
se puntuaba con un `final_model` re-ajustado por separado.

**Veredicto sobre la corrección del fix (foco 1): el arreglo es correcto y completo en
cuanto a la identidad tren/servicio.** El step 4 ahora asigna `scoring_model = inner_model`
y elimina por completo el `final_model` re-ajustado. Tracé las cuatro dependencias de
distribución y todas son consistentes:

- `ml_calibrator` se ajusta sobre `ml_fit_raw` (de `inner_model`) y se aplica a
  `ml_holdout_raw` (de `scoring_model = inner_model`). ✓
- `weight` se selecciona sobre `ml_cal_calibrated`/`baseline_cal` y se aplica al mismo
  par de distribuciones en el holdout. ✓
- `ens_calibrator` se ajusta sobre `ens_fit_raw` (derivado de `inner_model`) y se aplica
  al ensemble de probabilidades del holdout derivadas de `inner_model`. ✓

No queda ningún camino donde la distribución de ajuste-de-calibración y la de
puntuación-de-holdout diverjan. **No se encontró ningún BLOCKER** ni regresión de
validez estadística (fuga temporal, contaminación, recalibración inválida) introducida
por el cambio. La disciplina pre-cutoff (`_split_inner`, `calibration_max_date`) se
mantiene intacta.

Sin embargo, el fix introduce una **decisión metodológica con coste no documentado** y
el test de regresión, aunque pasa, **no prueba el invariante exacto que su docstring
afirma probar** — ambos son WARNING en un proyecto que se define por su rigor
metodológico. A continuación el detalle.

## Warnings

### WR-01: El test de regresión CR-01 no prueba identidad de modelo entre fit-de-calibración y scoring-de-holdout; solo cuenta el número de fits

**File:** `tests/test_ml_validation.py:493-510`
**Issue:** El docstring del test afirma (líneas 442-445) que "asserts that for every
holdout the array consumed by the calibration-fit path and the array fed into the
holdout-scoring transform came from the *same* model instance". Pero la aserción real
NO comprueba eso. El test instrumenta `output_to_model` (id de array → id de modelo) y
`fit_inputs` (ids de arrays sobre los que se ajustó un calibrador), pero el único uso
real es:

```python
fit_models = {output_to_model[a] for a in fit_inputs if a in output_to_model}
assert fit_models, "no calibration-fit raw array traced to a model output"   # solo "no vacío"
...
assert n_models == n_holdouts   # el invariante de verdad probado
```

El invariante efectivo es **"se ajusta exactamente un modelo por holdout"** (conteo de
`fit`), no "el modelo que puntúa el holdout es el mismo que alimentó la calibración".
El elaborado rastreo `output_to_model`/`fit_inputs` se construye y luego se descarta:
`fit_models` solo se asevera como no-vacío, nunca se compara contra el id del modelo que
produjo `ml_holdout_raw`. La prueba de scoring-de-holdout jamás se captura ni se
contrasta.

Esto importa porque el conteo `n_models == n_holdouts` es un proxy frágil: una futura
refactorización que, por ejemplo, re-ajustara el modelo final PERO reutilizara la misma
instancia, o que entrenara un segundo modelo dentro de `select_best_calibration`, podría
violar la identidad tren/servicio sin cambiar el conteo, o cambiar el conteo sin violar
la identidad. El test es un proxy del invariante que su nombre y docstring prometen, no
una prueba directa de él. (Además, el comentario de las líneas 472-473 menciona "wrap
_ensemble_probs to capture the ml array used for holdout scoring", pero ese wrapper
nunca se implementa — confirma que el rastreo de scoring quedó a medias.)

**Fix:** Capturar el id del modelo que produce el array de scoring del holdout
(`ml_holdout_raw`) y aseverar que coincide con el id del modelo cuyas salidas
alimentaron `ml_calibrator.fit` para el mismo holdout. Idealmente instrumentar
por-holdout (no agregado sobre los cuatro) para que el invariante se verifique holdout a
holdout. Como mínimo, sustituir el `assert fit_models` no-vacío por una comparación
real entre el modelo de scoring y el modelo de calibración. El conteo `n_models ==
n_holdouts` puede quedarse como aserción complementaria, no como la única.

### WR-02: El fix cambia el modelo servido a uno entrenado con ~75% de los datos pre-cutoff sin documentar ni mitigar la pérdida de potencia estadística y la asimetría del gate

**File:** `src/cdd_mundial/models/ml_validation.py:433`, `342-365`
**Issue:** El fix corrige el desajuste tren/servicio descartando el `final_model`
(ajustado sobre TODAS las filas pre-cutoff) y sirviendo `inner_model` (ajustado solo
sobre `inner_fit`, es decir `1 - _INNER_CAL_FRACTION` ≈ 75% de las filas pre-cutoff;
ver `_split_inner`, línea 320). Esto es metodológicamente defendible (prioriza la
identidad tren/servicio sobre el uso máximo de datos), pero tiene un coste real que el
código y la documentación no reconocen:

1. **Pérdida de ~25% de los datos de entrenamiento** para el modelo que efectivamente
   produce los inputs del gate de promoción. En un proyecto con ~5k partidos
   internacionales relevantes (ver CLAUDE.md), descartar el 25% más reciente de cada
   ventana pre-cutoff puede degradar materialmente el candidato ML — y precisamente la
   porción descartada (`inner_cal`, la más reciente por fecha) es la más informativa
   para predecir el holdout inmediatamente posterior.
2. **Sesgo sistemático contra el candidato ML y el ensemble en el gate.** El baseline
   Dixon-Coles (columnas `_DC_PROB_COLUMNS`) son probabilidades point-in-time que NO
   sufren este recorte del 25%; reflejan toda la historia disponible. El gate
   (`evaluate_ml_gate`) exige que ML/ensemble batan al baseline en log-loss en los
   cuatro holdouts — pero ahora compite un ML entrenado con ~75% de datos contra un
   baseline con 100%. El gate podría rechazar un candidato ML que, entrenado con todos
   los datos pre-cutoff, sí superaría al baseline. Es un sesgo de validez metodológica en
   el corazón mismo de la decisión de promoción del proyecto.

El docstring (líneas 357-359) justifica la elección ("We therefore score the holdout
with the inner model rather than re-fitting on all pre-cutoff rows") pero no menciona
que esto reduce los datos de entrenamiento del modelo servido ni que introduce la
asimetría baseline-vs-ML en el gate. El campo de auditoría `n_inner_fit`/`n_inner_cal`
(líneas 469-470) expone el conteo pero no la implicación.

**Fix:** Es una decisión del Director (Jesús), no un bug puro — pero debe ser una
decisión informada y documentada, no un efecto colateral silencioso del fix de CR-01.
Opciones:
- Documentar explícitamente en el docstring y en el reporte del gate que el modelo ML
  servido usa `_INNER_CAL_FRACTION` menos datos que el baseline, y registrar esto como
  limitación conocida del veredicto.
- Considerar el patrón que preserva AMBAS propiedades: re-ajustar el modelo final sobre
  todas las filas pre-cutoff Y ajustar los calibradores/peso sobre predicciones
  out-of-fold de ese mismo modelo final (CV temporal interna), de modo que tren==servicio
  sin sacrificar el 25% de datos. Más trabajo, pero elimina el sesgo.
- Como mínimo, elevar el trade-off al Director de forma explícita.

### WR-03: `_select_ml_holdout(frame, holdout)` se invoca dos veces por holdout, duplicando filtrado y sort sobre el frame completo

**File:** `src/cdd_mundial/models/ml_validation.py:382-385`
**Issue:** Dentro del bucle de holdouts:

```python
holdout_eligible = _eligible(_select_ml_holdout(frame, holdout))
n_holdout_excluded = int(
    len(_select_ml_holdout(frame, holdout)) - len(holdout_eligible)
)
```

`_select_ml_holdout` filtra el frame completo por torneo+año y hace `sort_values` +
`reset_index` (líneas 89-93). Se ejecuta dos veces sobre el mismo `frame` y `holdout`
solo para obtener un escalar (`len`). No es un bug de correctitud — ambas llamadas
devuelven el mismo resultado — pero es trabajo duplicado y una pequeña trampa de
mantenibilidad: si la selección llegara a depender de estado mutable o de un índice no
determinista, las dos rutas podrían divergir silenciosamente. (La versión
`run_ml_validation`, líneas 162-164, ya lo hace correctamente con una sola llamada, de
modo que las dos funciones hermanas son inconsistentes entre sí.)

**Fix:** Calcular una sola vez, igual que el harness hermano:

```python
holdout_all = _select_ml_holdout(frame, holdout)
holdout_eligible = _eligible(holdout_all)
n_holdout_excluded = int(len(holdout_all) - len(holdout_eligible))
```

## Info

### IN-01: Rama if/else idéntica en `MulticlassCalibrator.transform`

**File:** `src/cdd_mundial/models/ml_calibration.py:150-153`
**Issue:** Las dos ramas del condicional ejecutan código idéntico:

```python
if self.method == "isotonic":
    calibrated[:, cls] = calibrator.predict(column)
else:
    calibrated[:, cls] = calibrator.predict(column)
```

Tanto `IsotonicRegression` como `_SigmoidCalibration` exponen `.predict(column)`, así
que la rama es código muerto que sugiere una diferencia que no existe. (Fuera del diff
de 05-05, pero en un archivo central del flujo CR-01.)
**Fix:** Colapsar a una sola línea: `calibrated[:, cls] = calibrator.predict(column)`.

### IN-02: `fit_selected_calibrator` parece no usarse en el flujo de producción

**File:** `src/cdd_mundial/models/ml_calibration.py:197-203`
**Issue:** `run_ml_comparison` construye calibradores directamente vía
`MulticlassCalibrator(method=...).fit(...)` (líneas 408, 421), no a través de
`fit_selected_calibrator`. La función parece un helper huérfano.
**Fix:** Confirmar uso con búsqueda en el repo; eliminarla si no tiene consumidores para
reducir superficie de mantenimiento.

### IN-03: El test de regresión usa umbral de tolerancia mágico `0.02` sin justificación derivada

**File:** `tests/test_ml_calibration.py:201`
**Issue:** `assert served_ll <= raw_ll + 0.02` usa un margen de 0.02 nats descrito como
"sampling noise" pero sin derivación (tamaño de muestra, varianza esperada). Con
`serve` de ~450 filas y semilla fija el test es determinista, pero el umbral es un
número mágico: si el comportamiento del calibrador cambia ligeramente, no queda claro si
0.02 sigue siendo el margen correcto o si enmascara una regresión real. Riesgo bajo
(test determinista por semilla), pero documentar el origen del 0.02 mejoraría la
auditabilidad que el proyecto exige.
**Fix:** Comentar cómo se eligió 0.02 (p. ej. derivado empíricamente de la varianza de
log-loss bajo la semilla fija) o reemplazar por una tolerancia derivada del tamaño de
muestra.

---

_Revisado: 2026-06-16_
_Revisor: Claude (gsd-code-reviewer)_
_Profundidad: standard_
