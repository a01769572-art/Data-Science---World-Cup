---
phase: 2
slug: modelos-baseline
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
updated: 2026-06-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 (markers: network, manual, data_acceptance) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.\.venv\python.exe -m pytest tests/test_<modulo>.py -x -q` |
| **Full suite command** | `.\.venv\python.exe -m pytest -q` |
| **Estimated runtime** | quick ~5-20 s; suite completa ~60-120 s (incluye data_acceptance sobre parquet real y fits DC) |

---

## Sampling Rate

- **After every task commit:** Run `.\.venv\python.exe -m pytest tests/test_<modulo tocado>.py -x -q`
- **After every plan wave:** Run `.\.venv\python.exe -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite green + `jupyter nbconvert --to notebook --execute notebooks/02_modelos_baseline.ipynb` exit 0
- **Max feedback latency:** 120 s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | MODEL-01/04 (deps) | T-02-03 | Solo deps Wave 0 pineadas; sin penaltyblog en pyproject | smoke | `.\.venv\python.exe -c "import scipy, sklearn, matplotlib, seaborn, joblib; print('wave0-ok')"` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | MODEL-01 (tabla K) | T-02-02 | UnknownTournamentError, sin matching difuso | unit + data_acceptance | `pytest tests/test_tournaments.py -x -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | MODEL-04 (métricas) / D-05 | T-02-01 | Schema pandera validado antes de mutar | unit | `pytest tests/test_loading.py tests/test_metrics.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | MODEL-01 | — | Empate mueve rating; shootout=W=0.5 | unit | `pytest tests/test_elo.py -x -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | MODEL-01 | T-02-05/06/07 | Schemas + provenance sha256; Spearman ≥ 0.9 | data_acceptance | `pytest tests/test_elo.py -x -q -m data_acceptance` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 2 | MODEL-04 (baseline solo-Elo) | — | Probabilidades normalizadas y monótonas | unit | `pytest tests/test_baselines.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | MODEL-02 | T-02-11 | rho acotado; gradiente verificado vs numérico | unit | `pytest tests/test_dixon_coles.py -x -q` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | MODEL-02/03 | T-02-09/10/12 | UnknownTeamError; firma congelada por test; JSON, no pickle | unit | `pytest tests/test_dixon_coles.py -x -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | MODEL-04 | T-02-13/14/16 | Corte estricto; conteos 64/64/51/32 como gate duro | unit + data_acceptance | `pytest tests/test_validation_temporal.py -x -q` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 3 | MODEL-02/04 | T-02-15 | Reporte fechado con provenance; gate reportado pase o no | data_acceptance | `pytest tests/test_validation_temporal.py -x -q -m data_acceptance` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 4 | D-14/D-15 (DOC-01) | T-02-18 | Gate anti-secretos escanea outputs | existente (auto-paramétrico) | `jupyter nbconvert --execute --stdout ...02_modelos_baseline.ipynb; pytest tests/test_notebooks.py -x -q` | ✅ | ⬜ pending |
| 02-05-02 | 05 | 4 | D-15 | T-02-19 | Notebook solo invoca, nunca define | unit (gate extendido) | `pytest -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] pyproject.toml + `pip install -e ".[dev]"` — scipy/scikit-learn/matplotlib/seaborn/joblib (plan 02-01 Task 1)
- [ ] `tests/test_tournaments.py` — cobertura K (plan 02-01 Task 2)
- [ ] `tests/test_loading.py`, `tests/test_metrics.py` — MODEL-04 métricas (plan 02-01 Task 3)
- [ ] `tests/test_elo.py` — MODEL-01 (plan 02-02)
- [ ] `tests/test_baselines.py` — comparadores gate D-13 (plan 02-02)
- [ ] `tests/test_dixon_coles.py` — MODEL-02/03, incluye recuperación sintética con seed fija (plan 02-03)
- [ ] `tests/test_validation_temporal.py` — MODEL-04 cortes estrictos y conteos (plan 02-04)
- [ ] `data/external/tournament_k_factors.csv` — tabla revisada de 200 strings (plan 02-01 Task 2)

Los archivos de test se crean DENTRO del mismo task que el módulo que verifican (tdd="true" con `<behavior>`): ningún task referencia un test inexistente de otro plan.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Calidad didáctica del notebook (claridad de derivaciones D-14) | D-14 | Juicio humano sobre pedagogía | Leer el notebook renderizado; las derivaciones LaTeX deben ser seguibles a nivel ingeniería |

Todo lo demás tiene verificación automatizada.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120 s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending execution
