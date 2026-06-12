---
status: testing
phase: 01-fundaci-n-de-datos
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-06-11T22:45:00Z
updated: 2026-06-11T22:45:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: Suite completa de tests pasa
expected: |
  Corriendo `.\.venv\python.exe -m pytest -q` desde la raíz del repo, toda la suite pasa
  (≥58 tests: contratos, provenance, identidades, ingesta martj42, Elo, fixture, repo-safety)
  sin fallos ni errores, y `.\.venv\python.exe -m ruff check src tests` pasa limpio.
awaiting: user response

## Tests

### 1. Suite completa de tests pasa
expected: `.\.venv\python.exe -m pytest -q` pasa toda la suite (≥58 tests) sin fallos; `ruff check src tests` limpio
result: [pending]

### 2. Base histórica martj42 materializada (DATA-01)
expected: El gate de aceptación real pasa — `.\.venv\python.exe -m pytest -q -m data_acceptance tests/test_data01_acceptance.py` — verificando 49,405 partidos completados, 336 identidades exactas, parquet cargable y checksums de provenance
result: [pending]

### 3. Tabla maestra canónica de 48 selecciones (DATA-02)
expected: `data/external/teams.csv` contiene exactamente 48 selecciones con IDs slug estables; `data/external/team_aliases.csv` cubre las 5 fuentes (martj42, eloratings, fifa, fixture, odds); el resolver rechaza nombres desconocidos/ambiguos
result: [pending]

### 4. Elo actual cargado con cobertura completa
expected: El snapshot Elo de eloratings.net está en parquet validado con los 48 participantes resueltos (0 identidades sin rating), captura inmutable del TSV y manifiesto de provenance en `data/metadata/`
result: [pending]

### 5. Fixture 2026 congelado y validado (DATA-04)
expected: `data/external/fixture_2026.csv` tiene 104 partidos con match IDs únicos, 72 de fase de grupos en 12 grupos de 6, kickoffs UTC terminando en `Z`, participantes canónicos en grupos y slots oficiales sin resolver en eliminatorias
result: [pending]

### 6. Repositorio seguro para publicación
expected: `git ls-files` no muestra `.env`, payloads de cuotas restringidos, capturas raw restringidas ni contenido `.claude/`; `.env.example` existe con `ODDS_API_KEY` vacío; los tests de repo-safety lo verifican automáticamente
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0

## Gaps

[none yet]
