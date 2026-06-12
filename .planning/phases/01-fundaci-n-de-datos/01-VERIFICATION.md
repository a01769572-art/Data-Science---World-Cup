---
phase: 01-fundaci-n-de-datos
verified: 2026-06-12T01:32:16Z
status: gaps_found
score: 15/18 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Las 48 selecciones resuelven contra la tabla canonica en cada fuente mediante un gate duro que impide mismatches de nombres."
    status: failed
    reason: "La cobertura de aliases pasa, pero el fixture no enlaza sus slots A1-L4 con TeamResolver ni valida que cada slot corresponda al team_id prellenado. Un fixture mutado A1=south-africa y A2=mexico fue aceptado."
    artifacts:
      - path: "src/cdd_mundial/data/ingest_fixture.py"
        issue: "TeamResolver solo aporta el conjunto de IDs conocidos; no se llama resolve() ni existe un mapa slot->team_id."
      - path: "tests/test_phase1_acceptance.py"
        issue: "El gate comprueba existencia de aliases por fuente, no la correspondencia entre filas reales del fixture y IDs canonicos."
    missing:
      - "Persistir o derivar un mapa oficial de slots de grupo a nombres/IDs canonicos."
      - "Validar home_slot/home_team_id y away_slot/away_team_id antes de aceptar el fixture."
      - "Agregar un test que intercambie IDs de un partido y exija rechazo."
  - truth: "Cada archivo adquirido conserva provenance durable con fuente, version, timestamp, checksum, licencia y ruta local."
    status: failed
    reason: "Los manifests se nombran solo por basename y se sobrescriben entre versiones; ademas los dos payloads raw de cuotas no tienen manifest de checksum. Se encontraron 6 de 11 archivos raw sin manifest que los referencie."
    artifacts:
      - path: "src/cdd_mundial/data/provenance.py"
        issue: "write_provenance_manifest usa record.local_path.name, por lo que World.tsv y en.teams.tsv colisionan entre snapshots."
      - path: "data/raw/eloratings"
        issue: "Cuatro capturas de dos versiones anteriores quedaron sin metadata direccionable."
      - path: "data/raw/odds"
        issue: "Dos payloads restringidos estan ignorados correctamente, pero carecen de manifest/checksum individual."
    missing:
      - "Usar nombres/rutas de manifest que incluyan source y source_version."
      - "Emitir provenance para cada captura raw de cuotas sin publicar el payload."
      - "Agregar un test de dos versiones con el mismo basename que pruebe que ambos manifests sobreviven."
deferred:
  - truth: "Elo dinamico custom recomputado desde el historico."
    addressed_in: "Phase 2"
    evidence: "ROADMAP Phase 2 success criterion 1 and REQUIREMENTS MODEL-01 assign K por torneo, localia y margen de victoria to the baseline-model phase; DATA-03 now covers the current 48-team snapshot."
---

# Phase 1: Fundacion de Datos Verification Report

**Phase Goal:** Existe una base de datos limpia, unificada y validada donde toda fuente resuelve contra la tabla maestra canonica de selecciones; nada downstream puede romperse por mismatch de nombres.
**Verified:** 2026-06-12T01:32:16Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | El paquete instala el stack fijado y la suite no-network pasa | VERIFIED | `107 passed`; `ruff check src tests` limpio; pins y Python 3.11/3.12 comprobados por `tests/test_repository.py`. |
| 2 | La base martj42 real esta materializada y validada | VERIFIED | `verify-only`: 49,405 filas, 336 identidades, version `2026-06-11`, parquet SHA-256 `067ada...b239`; acceptance real paso. |
| 3 | El historico retiene IDs canonicos y nombres originales | VERIFIED | `HistoricalMatchesSchema` valida parquet; builder conserva `*_source_name` y resuelve ambos lados mediante `TeamResolver`. |
| 4 | Marcadores, prorroga y penales conservan la semantica fuente | VERIFIED | Scores no se alteran; ganador de penales vive en columna separada; tests de fixtures y parquet pasan. |
| 5 | Nombres desconocidos o ambiguos detienen la ingesta | VERIFIED | `UnknownTeamError`/`AmbiguousTeamError`; tests cubren ambos errores y no existe fuzzy fallback. |
| 6 | Existen 48 filas canonicas y aliases revisados | VERIFIED | 48 participantes unicos; 530 aliases totales; los 242 aliases de participantes resolvieron exactamente al ID esperado. |
| 7 | El gate de identidad enlaza cada fuente real a su ID canonico | FAILED | Cobertura 240/240 por existencia de alias, pero el fixture usa slots opacos y acepta IDs intercambiados. |
| 8 | Elo actual se adquiere con HTTP acotado y cobertura 48/48 | VERIFIED | Parquet validado: 48 filas, 48 IDs, 0 faltantes; tests cubren timeout/retry/HTML y las dos capturas actuales tienen checksum valido. |
| 9 | Fixture contiene 104 partidos, 72 de grupos y UTC | VERIFIED | 104 IDs unicos, 72 group, seis por grupo A-L, todos los kickoffs terminan en `Z`; checksum coincide con manifest. |
| 10 | Fixture coincide con el calendario FIFA vigente | UNCERTAIN | Solo existe la afirmacion de aprobacion en SUMMARY; el `01-UAT.md` independiente permanece `testing` con seis resultados pendientes. |
| 11 | Seleccion del proveedor de cuotas esta documentada | VERIFIED | Policy JSON registra provider, terms, probe 200, 71 eventos y storage restringido. |
| 12 | Solo mercados h2h de tres vias son aceptados | VERIFIED | Tests rechazan dos vias, draws duplicados, mercados incompatibles, quotes stale y fixtures sin match. |
| 13 | Cuotas producen benchmark canonico de-margined | VERIFIED | 1,385 filas, 71 fixtures, 24 bookmakers, 48 equipos, 0 IDs nulos, error maximo de suma `2.22e-16`. |
| 14 | Secretos y raw restringido no estan publicados | VERIFIED | GitHub API: repo publico; `.env`, raw odds/Elo y `data/processed` devuelven 404 y no estan tracked; `.env.example` esta vacio. |
| 15 | Cada captura adquirida tiene provenance durable | FAILED | 6/11 raw files no son objetivo de ningun manifest; nombres por basename sobrescriben snapshots anteriores. |
| 16 | Notebook usa codigo de produccion y MD->codigo->MD | VERIFIED | Gates estructurales pasan y el notebook importa `cdd_mundial.data`. |
| 17 | README cubre setup, provenance, licencias y limitaciones | VERIFIED | Secciones y contenido requeridos pasan tests; README y notebook existen en `origin/main`. |
| 18 | Un gate de aceptacion cubre los siete requirement IDs | VERIFIED | Suite completa y acceptance focalizado pasan; los artefactos reales se comprobaron aparte para evitar depender de fallbacks pequenos. |

**Score:** 15/18 truths verified

### Deferred Items

| Item | Addressed In | Evidence |
|---|---|---|
| Elo dinamico custom desde el historico | Phase 2 | `MODEL-01` y Phase 2 SC1 lo asignan explicitamente a modelos baseline. No existe en Phase 1 y no se conto como fallo de DATA-03. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `data/processed/historical_matches.parquet` | Historico real validado | VERIFIED | 49,405 filas; checksum y raw martj42 coherentes. |
| `data/external/teams.csv` + `team_aliases.csv` | Registro y aliases canonicos | VERIFIED | 48 participantes; cobertura declarativa 240/240. |
| `src/cdd_mundial/data/identities.py` | Resolucion exacta | VERIFIED | Sustantivo, usado por martj42, Elo y odds. |
| `src/cdd_mundial/data/ingest_fixture.py` | Fixture canonicalizado | PARTIAL | Valida estructura e IDs conocidos, pero no enlaza slot fuente con ID. |
| `data/processed/elo_current.parquet` | Snapshot Elo | VERIFIED | 48/48, schema valido, version explicita. |
| `data/external/fixture_2026.csv` | Fixture congelado | VERIFIED | 104/72 y checksum valido; fidelidad FIFA requiere revision humana independiente. |
| `data/processed/odds_2026.parquet` | Benchmark de mercado | VERIFIED | Datos reales no vacios y flujo canonico completo. |
| `src/cdd_mundial/data/provenance.py` | Metadata durable por captura | STUB/PARTIAL | Funciona para un basename, pero pierde historial entre versiones. |
| `README.md` + `notebooks/01_data_foundation.ipynb` | Documentacion publica | VERIFIED | Presentes en GitHub publico y sin secretos detectados. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| martj42 ingestion | aliases/contracts/parquet | resolver + schema | WIRED | Raw -> exact IDs -> schema -> parquet. |
| Elo endpoints | raw/provenance/aliases/parquet | bounded HTTP + resolver | WIRED | Snapshot actual 48/48. |
| Fixture CSV | aliases | `TeamResolver` | NOT_WIRED | Importado, pero nunca se resuelven slots/nombres de la fuente. |
| Odds payload | aliases + fixture + schema | resolver, pair/time link | WIRED | 71 fixtures y 48 equipos fluyen a output real. |
| Provenance records | immutable captures | manifest writer | PARTIAL | Colisiona por basename y odds raw no emite manifest. |
| Notebook/README | production modules/metadata | imports and documented paths | WIRED | Tests estructurales y remote contents verificados. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full suite | `.venv/python.exe -m pytest -q` | 107 passed | PASS |
| Lint | `.venv/python.exe -m ruff check src tests` | All checks passed | PASS |
| Real DATA-01 gate | `pytest -m data_acceptance tests/test_data01_acceptance.py` | 1 passed | PASS |
| Real materialization | `python -m ...ingest_martj42 --verify-only` | 49,405 / 336 / checksum valid | PASS |
| Production Elo/fixture/odds | Direct schema/load audit | 48; 104/72; 1,385 rows | PASS |
| Fixture mismatch rejection | Swap IDs for A1/A2 in memory | Validator accepted invalid mapping | FAIL |
| Public visibility | GitHub API | `private=false`, `visibility=public` | PASS |

### Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| DATA-01 | SATISFIED | Real parquet, immutable martj42 raw, exact counts, schema and checksums verified. |
| DATA-02 | BLOCKED | Aliases resolve, but the fixture source-to-ID mapping is not enforced by code or tests. |
| DATA-03 | SATISFIED | Current Elo snapshot is 48/48; custom recomputation is explicitly Phase 2 `MODEL-01`. |
| DATA-04 | NEEDS HUMAN | Structural artifact passes; independent comparison to the current official FIFA schedule remains open. |
| DATA-05 | SATISFIED | Real de-margined benchmark exists and passes contracts. |
| DOC-01 | SATISFIED | Notebook structure and production imports are automated gates. |
| DOC-03 | SATISFIED WITH DEBT | Repo is public and clean; rendered portfolio-quality review remains represented only by SUMMARY while untracked UAT is pending. |

**Requirements score:** 5/7 fully satisfied; 1 blocked; 1 needs independent human verification.

### Anti-Patterns and Verification Debt

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/cdd_mundial/data/ingest_fixture.py` | 48 | Resolver instantiated but not used for source identity | BLOCKER | Swapped canonical assignments pass. |
| `src/cdd_mundial/data/provenance.py` | 58 | Manifest key is basename only | BLOCKER | Later snapshots overwrite metadata history. |
| `.planning/phases/01-fundaci-n-de-datos/01-UAT.md` | 2 | `status: testing`, six pending results | WARNING | Conversational UAT is not closed; file preserved unchanged and untracked. |
| `.planning/phases/01-fundaci-n-de-datos/01-VALIDATION.md` | 41 | Many implemented tests still marked pending | WARNING | Validation ledger is stale, though commands pass. |
| Git state | n/a | Local HEAD is one planning-only commit ahead of `origin/main` | INFO | Contradicts SUMMARY's `0 0` sync claim; public README/notebook implementation is present remotely. |

### Human Verification Required

1. Compare all 104 fixture rows, kickoff UTC values, venues and group-slot assignments with the current official FIFA schedule.
2. Review the rendered README and notebook for portfolio quality and close or supersede the pending `01-UAT.md` intentionally.
3. Reconfirm the current odds-provider terms permit the documented local raw-storage and derived-use policy.

### Gaps Summary

The production datasets are present, non-empty and broadly well validated. The phase goal is still blocked because the fixture's real source identity is not bound to canonical IDs, so a name/slot mismatch can survive every current gate. Provenance is also not durable across repeated acquisitions: six raw captures have no surviving per-file manifest. These are codebase-observable failures, not missing SUMMARY prose.

---

_Verified: 2026-06-12T01:32:16Z_
_Verifier: Codex (gsd-verifier)_
