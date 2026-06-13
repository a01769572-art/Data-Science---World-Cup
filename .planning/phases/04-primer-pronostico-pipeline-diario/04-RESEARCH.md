# Phase 04: Primer Pronostico + Pipeline Diario - Research

**Researched:** 2026-06-13 [VERIFIED: session date]
**Domain:** Daily forecasting publication pipeline for conditioned World Cup simulation, immutable snapshots, static HTML reporting, and live calibration. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
**Confidence:** MEDIUM [VERIFIED: synthesis of verified codebase state plus a few implementation-shape decisions left to planning]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `results_2026.csv` es la fuente canónica y versionable de resultados jugados para la corrida diaria. Cualquier scraper externo solo puede validar o asistir; nunca sustituye la autoridad del CSV.
- **D-02:** El sistema puede re-simular en cualquier momento cuando cambie el estado real del torneo, pero el snapshot oficial publicable se genera una vez por jornada o antes del bloque relevante de partidos y se commitea append-only antes del kickoff correspondiente.
- **D-03:** `results_2026.csv` se mantiene minimalista, con solo las columnas necesarias para construir `TournamentState`. La metadata operativa vive en artefactos separados.
- **D-04:** Si existe scraper auxiliar, se usa como verificación contra el CSV canónico. Si hay discrepancias, la corrida oficial falla o exige corrección explícita; no publica silenciosamente.
- **D-05:** Si `results_2026.csv` está incompleto para partidos ya jugados, el pipeline falla por defecto. Solo puede continuar con override explícito y trazable.
- **D-06:** La corrida oficial usa modo mixto: el modo publicable rehace/refresca desde artefactos canónicos y estado observado, mientras que un modo rápido incremental puede existir solo para exploración, nunca como publicación oficial.
- **D-07:** El pipeline oficial vive en script/comando reproducible; el notebook de Jupyter puede dispararlo e inspeccionarlo, pero no define por sí solo el proceso oficial.
- **D-08:** Cada snapshot oficial es rico: incluye probabilidades por equipo, pronósticos del bloque próximo y metadata suficiente para reconstruir exactamente la corrida oficial.
- **D-09:** Cada snapshot vive en una carpeta propia append-only con varios archivos separados, no en un único archivo monolítico.
- **D-10:** `metadata.json` debe incluir obligatoriamente el commit hash del código usado para generar el snapshot.
- **D-11:** Por defecto, la publicación oficial exige worktree limpio. Si el repo está dirty, solo continúa con override explícito y `metadata.json` debe registrar `dirty=true` y los archivos modificados relevantes.
- **D-12:** Los datos canónicos del snapshot siempre se versionan; el reporte renderizado se guarda además cuando la corrida corresponda a una publicación oficial.
- **D-13:** `model_version` sigue un esquema semántico por familia + fecha + commit corto, por ejemplo `baseline-v1-2026-06-14-abc1234`.
- **D-14:** El reporte oficial de la fase es un HTML estático generado automáticamente. Puede combinar `matplotlib`/`seaborn` y componentes `Plotly` cuando eso mejore claridad o exploración.
- **D-15:** El HTML diario incluye obligatoriamente resumen ejecutivo, pronósticos del bloque próximo, probabilidades del torneo, evolución temporal y una nota metodológica corta. La sección detallada de grupos queda opcional según la jornada.
- **D-16:** La parte superior del HTML diario usa un resumen mixto: KPIs clave y un primer bloque visual combinando próximos partidos y probabilidades destacadas del torneo.
- **D-17:** La evolución temporal compara cada snapshot tanto contra el snapshot inmediatamente anterior como contra el primer snapshot publicado del proyecto.
- **D-18:** El tracker de calibración en vivo guarda datos canónicos por partido; las vistas por jornada son agregaciones derivadas para visualización.
- **D-19:** El benchmark de mercado es un agregado canónico de múltiples bookmakers válidos, no una casa fija ni una selección oportunista.
- **D-20:** La referencia principal del benchmark usa la mediana de probabilidades de-margined entre bookmakers válidos; el promedio simple se conserva como diagnóstico auxiliar.
- **D-21:** Para evaluación y comparación en vivo, el benchmark principal se congela con la cuota capturada al momento de publicar el snapshot oficial, no con una captura posterior.
- **D-22:** El reporte diario muestra métricas acumuladas de calibración y una serie temporal de evolución; no se limita a un agregado por jornada sin detalle base.

### the agent's Discretion
- Elegir el layout exacto de carpetas y nombres de archivos dentro de cada snapshot, siempre que preserve append-only, separación entre metadata y tablas, y lectura clara por humanos y scripts.
- Elegir el balance exacto entre visuales `matplotlib`/`seaborn` y `Plotly` dentro del HTML, siempre que el resultado final siga siendo estático, publicable y reproducible.
- Elegir qué elementos de grupos incluir dinámicamente según la relevancia competitiva de la jornada, sin convertir esa sección en obligatoria para todas las corridas.

### Deferred Ideas (OUT OF SCOPE)
- Publish after every single match instead of by jornada or relevant match block - deferred because it increases operational noise and snapshot churn beyond the Phase 4 requirement.
- Full interactive dashboard product surface - deferred; the report output for this phase is static HTML, not a persistent app.
- Making incremental model refresh the authoritative publication path - deferred; official runs stay rebuild/re-fit based.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-06 | Existe un pipeline de ingesta de resultados del torneo en curso con fallback manual editable (`results_2026.csv`) para que un scraper roto nunca bloquee la corrida diaria | Minimal CSV contract, fixture-backed validation, and fail-closed completeness gate. [VERIFIED: .planning/REQUIREMENTS.md, src/cdd_mundial/simulation/state.py, tests/test_tournament_state.py] |
| LIVE-01 | El pipeline de jornada corre con un comando: ingesta de resultados -> actualización Elo/forma -> re-simulación -> reporte generado | One-command orchestration should call explicit stage functions under `src/` with the repo-local interpreter. [VERIFIED: .planning/REQUIREMENTS.md, src/cdd_mundial/models/validation.py, README.md, local command checks 2026-06-13] |
| LIVE-02 | Cada pronóstico se persiste como snapshot append-only con timestamp y `model_version`, commiteado a git ANTES del kickoff | Snapshot folder contract, git-clean gate, metadata schema, and append-only write discipline. [VERIFIED: .planning/REQUIREMENTS.md, .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/provenance.py, git status --porcelain=v1 2026-06-13] |
| LIVE-03 | Cada jornada genera un reporte estático con matplotlib/seaborn: tabla de avance, barras P(Campeón), distribución de posiciones por grupo, evolución de probabilidades en el tiempo | Static HTML should be rendered from frozen snapshot artifacts using Jinja2 plus PNG assets written by Matplotlib/Seaborn; Plotly is optional only. [VERIFIED: .planning/REQUIREMENTS.md, local package inventory 2026-06-13, https://jinja.palletsprojects.com/en/stable/templates/, https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html, https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html] |
| LIVE-04 | El sistema trackea calibración en vivo: log-loss/RPS acumulado del modelo vs. benchmark de mercado de-margined sobre los partidos ya jugados | Canonical per-match ledger should join frozen snapshot probabilities, frozen market median benchmark, and realized outcome. [VERIFIED: .planning/REQUIREMENTS.md, src/cdd_mundial/data/ingest_odds.py, src/cdd_mundial/models/validation.py, tests/test_odds.py] |
| DOC-02 | Todo pronóstico publicado es reproducible: seeds fijas en simulación, raw inmutable, datos procesados con metadatos de extracción, artefactos de modelo versionados por fecha | Existing provenance, deterministic CRN, and dated model artifacts are already in place and must be extended into snapshot metadata instead of replaced. [VERIFIED: .planning/REQUIREMENTS.md, src/cdd_mundial/data/provenance.py, src/cdd_mundial/models/validation.py, src/cdd_mundial/simulation/engine.py, tests/test_simulation_engine.py, tests/test_provenance.py] |
</phase_requirements>

## Summary

Phase 4 should be planned as a thin publication layer on top of already-working contracts, not as a redesign of modeling or simulation. The codebase already has the three hardest primitives: `TournamentState.from_results(...)` for fail-loud conditioned state building, `predict_lambdas(...)` for the frozen model contract, and `simulate_tournaments(...)` for deterministic CRN-preserving re-simulation of only unresolved matches. [VERIFIED: src/cdd_mundial/simulation/state.py, src/cdd_mundial/models/dixon_coles.py, src/cdd_mundial/simulation/engine.py, tests/test_tournament_state.py, tests/test_simulation_engine.py]

The missing work is orchestration and publication discipline: define the canonical live-results CSV, refresh the official model from canonical artifacts plus observed state, freeze a rich append-only snapshot folder, derive a static HTML report strictly from snapshot files, and persist a per-match calibration ledger against a frozen multi-bookmaker benchmark captured at publication time. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, .planning/ROADMAP.md, src/cdd_mundial/data/ingest_odds.py, src/cdd_mundial/models/validation.py]

The lowest-friction reporting stack in the current workspace is Jinja2 plus pandas HTML tables plus Matplotlib/Seaborn PNG assets, because Jinja2 is installed locally, `plotly` is not installed, and the report only needs static publication rather than a long-lived app surface. Plotly can remain an optional enhancement behind an explicit dependency gate, not the baseline Phase 4 path. [VERIFIED: local package inventory 2026-06-13, https://jinja.palletsprojects.com/en/stable/templates/, https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html, https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html, https://plotly.com/python-api-reference/generated/plotly.io.write_html.html]

**Primary recommendation:** Plan Phase 4 as five implementation tracks in order: results ingestion contract -> official run orchestrator -> immutable snapshot writer -> snapshot-only HTML renderer -> live calibration ledger and report sections. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/simulation/state.py, src/cdd_mundial/simulation/engine.py, src/cdd_mundial/data/ingest_odds.py]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live results ingestion from `results_2026.csv` | API / Backend | Database / Storage | The CSV is authoritative input, but validation and normalization must happen in Python against the frozen fixture and canonical identities. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/simulation/state.py] |
| Official model refresh and conditioned simulation | API / Backend | Database / Storage | Re-fit/materialization and tournament simulation are pure backend compute over local artifacts. [VERIFIED: src/cdd_mundial/models/validation.py, src/cdd_mundial/simulation/engine.py] |
| Append-only snapshot persistence | Database / Storage | API / Backend | The durable product of each run is a folder of canonical files plus metadata, and backend code only writes it. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/provenance.py] |
| Static HTML report generation | API / Backend | CDN / Static | The report is rendered offline from snapshot files, then served as a static artifact. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, https://jinja.palletsprojects.com/en/stable/templates/, https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html] |
| Historical snapshot comparison and evolution charts | API / Backend | Database / Storage | The renderer must read the current snapshot plus previous snapshot tables and compute diffs/time series offline. [VERIFIED: D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |
| Market benchmark freeze and live calibration ledger | Database / Storage | API / Backend | The benchmark should be stored canonically per match and joined later for metrics and plots. [VERIFIED: D-18..D-21 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/ingest_odds.py] |
| Notebook trigger / operator UX | Browser / Client | API / Backend | The notebook is only a convenience entrypoint over the official script, not the source of truth. [VERIFIED: D-07 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, notebooks/03_simulador_torneo.ipynb reference in context] |

## Project Constraints (from CLAUDE.md)

- Production logic must live in `src/`; notebooks may orchestrate or explain but must not define the official behavior. [VERIFIED: CLAUDE.md]
- `data/raw/` remains immutable, and all transformed outputs must be new artifacts with metadata. [VERIFIED: CLAUDE.md]
- Reproducibility is a hard constraint: fixed seeds for report simulations and regeneration from raw plus versioned code. [VERIFIED: CLAUDE.md]
- The baseline must publish before 2026-06-27, so Phase 4 should choose the smallest architecture that satisfies official publication and auditability. [VERIFIED: CLAUDE.md, .planning/ROADMAP.md]
- Public outputs must not leak secrets or restricted raw odds payloads. [VERIFIED: CLAUDE.md, README.md, data/metadata/odds_provider_policy.json]
- The repo-local Windows runtime is `.\.venv\python.exe`, so plans should use explicit interpreter commands rather than plain `python`. [VERIFIED: local command checks 2026-06-13]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.13 | Official run CLI, snapshot writer, renderer, tests | This exact repo-local interpreter works today and already carries the scientific stack. [VERIFIED: local package inventory 2026-06-13] |
| pandas | 2.3.3 | Canonical tables, joins, snapshot parquet/CSV IO, HTML tables | Existing processed artifacts and contracts already use pandas, and `DataFrame.to_html` provides a direct static table path. [VERIFIED: pyproject.toml, local package inventory 2026-06-13, https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html] |
| pyarrow | 24.0.0 | Snapshot parquet serialization | The project already persists canonical data products as parquet through pandas/pyarrow. [VERIFIED: pyproject.toml, local package inventory 2026-06-13] |
| pandera | 0.31.1 | New Phase 4 schemas for results rows, snapshot tables, and calibration ledger | Existing data products already fail loud through `DataFrameModel` contracts; Phase 4 should extend that pattern instead of bypassing it. [VERIFIED: src/cdd_mundial/data/contracts.py, local package inventory 2026-06-13] |
| scikit-learn | 1.9.0 | `log_loss` for live calibration vs market | The project already uses sklearn metrics, and `log_loss` is the official metric implementation documented in stable docs. [VERIFIED: src/cdd_mundial/models/validation.py, local package inventory 2026-06-13, https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html] |
| matplotlib | 3.11.0 | Static chart assets for the HTML report | `savefig` writes deterministic static image files, matching the report publication shape. [VERIFIED: local package inventory 2026-06-13, https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html] |
| seaborn | 0.13.2 | Higher-level statistical plots for evolution/calibration charts | Already pinned in the project and sufficient for the required static visuals. [VERIFIED: pyproject.toml, local package inventory 2026-06-13] |
| Jinja2 | 3.1.6 | Static HTML templating for the report | Jinja templates generate text-based formats and support template inheritance, which is the cleanest way to separate base layout from day-specific sections. [VERIFIED: local package inventory 2026-06-13, https://jinja.palletsprojects.com/en/stable/templates/] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| existing `cdd_mundial.simulation` package | local source | Build conditioned state and tournament probabilities | Always; Phase 4 should orchestrate these APIs, not duplicate their logic. [VERIFIED: src/cdd_mundial/simulation/__init__.py] |
| existing `cdd_mundial.models.validation` flow | local source | Re-fit and materialize official DC artifacts with dated outputs and provenance precedent | Use for the official rebuild-based publication path. [VERIFIED: src/cdd_mundial/models/validation.py] |
| existing `cdd_mundial.data.ingest_odds` flow | local source | Manual and provider-backed benchmark construction with de-margining and fixture matching | Use for benchmark refresh/freeze and never invent a second odds format. [VERIFIED: src/cdd_mundial/data/ingest_odds.py, tests/test_odds.py] |
| joblib | 1.5.3 | Optional caching for expensive derived report objects, not canonical publication artifacts | Use only for temporary local acceleration, never as the published canonical artifact. [VERIFIED: local package inventory 2026-06-13] |
| Plotly | not installed locally | Optional interactive sections inside a static HTML artifact | Use only if explicitly added and only after the baseline static renderer is working. [VERIFIED: local package inventory 2026-06-13, https://plotly.com/python-api-reference/generated/plotly.io.write_html.html] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Jinja2 + pandas + Matplotlib static HTML | Plotly-first self-contained HTML | Plotly can improve exploration, but it is not installed locally and would add dependency and bundling decisions before the first publishable run. [VERIFIED: local package inventory 2026-06-13, https://plotly.com/python-api-reference/generated/plotly.io.write_html.html] |
| Rebuild-based official run | Incremental mutable cache as the official path | Faster locally, but it weakens reproducibility and conflicts with D-06 for official publication. [VERIFIED: D-06 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |
| Canonical per-match calibration ledger | Only jornada-level aggregates | Aggregates are easier to render, but D-18 requires canonical per-match storage and would block later honest recalculation. [VERIFIED: D-18 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |

**Installation:**
```bash
.\.venv\python.exe -m pip install -e ".[dev]"
.\.venv\python.exe -m pip install "Jinja2~=3.1"
```
[VERIFIED: pyproject.toml, local package inventory 2026-06-13]

**Version verification:** The current workspace has `pandas 2.3.3`, `numpy 2.4.6`, `pyarrow 24.0.0`, `pandera 0.31.1`, `scikit-learn 1.9.0`, `matplotlib 3.11.0`, `seaborn 0.13.2`, `Jinja2 3.1.6`, and `pytest 8.4.2` installed in `.\.venv\python.exe`. [VERIFIED: local package inventory 2026-06-13]

## Architecture Patterns

### System Architecture Diagram

```text
results_2026.csv (canonical live results)
        |
        v
validate rows against fixture + team identities
        |
        +--> optional scraper/aux validation -> mismatch? -> FAIL CLOSED
        |
        v
TournamentState.from_results(...)
        |
        v
official model refresh
  historical_matches.parquet
  + dated dc_params_*.json
  + current observed state
        |
        v
simulate_tournaments(fixture, state, predict_lambdas, seed)
        |
        +--> advancement_table(...)
        +--> group_position_table(...)
        +--> upcoming match probability table
        +--> frozen market benchmark for next block
        +--> live calibration ledger update
        |
        v
append-only snapshot folder
  metadata.json
  team_probabilities.parquet
  group_positions.parquet
  upcoming_predictions.parquet
  calibration_matches.parquet
  market_benchmark_frozen.parquet
  report assets/
        |
        v
Jinja2 renderer reads snapshot only
        |
        v
static report.html
```
[VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/simulation/state.py, src/cdd_mundial/simulation/engine.py, src/cdd_mundial/simulation/outputs.py, src/cdd_mundial/data/ingest_odds.py, src/cdd_mundial/models/validation.py]

### Recommended Project Structure

```text
src/cdd_mundial/live/
├── contracts.py        # Phase 4 pandera schemas for live results, snapshots, calibration
├── results.py          # load/validate results_2026.csv -> TournamentState
├── refresh.py          # official rebuild-based model refresh/materialization
├── predict.py          # upcoming match table + snapshot assembly
├── benchmark.py        # frozen market median/mean benchmark assembly
├── calibration.py      # per-match ledger + cumulative metrics
├── snapshots.py        # append-only folder writer + metadata.json + git gate
├── report.py           # Jinja2 HTML rendering from snapshot artifacts only
└── pipeline.py         # one-command orchestration entrypoint

templates/
├── report_base.html.jinja
└── report_daily.html.jinja

data/external/
└── results_2026.csv    # canonical manual/live results input

reports/
└── snapshots/
    └── 2026-06-14T17-00-00Z_baseline-v1-2026-06-14-abc1234/
```
[VERIFIED: repo layout conventions in src/cdd_mundial/data, src/cdd_mundial/simulation, src/cdd_mundial/models, plus D-09 and D-12 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

### Pattern 1: Minimal canonical results CSV feeding `TournamentState`
**What:** Define `data/external/results_2026.csv` as the only authoritative live-results input, with just the fields needed to construct `PlayedMatchResult` rows plus stage-specific optional columns. [VERIFIED: D-01 and D-03 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/simulation/state.py]

**When to use:** Every official and exploratory run that conditions on played matches. [VERIFIED: D-02 and D-07 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Recommended CSV columns:** `match_id,team_a,team_b,goals_a,goals_b,fair_play_a,fair_play_b,advanced_team`. This is exactly the accepted contract surface of `PlayedMatchResult`, and unknown keys already fail loudly in the JSON helper, so a CSV loader should mirror that strictness. [VERIFIED: src/cdd_mundial/simulation/state.py, tests/test_tournament_state.py]

**Example:**
```python
from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.simulation.state import PlayedMatchResult, TournamentState

fixture = load_fixture_2026()
records = [
    PlayedMatchResult(
        match_id="WC26-001",
        team_a="mexico",
        team_b="south-africa",
        goals_a=2,
        goals_b=1,
    )
]
state = TournamentState.from_results(records, fixture=fixture)
```
Source: `src/cdd_mundial/simulation/state.py`. [VERIFIED: src/cdd_mundial/simulation/state.py]

### Pattern 2: Official publication run is rebuild-based and explicit
**What:** The official path should re-run model materialization from canonical processed artifacts and then run conditioned simulation with a fixed publication seed, while any faster incremental path remains a separate non-official mode. [VERIFIED: D-06 and D-07 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/models/validation.py]

**When to use:** Every snapshot that will be committed as the official public forecast. [VERIFIED: D-02, D-06, D-12 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Implementation implication:** Do not call `predict_lambdas(...)` blindly against whichever `dc_params_*.json` happens to be latest on disk without first controlling how that file was produced for the run. The orchestration layer should either materialize a fresh dated model artifact or explicitly pin an existing one and record its checksum/path in `metadata.json`. [VERIFIED: src/cdd_mundial/models/dixon_coles.py, src/cdd_mundial/models/validation.py]

### Pattern 3: Snapshot folder is the only canonical publication boundary
**What:** The official run should write all publishable canonical outputs to a new timestamped folder and then render the report from that folder only. [VERIFIED: D-08, D-09, D-12 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**When to use:** Every official publication and every dry-run intended for audit or later comparison. [VERIFIED: D-02 and D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Required snapshot files:** `metadata.json`, `team_probabilities.parquet`, `group_positions.parquet`, `upcoming_predictions.parquet`, `market_benchmark_frozen.parquet`, `calibration_matches.parquet`, and `report.html` for official runs. [VERIFIED: D-08, D-09, D-12, D-15, D-17, D-18..D-22 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Required metadata fields:** `snapshot_timestamp_utc`, `publication_mode`, `model_version`, `code_commit`, `dirty`, `dirty_files`, `seed`, `fixture_sha256`, `results_sha256`, `dc_params_path`, `dc_params_sha256`, `odds_capture_timestamp_utc`, `benchmark_aggregation`, and `next_block_cutoff_utc`. The exact field names are discretionary, but the information is not. [VERIFIED: D-10, D-11, D-13, D-21 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/provenance.py]

### Pattern 4: Report renderer consumes snapshot artifacts only
**What:** The HTML generator should take a snapshot directory path as input and never refit models, fetch provider data, or rerun simulation internally. [VERIFIED: D-12 and the "HTML report should consume the snapshot artifacts" guidance in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**When to use:** Every report generation, including re-renders of historical snapshots. [VERIFIED: D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Why:** This removes hindsight drift between canonical data and rendered narrative, makes `report.html` reproducible, and allows backfills or cosmetic rerenders without touching forecast probabilities. [VERIFIED: D-12 and D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Example:**
```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("report_daily.html.jinja")
html = template.render(summary=summary, tables=tables, charts=charts)
```
Source: Jinja templates generate text-based formats and support inheritance for a base skeleton plus child sections. [CITED: https://jinja.palletsprojects.com/en/stable/templates/]

### Pattern 5: Freeze market benchmark per snapshot, then append canonical calibration rows
**What:** For each official publication, compute a canonical benchmark table for the upcoming block using the median of valid de-margined bookmaker probabilities as the primary reference and store mean as auxiliary diagnostics. After matches are played, append per-match realized rows to a cumulative calibration ledger. [VERIFIED: D-19, D-20, D-21, D-22 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/ingest_odds.py]

**When to use:** Every official publication, plus later replay when a snapshot transitions from "future benchmark rows" to "realized calibration rows". [VERIFIED: D-21 and D-22 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

**Implementation implication:** `data/processed/odds_2026.parquet` is currently a quote-level artifact with one row per bookmaker quote, so Phase 4 needs a derived aggregation step rather than mutating that canonical source file. [VERIFIED: data/processed/odds_2026.parquet inspected 2026-06-13, src/cdd_mundial/data/ingest_odds.py]

### Recommended Implementation Sequence

1. Add Phase 4 contracts and CSV loader for `results_2026.csv`, including fail-closed checks for missing played matches and optional override metadata capture. [VERIFIED: D-01..D-05 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
2. Build the official refresh/orchestration path that materializes or pins the exact DC artifact, constructs `TournamentState`, and runs conditioned simulation with a fixed publication seed. [VERIFIED: src/cdd_mundial/models/validation.py, src/cdd_mundial/simulation/engine.py]
3. Add snapshot writer and metadata schema, including git cleanliness checks and dirty override recording. [VERIFIED: D-10..D-13 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, git status --porcelain=v1 2026-06-13]
4. Add the benchmark aggregation/freeze layer and per-match calibration ledger before report rendering, so the snapshot contains the full publication truth. [VERIFIED: D-18..D-22 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/ingest_odds.py]
5. Add Jinja2 report templates and chart generation that read only snapshot files. [VERIFIED: D-14..D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, https://jinja.palletsprojects.com/en/stable/templates/, https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html]
6. Add the one-command CLI plus a notebook wrapper that shells out to or imports the same orchestrator. [VERIFIED: D-07 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

### Anti-Patterns to Avoid
- **Recomputing the report from live state instead of snapshot files:** This breaks auditability and makes `report.html` a moving target. [VERIFIED: D-12 and D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
- **Letting a scraper overwrite or outrank `results_2026.csv`:** This directly violates D-01 and D-04. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
- **Using the current latest odds quotes for past evaluation:** This introduces hindsight leakage and violates D-21. [VERIFIED: .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
- **Treating transitive `jinja2` installation as good enough forever:** The package is present locally but not declared in `pyproject.toml`, so Phase 4 should add it explicitly if the renderer depends on it. [VERIFIED: pyproject.toml, local package inventory 2026-06-13]
- **Assuming `python` is the correct command in this workspace:** The shell-level `python` entry point fails here while `.\.venv\python.exe` works. [VERIFIED: local command checks 2026-06-13]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML templating | String concatenation of full HTML pages | Jinja2 templates | Jinja already supports text generation and inheritance, which keeps the report maintainable and diffable. [CITED: https://jinja.palletsprojects.com/en/stable/templates/] |
| HTML tables | Manual `<table>` assembly for pandas outputs | `DataFrame.to_html(...)` with CSS classes | pandas already renders DataFrames to HTML and returns a string when `buf=None`. [CITED: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html] |
| Static chart file writing | Custom image encoders | `matplotlib.pyplot.savefig(...)` | Matplotlib already writes image or vector outputs to files. [CITED: https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html] |
| Market quote parsing and de-margining | A new odds ingestion path | Existing `build_odds_benchmark(...)` and its semantics | The code already enforces three-way market shape, staleness, fixture matching, and de-margining. [VERIFIED: src/cdd_mundial/data/ingest_odds.py, tests/test_odds.py] |
| Conditioned tournament state logic | Ad hoc dicts or cached standings | `PlayedMatchResult` + `TournamentState.from_results(...)` | The state contract already encodes the right invariants and fail-loud behavior. [VERIFIED: src/cdd_mundial/simulation/state.py, tests/test_tournament_state.py] |
| Log-loss implementation | Custom cross-entropy math in production code | `sklearn.metrics.log_loss` | The project already depends on sklearn and uses it in model validation. [VERIFIED: src/cdd_mundial/models/validation.py, https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html] |

**Key insight:** Phase 4 is mostly about joining existing verified primitives with publication discipline; the danger is not missing algorithms, it is duplicating logic outside the current contracts and silently creating two truths. [VERIFIED: src/cdd_mundial/simulation/state.py, src/cdd_mundial/simulation/engine.py, src/cdd_mundial/data/ingest_odds.py, src/cdd_mundial/models/validation.py]

## Common Pitfalls

### Pitfall 1: Freezing the report but not the model artifact
**What goes wrong:** A snapshot folder records probabilities but not the exact DC parameters used, so later reruns may silently use a different `dc_params_*.json`. [VERIFIED: src/cdd_mundial/models/dixon_coles.py, src/cdd_mundial/models/validation.py]
**Why it happens:** `predict_lambdas(...)` loads the latest params file by date unless the orchestration layer pins or materializes one intentionally. [VERIFIED: src/cdd_mundial/models/dixon_coles.py]
**How to avoid:** Record the model artifact path and checksum in `metadata.json`, and prefer materializing a dated artifact inside the official run before simulation. [VERIFIED: src/cdd_mundial/models/validation.py, src/cdd_mundial/data/provenance.py]
**Warning signs:** Re-rendering an old snapshot produces different upcoming probabilities without any change to the snapshot files. [VERIFIED: reasoning from current loading behavior in src/cdd_mundial/models/dixon_coles.py]

### Pitfall 2: Benchmark hindsight leakage
**What goes wrong:** Live evaluation looks better or worse than reality because it compares realized outcomes to quotes captured after kickoff or after line movement. [VERIFIED: D-21 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
**Why it happens:** The current odds parquet stores quote-level captures, but there is not yet a publication-time freeze layer. [VERIFIED: data/processed/odds_2026.parquet inspected 2026-06-13]
**How to avoid:** Write a per-snapshot frozen benchmark artifact and append its rows into the calibration ledger with the snapshot timestamp. [VERIFIED: D-18..D-21 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
**Warning signs:** The calibration code reads "latest odds" instead of a snapshot-local benchmark file. [VERIFIED: negative implication from current absence of Phase 4 code]

### Pitfall 3: Breaking CRN by bypassing the engine contract
**What goes wrong:** Daily state updates cause unrelated future-match probabilities to jump from RNG drift rather than new information. [VERIFIED: src/cdd_mundial/simulation/engine.py, tests/test_simulation_engine.py]
**Why it happens:** A planner may be tempted to prefilter unresolved matches and sample them outside `simulate_tournaments(...)`, which would bypass the stable `match_id` stream mapping. [VERIFIED: src/cdd_mundial/simulation/engine.py]
**How to avoid:** Always pass the full canonical fixture plus `TournamentState` into `simulate_tournaments(...)` and let the engine overlay played matches internally. [VERIFIED: src/cdd_mundial/simulation/engine.py]
**Warning signs:** New code constructs a reduced future-only fixture before simulation. [VERIFIED: engine contract in src/cdd_mundial/simulation/engine.py]

### Pitfall 4: Dirty worktree publication without explicit trace
**What goes wrong:** An official forecast cannot be audited because the repo state differs from the recorded commit or includes unrecorded notebook edits. [VERIFIED: D-10 and D-11 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
**Why it happens:** The current workspace is already dirty, so this is not hypothetical. [VERIFIED: git status --porcelain=v1 2026-06-13]
**How to avoid:** Make the default publication path fail if `git status --porcelain` is non-empty, unless a `--allow-dirty` flag is passed and the dirty file list is copied into metadata. [VERIFIED: D-11 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
**Warning signs:** Snapshot metadata only records a commit hash and omits `dirty` state or modified files. [VERIFIED: D-11 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

### Pitfall 5: Report templates depending on undeclared transitive packages
**What goes wrong:** The renderer works on one machine because Jinja2 came from Jupyter, but breaks in a fresh clone or CI. [VERIFIED: pyproject.toml, local package inventory 2026-06-13]
**Why it happens:** `jinja2` is installed locally but absent from direct project dependencies. [VERIFIED: pyproject.toml, local package inventory 2026-06-13]
**How to avoid:** Add `Jinja2` as a direct dependency if the baseline report renderer uses it. [VERIFIED: pyproject.toml]
**Warning signs:** `ImportError: No module named jinja2` on a clean environment despite local success on the maintainer machine. [VERIFIED: dependency mismatch risk from current environment]

## Code Examples

Verified patterns from official sources and the current codebase:

### Conditioned simulation from a validated state
```python
from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.models import predict_lambdas
from cdd_mundial.simulation import TournamentState, simulate_tournaments

fixture = load_fixture_2026()
state = TournamentState(played={})
result = simulate_tournaments(
    fixture=fixture,
    state=state,
    predict_lambdas=predict_lambdas,
    n_sims=10000,
    seed=20260614,
)
```
Source: `src/cdd_mundial/simulation/engine.py`, `src/cdd_mundial/simulation/state.py`. [VERIFIED: src/cdd_mundial/simulation/engine.py, src/cdd_mundial/simulation/state.py]

### Rendering a DataFrame to HTML
```python
html_table = dataframe.to_html(index=False, classes=["table", "table-sm"])
```
Source: `DataFrame.to_html` renders a DataFrame as an HTML table and returns a string when `buf=None`. [CITED: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html]

### Writing static figure assets
```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot(x, y)
fig.savefig(output_path, dpi=150, bbox_inches="tight")
```
Source: `savefig` writes the current figure to an image or vector file. [CITED: https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html]

### Optional offline Plotly section
```python
import plotly.io as pio

pio.write_html(fig, file=output_path, include_plotlyjs="directory", full_html=False)
```
Source: `write_html` can write a figure to HTML and `include_plotlyjs="directory"` keeps files offline-capable with a shared local bundle. [CITED: https://plotly.com/python-api-reference/generated/plotly.io.write_html.html]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mutable notebooks as the publication path | Scripted orchestration plus notebooks as interface only | Locked in Phase 4 context on 2026-06-13 | Prevents silent notebook drift from becoming the official process. [VERIFIED: D-07 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |
| Report-generation logic coupled to live recomputation | Snapshot-first rendering | Locked in Phase 4 context on 2026-06-13 | Makes public artifacts replayable and comparable over time. [VERIFIED: D-12 and D-17 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |
| Single-bookmaker or ad hoc odds comparison | Multi-bookmaker de-margined median benchmark with mean as diagnostic | Locked in Phase 4 context on 2026-06-13 | Reduces noise and benchmark opportunism. [VERIFIED: D-19 and D-20 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |

**Deprecated/outdated:**
- Using the current latest quote as the evaluation benchmark for already-published forecasts is outdated for this project because Phase 4 explicitly freezes benchmark odds at snapshot time. [VERIFIED: D-21 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
- Treating static matplotlib-only output as a project-wide hard constraint is outdated for this phase because Phase 4 explicitly allows optional Plotly inside static HTML. [VERIFIED: D-14 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `results_2026.csv` should live under `data/external/` rather than another versioned path. [ASSUMED] | Architecture Patterns | Low; planner can relocate the file without changing the contract if the team prefers another versioned directory. |
| A2 | The official refresh path should materialize a new dated `dc_params_*.json` for each publication rather than reusing the last dated artifact when underlying canonical training data has not changed. [ASSUMED] | Pattern 2 / metadata design | Medium; affects runtime cost and artifact churn, but not the high-level architecture. |

## Open Questions (RESOLVED)

1. **Resolved: official refit-vs-reuse authority**
   - Locked resolution: the official pipeline computes a deterministic fingerprint of canonical training inputs and selected model settings. It reuses a pinned dated production model artifact when the fingerprint is unchanged; it refits/materializes a new dated artifact only when the fingerprint changes. [VERIFIED: revision instructions 2026-06-13, D-06 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
   - Snapshot consequence: every official snapshot records the model artifact path, artifact SHA-256, input fingerprint, `model_version`, and whether the publication reused or refit the artifact. [VERIFIED: revision instructions 2026-06-13, D-08, D-10, D-13 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
   - Planning implication: the publication flow should fingerprint before model selection, then carry the resolved provenance into the immutable snapshot metadata instead of inferring it later. [VERIFIED: revision instructions 2026-06-13]

2. **Resolved: calibration-ledger authority and snapshot slices**
   - Locked resolution: the single authoritative calibration source is a top-level append-only per-match ledger. Each snapshot contains immutable frozen prediction and market-benchmark slices plus the checksums and row IDs used by that publication. Reports read the snapshot-local slices plus the authoritative ledger for cumulative history; no duplicate mutable ledger exists. [VERIFIED: revision instructions 2026-06-13, D-18, D-21, D-22 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md]
   - Snapshot consequence: benchmark freeze must occur before metadata finalization so the snapshot can publish one complete immutable bundle whose metadata already names the frozen slice row IDs/checksums and the ledger rows appended from that publication. [VERIFIED: revision instructions 2026-06-13]
   - Planning implication: calibration contracts must precede the renderer so report code consumes fixed snapshot-local benchmark/prediction slices plus the authoritative ledger for cumulative log-loss/RPS and time-series evolution. [VERIFIED: revision instructions 2026-06-13]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.\.venv\python.exe` | Official pipeline, tests, report rendering | ✓ | 3.12.13 | None needed. [VERIFIED: local command checks 2026-06-13] |
| `pytest` via `.\.venv\python.exe -m pytest` | Validation architecture | ✓ | 8.4.2 | None needed. [VERIFIED: local package inventory 2026-06-13] |
| `git` | Clean-worktree gate and snapshot provenance | ✓ | 2.53.0.windows.1 | None needed. [VERIFIED: `git --version` 2026-06-13] |
| `Jinja2` | Baseline static HTML renderer | ✓ | 3.1.6 | Could fall back to plain string templates, but that is not recommended. [VERIFIED: local package inventory 2026-06-13] |
| `plotly` | Optional interactive report sections | ✗ | - | Omit Plotly and ship the Matplotlib/Jinja baseline. [VERIFIED: local package inventory 2026-06-13] |
| `ODDS_API_KEY` | Live provider refresh for benchmark freeze | ✗ | - | Use manual benchmark input and existing quote-level parquet until the key is configured. [VERIFIED: environment check 2026-06-13, src/cdd_mundial/data/ingest_odds.py] |

**Missing dependencies with no fallback:**
- None for the baseline publication path. The absence of `ODDS_API_KEY` blocks live provider refresh, not the manual fallback or report generation. [VERIFIED: D-01..D-05 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md, src/cdd_mundial/data/ingest_odds.py]

**Missing dependencies with fallback:**
- `plotly` is absent locally, so the baseline plan should not depend on it. [VERIFIED: local package inventory 2026-06-13]
- `ODDS_API_KEY` is missing, so the planner must preserve a manual benchmark-capture route and not require authenticated provider access for the first official publication. [VERIFIED: environment check 2026-06-13, data/external/odds_2026_template.csv, src/cdd_mundial/data/ingest_odds.py]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest 8.4.2` via repo-local interpreter. [VERIFIED: local package inventory 2026-06-13] |
| Config file | `pyproject.toml` under `[tool.pytest.ini_options]`. [VERIFIED: pyproject.toml] |
| Quick run command | `.\.venv\python.exe -m pytest -q tests/test_tournament_state.py tests/test_simulation_engine.py tests/test_odds.py` [VERIFIED: local test runs 2026-06-13] |
| Full suite command | `.\.venv\python.exe -m pytest -q` [VERIFIED: README.md, pyproject.toml] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-06 | Canonical `results_2026.csv` rows validate against fixture and completeness rules | unit | `.\.venv\python.exe -m pytest -q tests/test_live_results.py -x` | ❌ Wave 0 |
| LIVE-01 | One command runs refresh -> simulation -> snapshot -> report | integration | `.\.venv\python.exe -m pytest -q tests/test_live_pipeline.py -x` | ❌ Wave 0 |
| LIVE-02 | Snapshot writer is append-only, metadata-rich, and git-gated | unit + integration | `.\.venv\python.exe -m pytest -q tests/test_live_snapshots.py -x` | ❌ Wave 0 |
| LIVE-03 | HTML report reads snapshot artifacts only and emits required sections | unit + golden-file | `.\.venv\python.exe -m pytest -q tests/test_live_report.py -x` | ❌ Wave 0 |
| LIVE-04 | Calibration ledger uses frozen benchmark rows and computes cumulative log-loss/RPS correctly | unit | `.\.venv\python.exe -m pytest -q tests/test_live_calibration.py -x` | ❌ Wave 0 |
| DOC-02 | Published snapshot is reproducible from versioned inputs, fixed seed, and recorded artifacts | integration | `.\.venv\python.exe -m pytest -q tests/test_live_reproducibility.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.\.venv\python.exe -m pytest -q tests/test_tournament_state.py tests/test_simulation_engine.py tests/test_odds.py` [VERIFIED: local test runs 2026-06-13]
- **Per wave merge:** `.\.venv\python.exe -m pytest -q tests/test_validation_temporal.py tests/test_simulation_outputs.py tests/test_provenance.py` [VERIFIED: local test runs plus existing suite topology 2026-06-13]
- **Phase gate:** Full suite green before `$gsd-verify-work`. [VERIFIED: .planning/config.json]

### Wave 0 Gaps

- [ ] `tests/test_live_results.py` - covers DATA-06 CSV contract, fixture conflicts, incomplete-played-match failure, and override trace. [VERIFIED: gap against current `tests/` tree 2026-06-13]
- [ ] `tests/test_live_snapshots.py` - covers append-only writes, metadata completeness, and dirty worktree gate behavior. [VERIFIED: gap against current `tests/` tree 2026-06-13]
- [ ] `tests/test_live_report.py` - covers snapshot-only rendering and required report sections. [VERIFIED: gap against current `tests/` tree 2026-06-13]
- [ ] `tests/test_live_calibration.py` - covers market median aggregation, mean diagnostic, and cumulative metric math. [VERIFIED: gap against current `tests/` tree 2026-06-13]
- [ ] `tests/test_live_pipeline.py` - covers the one-command official run over fixtures with stubbed/model-pinned inputs. [VERIFIED: gap against current `tests/` tree 2026-06-13]
- [ ] `tests/test_live_reproducibility.py` - covers rerun equivalence from the same seed and frozen inputs. [VERIFIED: gap against current `tests/` tree 2026-06-13]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local CLI workflow only; no user auth surface in Phase 4. [VERIFIED: phase scope in .planning/ROADMAP.md] |
| V3 Session Management | no | No server session layer is introduced by the recommended static publication path. [VERIFIED: phase scope in .planning/ROADMAP.md] |
| V4 Access Control | yes | Restrict raw odds payload handling to existing policy paths and publish only derived artifacts. [VERIFIED: README.md, data/metadata/odds_provider_policy.json] |
| V5 Input Validation | yes | Extend pandera contracts plus `TournamentState.from_results(...)` fail-loud checks to Phase 4 inputs. [VERIFIED: src/cdd_mundial/data/contracts.py, src/cdd_mundial/simulation/state.py] |
| V6 Cryptography | yes | Use existing SHA-256 provenance/checksum pattern for snapshot-linked artifacts; do not invent new crypto. [VERIFIED: src/cdd_mundial/data/provenance.py] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Silent mutation of canonical results or snapshot files | Tampering | Append-only folder writes, SHA-256 checksums, and git commit recording. [VERIFIED: src/cdd_mundial/data/provenance.py, D-10..D-12 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |
| Raw odds data accidentally committed | Information Disclosure | Keep raw payloads under the existing ignored raw path and publish only de-margined derivatives. [VERIFIED: README.md, data/metadata/odds_provider_policy.json, src/cdd_mundial/data/ingest_odds.py] |
| HTML injection from unescaped text tables | Tampering / XSS | Keep pandas HTML escaping enabled by default and avoid injecting raw unsafe strings into templates. [CITED: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html] |
| Misattributed publication provenance | Repudiation | Record commit hash, dirty state, artifact checksums, and snapshot timestamp in metadata. [VERIFIED: D-10 and D-11 in .planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/04-primer-pronostico-pipeline-diario/04-CONTEXT.md` - locked decisions, scope, and canonical integration targets. [VERIFIED: repo file]
- `.planning/REQUIREMENTS.md` - Phase 4 requirement surface. [VERIFIED: repo file]
- `.planning/ROADMAP.md` - deadline and success criteria. [VERIFIED: repo file]
- `CLAUDE.md` - project constraints and workflow expectations. [VERIFIED: repo file]
- `src/cdd_mundial/simulation/state.py` - conditioned state contract. [VERIFIED: repo file]
- `src/cdd_mundial/simulation/engine.py` - deterministic CRN-preserving simulation contract. [VERIFIED: repo file]
- `src/cdd_mundial/simulation/outputs.py` - stable marginal output tables. [VERIFIED: repo file]
- `src/cdd_mundial/models/dixon_coles.py` - production model loading and frozen prediction contract. [VERIFIED: repo file]
- `src/cdd_mundial/models/validation.py` - dated artifact materialization and validation precedent. [VERIFIED: repo file]
- `src/cdd_mundial/data/ingest_odds.py` - benchmark semantics, provider constraints, and manual fallback. [VERIFIED: repo file]
- `src/cdd_mundial/data/provenance.py` - checksum and manifest primitives. [VERIFIED: repo file]
- `pyproject.toml` - declared dependencies and pytest config. [VERIFIED: repo file]
- Local environment checks on 2026-06-13 - interpreter path, package versions, `ODDS_API_KEY` presence, git state, and passing test commands. [VERIFIED: shell commands run in session]

### Secondary (MEDIUM confidence)
- https://jinja.palletsprojects.com/en/stable/templates/ - Jinja text-template semantics and inheritance. [CITED: official docs]
- https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html - HTML table rendering contract and default escaping behavior. [CITED: official docs]
- https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html - static figure writing contract. [CITED: official docs]
- https://plotly.com/python-api-reference/generated/plotly.io.write_html.html - optional static/offline HTML export behavior. [CITED: official docs]
- https://scikit-learn.org/stable/modules/generated/sklearn.metrics.log_loss.html - live calibration metric contract. [CITED: official docs]

### Tertiary (LOW confidence)
- None. All recommendations in this document are either repo-verified, environment-verified, or cited to official documentation. [VERIFIED: current research corpus]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all baseline choices are either already installed locally or already used in the codebase; only Plotly remains explicitly optional. [VERIFIED: local package inventory 2026-06-13, pyproject.toml]
- Architecture: MEDIUM - the core contracts are verified, but planning still needs to lock the exact refresh cadence and calibration-ledger placement. [VERIFIED: codebase plus Open Questions]
- Pitfalls: HIGH - each listed failure mode is directly implied by current code behavior or locked Phase 4 decisions. [VERIFIED: repo files and context]

**Research date:** 2026-06-13 [VERIFIED: session date]
**Valid until:** 2026-06-27 for planning this publication phase, because the relevant deadline is the first official pre-kickoff publication before the end of the group stage. [VERIFIED: .planning/ROADMAP.md]
