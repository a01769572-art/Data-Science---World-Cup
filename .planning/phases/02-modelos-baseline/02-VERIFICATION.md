---
phase: 02-modelos-baseline
verified: 2026-06-12T16:02:05Z
status: passed
score: 17/17 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 16/17
  gaps_closed:
    - "The Phase 02 MODEL-01 contract now explicitly requires fixed canonical WFE parameters plus external rank-correlation validation, matching the implemented Elo recomputation."
  gaps_remaining: []
  regressions: []
---

# Phase 2: Modelos Baseline Verification Report

**Phase Goal:** El sistema produce goles esperados (λ) y probabilidades W/D/L de partido desde modelos estructurales custom, validados temporalmente.
**Verified:** 2026-06-12T16:02:05Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | El Elo dinámico custom (K canónico WFE por torneo, ventaja local condicional a sede neutral y multiplicador por margen) está recomputado desde el histórico y validado por correlación de rangos contra un snapshot externo | ✓ VERIFIED | [ROADMAP.md](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/.planning/ROADMAP.md:46) now matches the fixed-WFE implementation, [REQUIREMENTS.md](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/.planning/REQUIREMENTS.md:20) explicitly defers K optimization, [elo.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/elo.py:87) recomputes from history with canonical WFE components, and the external validation still holds with Spearman `0.9786956879333604` over 48 World Cup teams. |
| 2 | El venv importa `scipy`, `sklearn`, `matplotlib`, `seaborn` y `joblib` sin error | ✓ VERIFIED | `pyproject.toml` pins the five dependencies at [pyproject.toml](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/pyproject.toml:18), and direct import/version check succeeded: `scipy 1.17.1`, `sklearn 1.9.0`, `matplotlib 3.11.0`, `seaborn 0.13.2`, `joblib 1.5.3`. |
| 3 | Los 200 strings reales de torneo mapean a un K-factor o fallan ruidosamente | ✓ VERIFIED | [tournament_k_factors.csv](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/data/external/tournament_k_factors.csv:1) has 200 reviewed rows; [tournaments.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/tournaments.py:58) raises `UnknownTournamentError`; focused tests passed including the real-history coverage gate. |
| 4 | `load_matches()` entrega fechas datetime y outcome de 90 minutos con ET/penales tratados como empate | ✓ VERIFIED | [loading.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/loading.py:27) validates before mutation, converts `date`, and derives `drew_90` from `result_after_extra_time` or `shootout_winner_team_id`; real-history spot check still shows 677 such matches. |
| 5 | RPS y Brier multiclase devuelven los valores esperados | ✓ VERIFIED | [metrics.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/metrics.py:8) implements both metrics; `tests/test_metrics.py` still passes exact-value checks. |
| 6 | El Elo recomputado desde 1000 correlaciona con el snapshot externo en las 48 selecciones | ✓ VERIFIED | [tests/test_elo.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_elo.py:162) enforces Spearman ≥ 0.9; current recomputation check still yields `0.9786956879333604`. |
| 7 | Un empate entre equipos de distinto rating sí mueve el Elo | ✓ VERIFIED | [elo.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/elo.py:52) returns `1.0` for `goal_diff == 0`; [tests/test_elo.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_elo.py:75) still verifies a 1700–1300 draw changes both ratings. |
| 8 | Penales y tiempo extra actualizan el Elo como empate | ✓ VERIFIED | [elo.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/elo.py:66) forces `w_a=0.5` when `drew_after_et=True`; [tests/test_elo.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_elo.py:84) still checks the equivalence. |
| 9 | El baseline solo-Elo produce probabilidades W/D/L válidas y monótonas | ✓ VERIFIED | [baselines.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/baselines.py:39) normalizes clipped ordered-logit probabilities; [tests/test_baselines.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_baselines.py:16) still verifies row sums, bounds, monotonicity, and parameter recovery. |
| 10 | `predict_lambdas(team_a, team_b, ctx)` está congelado y operativo para cualquier par de selecciones del Mundial | ✓ VERIFIED | [dixon_coles.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:252) exposes the module contract; [tests/test_dixon_coles.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:140) freezes the signature; current smoke call still returns positive lambdas for `argentina`–`mexico`. |
| 11 | `predict_lambdas` rechaza slugs desconocidos con `UnknownTeamError` | ✓ VERIFIED | [dixon_coles.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:160) imports and raises `UnknownTeamError`; [tests/test_dixon_coles.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:146) still covers the failure path. |
| 12 | El gradiente analítico Dixon-Coles coincide con el numérico | ✓ VERIFIED | [grad_neg_log_lik](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:64) is implemented, and [tests/test_dixon_coles.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:41) still checks relative error `< 1e-5`. |
| 13 | Las probabilidades W/D/L salen de la matriz de marcadores Dixon-Coles y el empate cae en rango sano | ✓ VERIFIED | [wdl_from_lambdas](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:220) sums the score matrix rather than a logistic; the sanity case `score_matrix(1.25, 1.25, 0.0)` still gives `p_draw = 0.2700464919380503`; [tests/test_dixon_coles.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:162) still enforces the 24–28% band. |
| 14 | Los 4 holdouts usan conteos exactos y cortes temporales estrictos | ✓ VERIFIED | [validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:30) defines the four holdouts and [validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:50) fails loudly on count drift; real-data temporal validation tests still pass for `64/64/51/32` and `date < cutoff`. |
| 15 | `xi` se compara en `{0.00095, 0.0018}` y el gate D-13 queda persistido con métricas por holdout | ✓ VERIFIED | [validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:39) defines `XI_GRID`; [validation_report_2026-06-12.json](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/data/processed/models/validation_report_2026-06-12.json:1) still records `chosen_xi`, `per_holdout`, `xi_search`, and `gate`. |
| 16 | El baseline vence a los baselines naive definidos para la fase | ✓ VERIFIED | The persisted gate still reports mean log-loss `dixon_coles=0.9671839414004801`, `solo_elo=0.9830166784963363`, `uniform=1.0986122886681098`; [validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:129) evaluates the D-13 comparison and `python -m cdd_mundial.models.validation --verify-only` still returns `gate_passed: true`. |
| 17 | El notebook didáctico ejecuta limpio, deriva la matemática core, incluye reliability diagram y está bajo los gates estructurales | ✓ VERIFIED | [02_modelos_baseline.ipynb](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/notebooks/02_modelos_baseline.ipynb:24) still contains the required sections, imports production code, loads `validation_report_*` and `holdout_predictions_*`, references `calibration_curve` and `wdl_from_lambdas`, and the saved notebook remains fully executed with 6 code cells and 0 error outputs. |

**Score:** 17/17 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/cdd_mundial/models/tournaments.py` | Exact tournament → K lookup with loud failure | ✓ VERIFIED | Substantive class + exception; wired to default CSV path; still used by `elo.py`. |
| `data/external/tournament_k_factors.csv` | Reviewed 200-row tournament registry | ✓ VERIFIED | 200 data rows; includes `Copa América` and other exact tournament strings from real history. |
| `src/cdd_mundial/models/loading.py` | Canonical validated match loader with `outcome_90` | ✓ VERIFIED | Validates with Pandera before mutation; derives `outcome_idx`; sorted deterministically. |
| `src/cdd_mundial/models/metrics.py` | `rps()` and `brier_multiclass()` | ✓ VERIFIED | Implemented directly and still covered by exact-value tests. |
| `src/cdd_mundial/models/elo.py` | Elo recompute/materialization/CLI | ✓ VERIFIED | Recomputes Elo from history with fixed canonical WFE parameters, materializes artifacts, and verify-only CLI still passes. |
| `src/cdd_mundial/models/baselines.py` | Uniform and solo-Elo baselines | ✓ VERIFIED | Ordered-logit fit and scoring functions remain present and tested. |
| `data/processed/models/elo_history.parquet` | Point-in-time Elo history | ✓ VERIFIED | 98,810 rows / 49,405 unique matches; validated by `verify_elo_materialization()`. |
| `data/processed/models/elo_ratings.parquet` | Current recomputed Elo snapshot | ✓ VERIFIED | 336 teams; verify-only CLI still reports top team `spain` and top rating `1601.9752545730817`. |
| `src/cdd_mundial/models/dixon_coles.py` | DC fit, score matrix, contract, serialization | ✓ VERIFIED | Substantive implementation; loader, cache, and contract remain wired. |
| `src/cdd_mundial/models/validation.py` | Temporal validation harness and materialization | ✓ VERIFIED | Produces report, holdout parquet, provenance, and production model; verify-only CLI still passes. |
| `data/processed/models/validation_report_2026-06-12.json` | Holdout metrics, xi search, gate result | ✓ VERIFIED | Contains all required keys and non-empty per-holdout metrics. |
| `data/processed/models/holdout_predictions_2026-06-12.parquet` | Reliability-diagram prediction rows | ✓ VERIFIED | 633 rows = 3 models × 211 matches; probabilities still normalize to 1. |
| `data/processed/models/dc_params_2026-06-12.json` | Production DC model for live contract | ✓ VERIFIED | `load_production_model()` and module `predict_lambdas()` still consume it successfully. |
| `notebooks/02_modelos_baseline.ipynb` | Executed didactic notebook | ✓ VERIFIED | 6 executed code cells, 0 error outputs, production imports only. |
| `tests/test_notebooks.py` | Structural notebook gate for phase 02 | ✓ VERIFIED | Still includes notebook 02 in forbidden-fragment and required-analysis checks. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `loading.py` | `contracts.py` | `HistoricalMatchesSchema.validate` before mutation | ✓ WIRED | `load_matches()` still validates first, then converts dates and derives outcomes. |
| `tournaments.py` | `tournament_k_factors.csv` | `from_csv()` default path | ✓ WIRED | Default path still points to `data/external/tournament_k_factors.csv`. |
| `elo.py` | `tournaments.py` | `TournamentKTable.k_factor` per match | ✓ WIRED | `materialize_elo()` still constructs `TournamentKTable.from_csv()` and passes it to `recompute_elo()`. |
| `elo.py` | `data/provenance.py` | `write_provenance_manifest` | ✓ WIRED | Both Elo artifacts still emit provenance manifests during materialization. |
| `__init__.py` | `dixon_coles.py` | Re-export of frozen contract | ✓ WIRED | `from cdd_mundial.models import predict_lambdas` still resolves to the DC module contract. |
| `validation.py` | `dixon_coles.py` | `fit_dixon_coles` + probability conversion | ✓ WIRED | Validation still refits DC at each cutoff and writes the production model. |
| `validation.py` | `baselines.py` | `uniform_wdl`, `fit_solo_elo`, `solo_elo_probs` | ✓ WIRED | Both naive baselines remain computed inside the holdout harness. |
| `validation.py` | `elo_history.parquet` | Pre-match ratings for solo-Elo baseline | ✓ WIRED | `_attach_pre_match_ratings()` still joins `rating_pre_home`/`rating_pre_away` and fails loudly on missing rows. |
| `02_modelos_baseline.ipynb` | `src/cdd_mundial/models` | Production imports only | ✓ WIRED | Notebook still imports `predict_lambdas`, `load_production_model`, `score_matrix`, and `wdl_from_lambdas`. |
| `02_modelos_baseline.ipynb` | `holdout_predictions_*.parquet` | Reliability diagram without refit | ✓ WIRED | Notebook still loads the latest dated holdout predictions artifact and uses it for `calibration_curve`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/cdd_mundial/models/validation.py` | `prediction_rows` / `report` | `load_matches()` + `elo_history.parquet` + per-holdout `fit_dixon_coles()` and baselines | Yes | ✓ FLOWING |
| `src/cdd_mundial/models/dixon_coles.py` | `_PRODUCTION_MODEL` in module `predict_lambdas()` | Latest `dc_params_*.json` loaded from `data/processed/models/` | Yes | ✓ FLOWING |
| `notebooks/02_modelos_baseline.ipynb` | `report_path` / `predictions_path` | Latest `validation_report_*` JSON and `holdout_predictions_*` parquet | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 02 focused model/notebook tests pass | `python -m pytest tests/test_tournaments.py ... tests/test_notebooks.py -q` | `66 passed in 7.52s` | ✓ PASS |
| Full repository suite stays green | `python -m pytest -q` | `165 passed in 56.34s` | ✓ PASS |
| MODEL-01 artifacts verify cleanly | `python -m cdd_mundial.models.elo --verify-only` | `49405` matches, `336` teams, top team `spain` | ✓ PASS |
| MODEL-04 artifacts verify cleanly | `python -m cdd_mundial.models.validation --verify-only` | `chosen_xi=0.00095`, `gate_passed=true`, `prediction_rows=633` | ✓ PASS |
| Frozen production contract returns positive lambdas | module `predict_lambdas("argentina","mexico", ctx)` | `(1.513097124784158, 0.47210187259682984)` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `MODEL-01` | 02-01, 02-02, 02-05 | Custom dynamic Elo with canonical WFE parameters, historical recomputation, and external rank-correlation validation | ✓ SATISFIED | [REQUIREMENTS.md](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/.planning/REQUIREMENTS.md:20) now matches the fixed-WFE implementation and deferred optimization; code, artifacts, and Spearman validation still verify. |
| `MODEL-02` | 02-03, 02-04, 02-05 | Dixon-Coles model exposing `predict_lambdas(team_a, team_b, ctx)` | ✓ SATISFIED | Contract is implemented, re-exported, tested, and activated by `dc_params_2026-06-12.json`. |
| `MODEL-03` | 02-03, 02-05 | W/D/L derived from the DC score matrix | ✓ SATISFIED | `wdl_from_lambdas()` derives W/D/L from `score_matrix()`; draw sanity check still passes in tests and notebook. |
| `MODEL-04` | 02-01, 02-04, 02-05 | Strict temporal validation on four holdouts with log-loss/Brier/RPS | ✓ SATISFIED | Holdout counts, strict cutoffs, xi search, persisted report, persisted predictions, and D-13 gate still verify. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `tests/test_notebooks.py` | 165 | Source-string check for `calibration_curve` / `wdl_from_lambdas` | ℹ️ Info | The test proves the notebook source references the analysis, but not by itself that the rendered plots remain meaningful; execution evidence covers that gap here. |
| `src/cdd_mundial/models/validation.py` | 308 | Provenance verification checks presence, not manifest-to-artifact SHA correspondence | ⚠️ Warning | Phase 02 still passes, but artifact/provenance drift would not be caught by `verify_model04_materialization()`. |

---

_Verified: 2026-06-12T16:02:05Z_  
_Verifier: the agent (gsd-verifier)_
