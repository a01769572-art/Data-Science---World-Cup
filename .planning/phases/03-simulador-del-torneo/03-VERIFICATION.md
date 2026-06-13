---
phase: 03-simulador-del-torneo
verified: 2026-06-12T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
---

# Fase 3: Simulador del Torneo — Reporte de Verificación

**Objetivo de la fase:** El motor Monte Carlo simula el formato 2026 completo con reglas FIFA verificadas contra el reglamento oficial, condicional al estado real del torneo — construible en paralelo con Fase 2 vía λs stub.
**Verificado:** 2026-06-12
**Estado:** passed
**Re-verificación:** No — verificación inicial

## Logro del Objetivo

La verificación parte del objetivo y trabaja hacia atrás. Las cinco Success Criteria del ROADMAP y las 14 verdades (truths) declaradas en los `must_haves` de los cinco planes fueron confirmadas contra el código real, no contra los SUMMARY. La evidencia primaria es la ejecución directa de las suites de prueba con el venv del proyecto, complementada con inspección de artefactos para descartar stubs y verificar el cableado y el flujo de datos.

### Verdades Observables

| # | Verdad (origen) | Estado | Evidencia |
| --- | --- | --- | --- |
| 1 | (SC1 / 03-01) Evidencia regulatoria FIFA 2026 fijada localmente con URL oficial HTTPS, timestamp, checksum y punteros de artículo/anexo | ✓ VERIFIED | `data/metadata/fifa_2026_regulations.provenance.json` (6910 B): `source_url` digitalhub.fifa.com, `sha256` bad4ea83…, `retrieved_at_utc`, `article_pointers` (Art. 13/14/12), `annex_pointers` (Annexe C, 495 opciones) |
| 2 | (03-01) Fixture de combinaciones esperadas autoría independiente que enumera los conjuntos de 8-de-12 grupos | ✓ VERIFIED | `tests/fixtures/tournament/third_place_expected_combinations.json` (9090 B); 495 = C(12,8); validador cruza expected vs mapping sin inferir |
| 3 | (03-01) Artefacto de asignación de mejores terceros revisado, exhaustivo, biyectivo, compatible con tokens de slot | ✓ VERIFIED | `third_place_mapping_official.json` (152 KB) + `tests/validators/validate_third_place_mapping.py`; `test_slot_resolution.py` passa (parte del quick suite, 83 passed) |
| 4 | (SC1 / 03-03/03-04) `rules_fifa.py` implementa la cascada completa (h2h → reaplicación residual → criterios globales → conduct score → ediciones sucesivas ranking FIFA), fallando ruidosamente sin sorteo | ✓ VERIFIED | `src/cdd_mundial/simulation/rules_fifa.py`: `_resolve_head_to_head`, `_resolve_tail`, `_resolve_by_fifa_ranking` con `raise ValueError` (no randomness); `test_rules_fifa.py` passa (incl. Grupo H 2018, empates 3/4 bandas) |
| 5 | (03-03) Tests Wave 0 (Nyquist) y fixtures con `expected_order` existen antes de la implementación pura | ✓ VERIFIED | `test_rules_fifa.py`, `test_slot_resolution.py`, validador `assert_phase03_red.py`; commits d32f191/35cf9f0 (tests rojos) preceden a 03-04 |
| 6 | (03-02) Paquete `simulation/` existe y exporta los primeros contratos estables | ✓ VERIFIED | `src/cdd_mundial/simulation/__init__.py` exporta rules_fifa, slots, state, knockout; importado por engine y tests |
| 7 | (SC3 / 03-02) Resultados jugados almacenados como registros thin `team_a`/`team_b`, fijos en cada semilla | ✓ VERIFIED | `state.py` `PlayedMatchResult` valida claves, goles >=0, equipos distintos, rechaza standings derivados; `test_tournament_state.py` + `test_simulation_engine.py` (conditioning) passan |
| 8 | (SC5 / 03-02) Empates de knockout post-90' producen exactamente un avance, sin sesgo de orden, sin λ de tiempo extra | ✓ VERIFIED | `knockout.py` `post_draw_advance_probability`: q=0.5 sin señal, simétrico por construcción; `test_knockout.py` passa (complemento, 0.5, bias <0.005) |
| 9 | (SC1 / 03-04) Ranking de grupo y mejores terceros por funciones puras según Art. 13 hasta ediciones FIFA | ✓ VERIFIED | `rank_group`, `rank_best_thirds` en rules_fifa.py; cross-group h2h ignorado deliberadamente; tests verdes |
| 10 | (03-04) Slots de tercer lugar en R32 resueltos del mapping oficial preservando los slot strings del fixture congelado | ✓ VERIFIED | `slots.py` `resolve_third_place_assignments`, parsing de `1A`/`3ABCDF`/`W74`/`L101`; importado por `engine.py:59`; `test_slot_resolution.py` verde |
| 11 | (SC2 / 03-05) ≥10,000 torneos bajo el gate duro (<60s), NumPy-first, semillas fijas, CRN estables | ✓ VERIFIED | `test_simulation_performance.py -m performance`: **2 passed**; 100k en **6.79s** (10k muy por debajo de 60s); reproducibilidad en `test_simulation_engine.py` |
| 12 | (SC3 / 03-05) Jugados fijos; solo no resueltos llaman `predict_lambdas(team_a,team_b,ctx)` con outcomes estocásticos | ✓ VERIFIED | `engine.py:185` `lambda_cache[key]=predict_lambdas(a,b,ctx)`; conditioning probado en engine tests |
| 13 | (SC4 / 03-05) Tablas marginales estables de 48 equipos para avance y posición de grupo, sin enumeración conjunta | ✓ VERIFIED | `outputs.py` columnas exactas `p_r32…p_champion`, `p_1st…p_4th`; `test_simulation_outputs.py` (totales, monotonía, sumas) verde |
| 14 | (03-05) Notebook integral ejecutado importa la API de producción, demo determinística ligera, opciones 10k/100k | ✓ VERIFIED | `notebooks/03_simulador_torneo.ipynb`: `from cdd_mundial.simulation`, execution_count secuencial, 9 celdas con output, 1 plot PNG; `test_notebooks.py` **25 passed** |

**Puntuación:** 14/14 verdades verificadas

### Cobertura de las Success Criteria del ROADMAP

| SC | Descripción | Verdades de soporte | Estado |
| --- | --- | --- | --- |
| SC1 | rules_fifa cascada + mejores terceros + asignación R32 vs PDF oficial + tests históricos | 1,2,3,4,9,10 | ✓ SATISFIED |
| SC2 | ≥10k (objetivo 100k) <1 min, numpy, semilla fija | 11 | ✓ SATISFIED |
| SC3 | Partidos jugados fijos, solo se simula lo restante (TournamentState) | 7,12 | ✓ SATISFIED |
| SC4 | Tablas P(R32)…P(Campeón) por selección | 13 | ✓ SATISFIED |
| SC5 | Eliminatorias ~50/50 con desempate aleatorio sin sesgo de orden | 8 | ✓ SATISFIED |

### Artefactos Requeridos

| Artefacto | Esperado | Estado | Detalle |
| --- | --- | --- | --- |
| `data/metadata/fifa_2026_regulations.provenance.json` | Provenance inmutable oficial | ✓ VERIFIED | URL, SHA-256, artículos, Annexe C (495), reviewed_extraction |
| `tests/fixtures/tournament/third_place_expected_combinations.json` | Combinaciones esperadas autoría independiente | ✓ VERIFIED | 9090 B |
| `tests/fixtures/tournament/third_place_mapping_official.json` | Mapping oficial revisado | ✓ VERIFIED | 152 KB, consumido por validador |
| `tests/validators/validate_third_place_mapping.py` | Validador de contrato del mapping | ✓ VERIFIED | 16565 B |
| `src/cdd_mundial/simulation/__init__.py` | Exports del paquete | ✓ VERIFIED | Exporta rules_fifa/slots/state/knockout |
| `src/cdd_mundial/simulation/state.py` | Estado thin de jugados | ✓ VERIFIED | Validación completa, sin standings derivados |
| `src/cdd_mundial/simulation/knockout.py` | Resolver compacto post-90' | ✓ VERIFIED | Simétrico por construcción |
| `tests/test_tournament_state.py` | Invariantes de estado | ✓ VERIFIED | Verde en quick suite |
| `tests/test_knockout.py` | Simetría y no-sesgo | ✓ VERIFIED | Verde en quick suite |
| `tests/test_rules_fifa.py` | Tests de reglas | ✓ VERIFIED | Verde |
| `tests/test_slot_resolution.py` | Tests de slots | ✓ VERIFIED | Verde |
| `tests/validators/assert_phase03_red.py` | Validador red-test Nyquist | ✓ VERIFIED | Presente |
| `src/cdd_mundial/simulation/rules_fifa.py` | Funciones puras de reglas | ✓ VERIFIED | Cascada completa, sin stubs |
| `src/cdd_mundial/simulation/slots.py` | Parsing de tokens + R32 | ✓ VERIFIED | Cableado en engine |
| `src/cdd_mundial/simulation/engine.py` | Motor vectorizado + conditioning + RNG | ✓ VERIFIED | 17 KB, CR-01 corregido (a083013) |
| `src/cdd_mundial/simulation/outputs.py` | Tablas de probabilidad | ✓ VERIFIED | Columnas exactas |
| `tests/test_simulation_engine.py` | Vectorización/conditioning/repro/oracle | ✓ VERIFIED | Verde |
| `tests/test_simulation_outputs.py` | Invariantes de tablas | ✓ VERIFIED | Verde |
| `tests/test_simulation_performance.py` | Gate 10k + medición 100k | ✓ VERIFIED | 2 passed (100k en 6.79s) |
| `notebooks/03_simulador_torneo.ipynb` | Notebook integral ejecutado | ✓ VERIFIED | Ejecutado, plot, gates verdes |
| `tests/test_notebooks.py` | Gates de estructura/import/ejecución | ✓ VERIFIED | 25 passed |

### Verificación de Key Links

| De | A | Vía | Estado | Detalle |
| --- | --- | --- | --- | --- |
| engine.py | models/dixon_coles.py | `predict_lambdas(team_a,team_b,ctx)` | ✓ WIRED | `engine.py:58,185`; notebook usa `predict_lambdas` real |
| engine.py | rules_fifa.py | ranking de grupo / mejores terceros | ✓ WIRED (diseño) | El engine implementa los criterios globales vectorizados inline (`engine.py:212-262`); `rules_fifa.py` mantiene el contrato puro de la cascada de desempates (h2h/conduct/ranking) probado por unit tests. Conforme a `03-VALIDATION.md`: los partidos simulados no portan inputs de conduct/ranking. No es un stub |
| engine.py | slots.py | `resolve_third_place_assignments` | ✓ WIRED | `engine.py:59` import + uso |
| outputs.py | test_simulation_outputs.py | monotonía y totales | ✓ WIRED | Columnas `p_champion`/`p_1st`; tests verdes |
| notebook | cdd_mundial.simulation | `from cdd_mundial.simulation` | ✓ WIRED | Import presente; test de import verde |
| expected_combinations.json | mapping_official.json | combinaciones independientes vía validador | ✓ WIRED | Validador cruza sin inferir del mapping |
| mapping_official.json | fixture_2026.csv | selectores vs filas R32 reales | ✓ WIRED | `selector_key` contra fixture |
| provenance.json | expected_combinations / mapping | `annex_refs` / `reviewed_extraction` | ✓ WIRED | Annexe C punteros presentes |

### Flujo de Datos (Nivel 4)

| Artefacto | Variable | Fuente | Datos reales | Estado |
| --- | --- | --- | --- | --- |
| outputs.py advancement_table | `probs[:, ...]` | `SimulationResult` (conteos / n_sims) del engine vectorizado | Sí — derivado de simulación Monte Carlo real | ✓ FLOWING |
| outputs.py group_position_table | `group_position_counts` | engine `np.add.at` sobre rankings simulados | Sí | ✓ FLOWING |
| notebook tablas/plot | API de producción | `cdd_mundial.simulation` + `predict_lambdas` | Sí — outputs determinísticos commiteados | ✓ FLOWING |

### Behavioral Spot-Checks

| Comportamiento | Comando | Resultado | Estado |
| --- | --- | --- | --- |
| Quick suite (reglas, slots, estado, engine, outputs, knockout) | `pytest … -m "not performance"` | 83 passed in 22.31s | ✓ PASS |
| Notebook gate | `pytest tests/test_notebooks.py` | 25 passed in 3.51s | ✓ PASS |
| Performance gate (10k <60s, 100k medido) | `pytest tests/test_simulation_performance.py -m performance` | 2 passed; 100k en 6.79s | ✓ PASS |
| Suite completa del repo (sin performance) | `pytest -m "not performance"` | 258 passed, 2 deselected in 97.32s | ✓ PASS |

### Cobertura de Requisitos

| Requisito | Plan(es) | Descripción | Estado | Evidencia |
| --- | --- | --- | --- | --- |
| SIM-01 | 03-01, 03-03, 03-04 | Reglas FIFA completas verificadas vs reglamento + tests históricos | ✓ SATISFIED | Verdades 1-5,9,10; provenance real; test_rules_fifa/test_slot_resolution verdes |
| SIM-02 | 03-05 | Monte Carlo vectorizado ≥10k (objetivo 100k) <1 min | ✓ SATISFIED | Verdad 11; performance gate 2 passed (100k 6.79s) |
| SIM-03 | 03-02, 03-05 | Condicional al estado real; jugados fijos | ✓ SATISFIED | Verdades 7,12; state.py + conditioning tests |
| SIM-04 | 03-05 | Tablas P(R32)…P(Campeón) | ✓ SATISFIED | Verdad 13; outputs.py + invariantes |
| SIM-05 | 03-02, 03-05 | Eliminatorias ~50/50 sin sesgo de orden | ✓ SATISFIED | Verdad 8; knockout.py + bias <0.005 |

Los 5 IDs de requisito (SIM-01…SIM-05) están declarados en frontmatter de planes y mapeados a `Phase 3 | Complete` en REQUIREMENTS.md. No hay requisitos huérfanos.

### Anti-Patrones Encontrados

| Archivo | Línea | Patrón | Severidad | Impacto |
| --- | --- | --- | --- | --- |
| — | — | — | — | Ninguno bloqueante. Code review previo (03-REVIEW.md) reportó CR-01 (np.unique inverse shape numpy 2.0/2.1), corregido en commit a083013 (verificado: engine.py líneas 302/400). Hallazgos restantes del review son advisory (warning/info), no bloqueantes |

### Verificación Humana Requerida

Ninguna. Todas las Success Criteria del ROADMAP y las verdades de los planes se verifican programáticamente mediante suites de prueba que ejecutan código de producción real. El único elemento potencialmente visual (el plot del notebook, D-15) está presente (1 PNG renderizado) y aseverado por un test verde (`test_notebooks.py`).

### Resumen

El objetivo de la fase se logra de forma completa y substantiva. El gate regulatorio fail-closed (03-01) está respaldado por evidencia oficial real: PDF FIFA con SHA-256, punteros de artículo (Art. 13 cascada, Art. 14 tiempo extra/penales) y Annexe C con las 495 combinaciones de mejores terceros — confirmando que el fallback es por ediciones del ranking FIFA y no por sorteo, tal como exige el contrato. `rules_fifa.py` implementa la cascada completa fallando ruidosamente sin aleatoriedad. El motor Monte Carlo vectorizado en numpy supera el gate duro con amplio margen (100k torneos en 6.79s frente al límite de 60s para 10k), con conditioning real al estado del torneo, salidas marginales de 48 equipos con invariantes exactos, y resolución de knockout simétrica sin sesgo de orden. El notebook integral está ejecutado e importa la API de producción. La suite completa del repositorio (258 tests) pasa sin regresiones, y el único blocker del code review (CR-01) está corregido y verificado en el código.

El key link engine→rules_fifa merece una nota: el engine no llama a `rules_fifa.best_thirds` en el bucle caliente, sino que implementa los criterios globales (puntos→GD→GF) vectorizados inline, dejando la cascada de desempates exacta (h2h/conduct/ranking FIFA) en `rules_fifa.py` para el contrato puro y los unit tests. Esto es conforme al diseño documentado en `03-VALIDATION.md` ("los partidos simulados no portan inputs de conduct ni ranking") y no constituye un stub ni una desconexión: ambas piezas existen, son substantivas y están cableadas a sus respectivos consumidores.

---

_Verificado: 2026-06-12_
_Verificador: Claude (gsd-verifier)_
