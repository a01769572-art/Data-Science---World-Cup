---
phase: 02-modelos-baseline
plan: 03
subsystem: models
tags: [dixon-coles, scipy, mle, l-bfgs-b, poisson, rho, contrato-d09, json]

# Dependency graph
requires:
  - phase: 02-modelos-baseline
    plan: 01
    provides: paquete cdd_mundial.models, columnas canonicas de load_matches (date datetime, home/away_team_id, scores, neutral)
  - phase: 01-fundacion-datos
    provides: UnknownTeamError (identities.py), patron JSON determinista de provenance.py, slugs canonicos de teams.csv
provides:
  - dixon_coles.py completo: tau_log, neg_log_lik + gradiente analitico, fit_dixon_coles (fit-at-cutoff con decaimiento exponencial), DixonColesModel
  - "Contrato D-09 CONGELADO: predict_lambdas(team_a, team_b, ctx) -> tuple[float, float], modulo-level y re-exportado en cdd_mundial.models"
  - score_matrix / wdl_from_lambdas: W/D/L derivadas de la matriz de marcadores con correccion rho (MODEL-03, D-10)
  - Serializacion JSON determinista (save/load/to_dict/from_dict) + load_production_model (dc_params_*.json mas reciente)
affects: [02-04 validacion, 03 simulador, 05 ml]

# Tech tracking
tech-stack:
  added: []
  patterns: [gradiente analitico acumulado con np.bincount, penalizacion suave de identifiabilidad en la NLL, JSON plano sort_keys para parametros de modelo (nunca pickle), contrato congelado protegido por test de firma inspect.signature]

key-files:
  created:
    - src/cdd_mundial/models/dixon_coles.py
    - tests/test_dixon_coles.py
  modified:
    - src/cdd_mundial/models/__init__.py

key-decisions:
  - "Identifiabilidad via penalizacion suave 1000*(sum(att)^2 + sum(dfn)^2) con gradiente 2000*sum — sumas del fit < 0.01 sin reparametrizar a n-1 libres (pitfall 7c)"
  - "Cache del modelo de produccion en predict_lambdas modulo-level por (path, mtime) — discrecion menor otorgada por el plan; invalida al materializar un dc_params nuevo"
  - "Cobertura de mitigaciones del threat model como tests: from_dict revalida rho (T-02-10) y load_production_model falla ruidosamente sin artefactos (2 tests extra sobre los 8 del behavior)"

requirements-completed: [MODEL-02, MODEL-03]

# Metrics
duration: 10min
completed: 2026-06-12
---

# Phase 2 Plan 03: Dixon-Coles + contrato predict_lambdas congelado Summary

**Dixon-Coles completo con NLL ponderada por decaimiento exponencial, correccion rho de marcadores bajos, gradiente analitico verificado contra approx_fprime (error relativo < 1e-5), fit L-BFGS-B que recupera parametros sinteticos conocidos en ~2s, y el contrato D-09 congelado con W/D/L derivadas de la matriz de marcadores (p_draw 0.268 en el caso de sanidad)**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-12T15:00:29Z
- **Completed:** 2026-06-12T15:10:43Z
- **Tasks:** 2 (ambas en TDD RED/GREEN)
- **Files modified:** 3

## Accomplishments

- Gradiente analitico de la NLL (incluida la penalizacion y los terminos tau por caso) coincide con el numerico de scipy con error relativo < 1e-5 — los fits corren en segundos, no minutos (pitfall 7a / D-14)
- Recuperacion sintetica seed 42 (8 equipos, 3000 partidos, Poisson independiente): |c_hat-0.2| < 0.1, |gamma_hat-0.3| < 0.1, max|att_hat-att_true| < 0.15, |rho_hat| < 0.05, sumas att/dfn < 0.01
- Fit-at-cutoff por construccion: corte estricto `date < cutoff`, pesos w = exp(-xi*dias) con truncamiento w < 1e-4 (documentado como equivalente numerico de D-07); rho acotado a [-0.2, 0.2] en L-BFGS-B (pitfall 8)
- **Contrato D-09 congelado y protegido**: firma exacta `(team_a, team_b, ctx)` verificada con inspect.signature (T-02-12); slugs desconocidos lanzan UnknownTeamError importada de identities (sin redefinir, sin TeamResolver); ctx incompleto lanza ValueError nombrando las claves faltantes
- Convencion documentada en docstring: cuando `ctx["neutral"]` es False, team_a ES el local/anfitrion y recibe gamma (Phase 3 la consume a ciegas; en 2026 solo MEX/USA/CAN)
- W/D/L desde la matriz de marcadores 11x11 con tau en las 4 celdas y renormalizacion: p_draw = 0.268 en [0.24, 0.28] para lambda=mu=1.25 (MODEL-03/D-10); celdas no negativas, suma 1
- Persistencia JSON determinista (sort_keys, nunca pickle — T-02-10) con round-trip bit a bit; load_production_model toma el dc_params_*.json lexicograficamente mayor y falla ruidosamente si no hay ninguno
- Suite completa: 148 tests verdes (133 previos + 15 nuevos), ruff limpio

## Task Commits

Each task was committed atomically:

1. **Task 1: NLL ponderada + gradiente analitico + fit L-BFGS-B** - `7488831` (test, RED) + `e33fe94` (feat, GREEN)
2. **Task 2: Contrato predict_lambdas congelado + W/D/L + serializacion** - `d1e87dc` (test, RED) + `8de20d4` (feat, GREEN)

## Files Created/Modified

- `src/cdd_mundial/models/dixon_coles.py` - tau_log/neg_log_lik/grad_neg_log_lik (verbatim RESEARCH + derivadas del plan), fit_dixon_coles, DixonColesModel (frozen, __post_init__ valida rho y longitudes), score_matrix, wdl_from_lambdas, load_production_model, predict_lambdas modulo-level con cache por mtime
- `tests/test_dixon_coles.py` - 15 tests: 5 de Task 1 (gradiente, recuperacion, cotas, pesos, identifiabilidad) + 8 del behavior de Task 2 + 2 de mitigacion (rho en from_dict, loader de produccion)
- `src/cdd_mundial/models/__init__.py` - re-export del contrato D-09 (`DixonColesModel`, `predict_lambdas`) conservando el docstring

## Decisions Made

- **Penalizacion suave de identifiabilidad** (especificada por el plan): 1000*(sum(att)^2 + sum(dfn)^2) en la NLL con su gradiente exacto — el test confirma |sum| < 0.01 tras el fit
- **Cache de produccion por (path, mtime)**: el plan dejaba a discrecion cache simple o sin cache; se eligio cache con invalidacion por mtime para que Phase 3 (simulador, miles de llamadas) no relea el JSON por llamada y el re-fit diario lo invalide solo
- **2 tests de mitigacion extra** sobre los 8 del behavior: el threat model exige que from_dict revalide invariantes (T-02-10) y que el loader falle claro sin artefactos — se verificaron explicitamente

## Deviations from Plan

None - plan executed exactly as written. (Los 2 tests adicionales sobre los 8 del behavior cubren mitigaciones que el propio threat model del plan marca como `mitigate`; no modifican alcance.)

## TDD Gate Compliance

Ambas tasks siguieron RED→GREEN: commits `test(...)` (7488831, d1e87dc) preceden a sus `feat(...)` (e33fe94, 8de20d4). Ambos RED fallaron por coleccion (modulo/simbolos inexistentes) antes de implementar. Sin fase REFACTOR (GREEN salio limpio bajo ruff en ambas tasks).

## Verification Results

- `pytest tests/test_dixon_coles.py -x -q` → 15 passed (2.9s — el fit sintetico de 3000 partidos converge en ~2s gracias al gradiente analitico)
- `python -c "from cdd_mundial.models import predict_lambdas, DixonColesModel"` → imprime `contract-ok`
- `pytest -q` (suite completa) → 148 passed
- Acceptance greps: 4 defs core + `(-0.2, 0.2)` + `1e-4` + `1000.0 *` presentes; import de UnknownTeamError sin redefinicion; firma exacta del contrato presente; `predict_lambdas` re-exportado en `__init__.py`

## Threat Model Compliance

- T-02-09 (spoofing inputs): UnknownTeamError en slugs fuera del fit con valores en !r; ValueError nombrando claves de ctx faltantes ✓
- T-02-10 (tampering deserializacion): JSON plano (nunca pickle); from_dict reconstruye via constructor → __post_init__ revalida; test explicito con rho=0.5 ✓
- T-02-11 (rho fuera de rango): bounds L-BFGS-B + __post_init__ + test de matriz no negativa que suma 1 ✓
- T-02-12 (cambio accidental de firma): test inspect.signature rompe la suite si alguien toca el contrato sin versionar ✓

## Issues Encountered

None.

## Known Stubs

None — toda la matematica opera sobre parametros reales. Nota de diseño (no stub): `predict_lambdas` modulo-level y `load_production_model` lanzan FileNotFoundError con mensaje claro hasta que el plan 02-04 materialice el primer `dc_params_*.json` de produccion — comportamiento especificado por el plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- El contrato D-09 queda congelado y protegido por test de firma — Phase 3 (simulador) puede construirse contra `from cdd_mundial.models import predict_lambdas`
- 02-04 (validacion temporal, gate D-13) tiene todo lo que necesita: `fit_dixon_coles(matches, cutoff, xi)` para los 4 fits holdout + produccion, `wdl_from_lambdas` para las probabilidades, y `DixonColesModel.save` para materializar `dc_params_{fecha}.json` con provenance
- El mini-grid de xi (Open Question 2: 0.00095 vs 0.0018) es trabajo de 02-04 — el fit recibe xi como parametro libre

---
*Phase: 02-modelos-baseline*
*Completed: 2026-06-12*

## Self-Check: PASSED

Los 3 archivos de codigo/tests y el SUMMARY existen en disco; los 4 commits de tareas (7488831, e33fe94, d1e87dc, 8de20d4) estan en el historial.
