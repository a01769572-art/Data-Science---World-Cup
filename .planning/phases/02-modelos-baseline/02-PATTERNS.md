# Phase 2: Modelos Baseline (Elo + Dixon-Coles) - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 16 archivos nuevos/modificados
**Analogs found:** 12 / 16 (4 sin análogo: la matemática core es contenido nuevo deliberado — usar Code Examples de RESEARCH.md)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` (mod: deps Wave 0) | config | — | `pyproject.toml` (existente) | exact |
| `src/cdd_mundial/models/__init__.py` | package init | — | `src/cdd_mundial/data/__init__.py` | exact |
| `src/cdd_mundial/models/tournaments.py` | config/clasificador | transform | `src/cdd_mundial/data/identities.py` (registro revisado + fallo ruidoso) | role-match |
| `src/cdd_mundial/models/elo.py` | model/service | batch secuencial | `src/cdd_mundial/data/ingest_martj42.py` (build→validate→parquet→provenance) | role-match |
| `src/cdd_mundial/models/dixon_coles.py` | model/service | batch + request-response (contrato) | `src/cdd_mundial/data/identities.py` (clase + validación de inputs) + `provenance.py` (dataclass) | role-match |
| `src/cdd_mundial/models/baselines.py` | model/utility | transform | funciones puras de RESEARCH.md | no-analog (matemática nueva) |
| `src/cdd_mundial/models/metrics.py` | utility | transform | funciones puras de RESEARCH.md | no-analog (matemática nueva) |
| `src/cdd_mundial/models/validation.py` | evaluation/pipeline | batch | `src/cdd_mundial/data/ingest_martj42.py` (`verify_*` + `materialize_*` + CLI) | role-match |
| `src/cdd_mundial/data/contracts.py` (mod: schemas nuevos) | model/schema | — | `contracts.py` mismo (`EloRatingsSchema`, `HistoricalMatchesSchema`) | exact |
| `data/external/tournament_k_factors.csv` | config/tabla revisada | — | `data/external/teams.csv` | exact |
| `tests/test_elo.py` | test | — | `tests/test_identities.py` + `tests/test_ingest_martj42.py` | exact |
| `tests/test_dixon_coles.py` | test | — | `tests/test_ingest_martj42.py` (fixtures comprometidos) | exact |
| `tests/test_metrics.py` | test | — | `tests/test_identities.py` (valores a mano) | exact |
| `tests/test_validation_temporal.py` | test | — | `tests/test_data01_acceptance.py` (marker `data_acceptance`) + `test_identities.py` | exact |
| `tests/fixtures/models/` (mini-dataset) | test fixture | — | `tests/fixtures/martj42/results.csv` | exact |
| `notebooks/02_modelos_baseline.ipynb` | notebook didáctico | — | `notebooks/01_data_foundation.ipynb` | exact |

**Modificación opcional recomendada:** `tests/test_notebooks.py` — extender el gate `FORBIDDEN_CODE_FRAGMENTS` (hoy solo aplica al notebook 01, líneas 120-129) al notebook 02, según recomendación de RESEARCH.md Pattern 3.

## Pattern Assignments

### `src/cdd_mundial/models/__init__.py` (package init)

**Analog:** `src/cdd_mundial/data/__init__.py` (completo, 2 líneas)

```python
"""Data acquisition, validation, and provenance utilities."""
```

El paquete Phase 1 usa un init con solo docstring. Para `models/` el RESEARCH pide re-exportar las APIs públicas — mantener el docstring de una línea y añadir re-exports explícitos:

```python
"""Baseline structural models: dynamic Elo, Dixon-Coles, metrics, validation."""

from cdd_mundial.models.dixon_coles import DixonColesModel, predict_lambdas  # contrato D-09
```

---

### `src/cdd_mundial/models/tournaments.py` (clasificador torneo → K)

**Analog:** `src/cdd_mundial/data/identities.py` — el patrón "registro revisado a mano + resolución exacta + fallo ruidoso".

**Excepciones custom** (`identities.py` líneas 14-19):
```python
class UnknownTeamError(LookupError):
    """Raised when no reviewed alias resolves a source team name."""


class AmbiguousTeamError(LookupError):
    """Raised when multiple reviewed aliases are valid for one lookup."""
```
Para tournaments.py: definir `UnknownTournamentError(LookupError)` análogo — los 200 strings de torneo DEBEN mapear a una categoría K o fallar (pitfall 3 de RESEARCH).

**Fallo ruidoso en resolución** (`identities.py` líneas 92-101):
```python
def resolve(self, source, source_name, on_date=None) -> str:
    """Return the exact canonical ID or fail loudly."""
    matches = self._matches(source, source_name, on_date)
    if matches.empty:
        suffix = f" on {on_date}" if on_date is not None else ""
        raise UnknownTeamError(f"unknown team alias: {source!r}/{source_name!r}{suffix}")
    if len(matches) > 1:
        raise AmbiguousTeamError(...)
    return str(matches.iloc[0]["team_id"])
```

**Carga de tabla CSV revisada** (`identities.py` líneas 39-65, método `from_csv` con default `Path("data/external/...")`): replicar para `data/external/tournament_k_factors.csv` si se opta por CSV en vez de listas en módulo.

---

### `src/cdd_mundial/models/elo.py` (recomputación secuencial + artefactos)

**Analog:** `src/cdd_mundial/data/ingest_martj42.py` — el patrón build → validate → parquet → provenance.

**Imports del proyecto** (`ingest_martj42.py` líneas 1-22) — orden: docstring, `from __future__`, stdlib, terceros, `cdd_mundial.*`:
```python
"""Acquire martj42 data and build the canonical historical match dataset."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import kagglehub
import pandas as pd

from cdd_mundial.data.contracts import HistoricalMatchesSchema
from cdd_mundial.data.identities import TeamResolver, UnknownTeamError
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    copy_immutable_capture,
    file_sha256,
    write_provenance_manifest,
)
```

**Escritura de artefacto validado** (`ingest_martj42.py` líneas 266-269) — el patrón para `elo_history.parquet` / `elo_ratings.parquet`:
```python
validated = HistoricalMatchesSchema.validate(output[canonical_columns])
output_path.parent.mkdir(parents=True, exist_ok=True)
validated.to_parquet(output_path, index=False)
return validated
```

**Registro de provenance del artefacto derivado** (`ingest_martj42.py` líneas 387-399) — replicar para los parquet del modelo:
```python
write_provenance_manifest(
    ProvenanceRecord(
        source="martj42",
        source_url=DATASET_URL,
        retrieved_at_utc=datetime.now(timezone.utc),
        source_version=source_version,
        sha256=file_sha256(output_path),
        license="CC0-1.0",
        local_path=output_path,
        notes=f"Derived canonical parquet from immutable raw captures: {raw_checksums}",
    ),
    data_root / "metadata",
)
```
**OJO:** la API real es `ProvenanceRecord` + `write_provenance_manifest(record, metadata_root)` (`provenance.py` líneas 21-61), NO `record_provenance(path, metadata)` como dice CONTEXT.md.

**Conversión de fecha al cargar** (pitfall 11 — `date` es `str` en el contrato; patrón en `ingest_martj42.py` línea 205):
```python
results["date"] = pd.to_datetime(results["date"], errors="raise").dt.strftime("%Y-%m-%d")
```
Para `load_matches()`: convertir UNA sola vez a datetime real (`pd.to_datetime(frame["date"])`) tras validar el schema.

**Matemática del update Elo:** sin análogo en repo — copiar el ejemplo verificado de RESEARCH.md §Code Examples (`expected_score`, `margin_factor` con rama de empate = 1.0, `elo_update` con `drew_after_et`).

---

### `src/cdd_mundial/models/dixon_coles.py` (MLE + contrato congelado)

**Analog A — clase con estado validado en `__init__`:** `identities.py` líneas 28-37:
```python
class TeamResolver:
    """Resolve exact source names to immutable canonical team IDs."""

    def __init__(self, teams: pd.DataFrame, aliases: pd.DataFrame) -> None:
        self.teams = TeamsSchema.validate(teams.copy())
        self.aliases = TeamAliasesSchema.validate(aliases.copy())

        unknown_ids = sorted(set(self.aliases["team_id"]) - set(self.teams["team_id"]))
        if unknown_ids:
            raise ValueError(f"alias rows reference unknown team IDs: {unknown_ids}")
```
`DixonColesModel` debe seguir el mismo patrón: validar invariantes en construcción (ρ dentro de bounds, equipos conocidos) y fallar con mensaje que incluya los valores ofensores.

**Analog B — dataclass serializable:** `provenance.py` líneas 21-49 (`ProvenanceRecord` frozen dataclass con `to_dict()` determinista, claves ordenadas) — patrón para serializar `dc_params_{fecha}.json`:
```python
@dataclass(frozen=True)
class ProvenanceRecord:
    source: str
    ...
    def to_dict(self) -> dict[str, Any]:
        """Convert the record to deterministic JSON-compatible values."""
        if self.retrieved_at_utc.tzinfo is None:
            raise ValueError("retrieved_at_utc must be timezone-aware")
        ...
```
Y la escritura JSON determinista (`provenance.py` líneas 59-60):
```python
payload = json.dumps(record.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
manifest_path.write_text(payload, encoding="utf-8", newline="\n")
```

**Validación de slugs en `predict_lambdas` (D-09):** los inputs YA son slugs canónicos — validar pertenencia contra el set de equipos del fit y lanzar `UnknownTeamError` (importarla de `cdd_mundial.data.identities`, NO redefinirla). NO usar `TeamResolver.resolve` dentro del contrato (anti-patrón de RESEARCH: "no re-resolver alias dentro del modelo").

**Matemática (τ, NLL, gradiente, matriz W/D/L):** sin análogo — copiar los ejemplos verificados de RESEARCH.md §Code Examples (`tau_log`, `neg_log_lik`, `wdl_from_lambdas`) con bounds `rho ∈ (-0.2, 0.2)` en L-BFGS-B.

---

### `src/cdd_mundial/models/validation.py` (fit-at-cutoff + verificador + CLI)

**Analog:** `ingest_martj42.py` — dos patrones:

**Verificador que falla ruidosamente sobre artefactos reales** (líneas 278-293, `verify_martj42_materialization`):
```python
def verify_martj42_materialization(data_root: Path = Path("data")) -> dict[str, int | str]:
    """Fail unless the real parquet and its source provenance are internally consistent."""
    output_path = data_root / "processed" / "historical_matches.parquet"
    if not output_path.exists():
        raise FileNotFoundError(f"required DATA-01 artifact is missing: {output_path}")

    historical = HistoricalMatchesSchema.validate(pd.read_parquet(output_path))
    versions = historical["source_version"].drop_duplicates().tolist()
    if len(versions) != 1 or not versions[0] or versions[0] == "unknown":
        raise ValueError(f"historical parquet must contain one explicit source version: {versions}")
```
Replicar la forma para el gate D-13: una función que devuelve `dict` resumen (log-loss por holdout vs baselines) y lanza/reporta si el gate no pasa.

**Entry point CLI con argparse** (líneas 403-426, `main()`):
```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize and verify martj42 history.")
    parser.add_argument("--source-version", default=..., help="...")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--verify-only", action="store_true", help="...")
    args = parser.parse_args()
    summary = (...)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

**Constante HOLDOUTS:** usar el dict de RESEARCH.md Pattern 1 (strings exactos con tilde: `"Copa América"`, fechas de inicio verificadas; pitfall 5).

---

### `src/cdd_mundial/data/contracts.py` (mod: schemas para artefactos de modelo)

**Analog:** el mismo archivo — heredar de `CanonicalSchema` (líneas 8-13):
```python
import pandas as pd
import pandera.pandas as pa
from pandera.typing.pandas import Series


class CanonicalSchema(pa.DataFrameModel):
    """Base configuration shared by canonical, post-resolution outputs."""

    class Config:
        strict = True
        coerce = True
```

Modelo de schema con checks (líneas 69-75, `EloRatingsSchema` — ya existe y es EL análogo directo para el snapshot recomputado):
```python
class EloRatingsSchema(CanonicalSchema):
    team_id: Series[str] = pa.Field(unique=True)
    elo_rating: Series[float] = pa.Field(gt=0)
    rank: Series[int] = pa.Field(ge=1)
    rating_date_utc: Series[str] = pa.Field(str_matches=r".*Z$")
    source: Series[str]
    source_version: Series[str]
```
Y dataframe_check cruzado (líneas 64-66):
```python
@pa.dataframe_check
def teams_are_distinct(cls, frame: pd.DataFrame) -> Series[bool]:
    return frame["home_team_id"] != frame["away_team_id"]
```
Nuevos schemas necesarios: `EloHistorySchema` (rating post-partido por equipo/fecha). Decisión de ubicación del planner: añadirlos a `contracts.py` o a un `models/contracts.py` — el patrón de import es idéntico (`import pandera.pandas as pa`, NUNCA `import pandera as pa`).

---

### `data/external/tournament_k_factors.csv` (tabla revisada)

**Analog:** `data/external/teams.csv` (líneas 1-3):
```csv
team_id,canonical_name,fifa_code,elo_code,confederation,is_world_cup_2026,active_from,active_to
algeria,Algeria,ALG,ALG,CAF,true,1962-01-01,
argentina,Argentina,ARG,ARG,CONMEBOL,true,1901-01-01,
```
Convención: header en snake_case, valores revisados a mano, booleanos como `true`/`false` minúscula, vacío = null. Para la tabla K: columnas tipo `tournament,k_category,k_factor,note` cubriendo los 200 strings exactos del parquet (con tildes UTF-8).

---

### `tests/test_elo.py`, `tests/test_dixon_coles.py`, `tests/test_metrics.py` (tests unitarios)

**Analog principal:** `tests/test_identities.py` y `tests/test_ingest_martj42.py`.

**Forma de test: nombre descriptivo + tipado + aserciones directas** (`test_identities.py` líneas 40-53):
```python
def test_resolution_is_exact_and_source_keyed() -> None:
    resolver = TeamResolver.from_csv()

    assert resolver.resolve("martj42", "South Korea", "2022-12-02") == "south-korea"
    with pytest.raises(UnknownTeamError):
        resolver.resolve("martj42", "south korea", "2022-12-02")


def test_unknown_alias_fails_loudly() -> None:
    resolver = TeamResolver.from_csv()

    with pytest.raises(UnknownTeamError, match="unknown team alias"):
        resolver.resolve("martj42", "Atlantis", "2026-06-11")
```
Patrón clave: `pytest.raises(..., match="substring del mensaje")` para cada modo de fallo.

**Construcción de inputs sintéticos inline** (`test_identities.py` líneas 56-104, `test_ambiguous_alias_fails_loudly`): DataFrames pequeños construidos con `pd.DataFrame([{...}, {...}])` dentro del test — usar para el test de recuperación de parámetros DC con datos sintéticos y semilla fija.

**Uso de fixtures comprometidos** (`test_ingest_martj42.py` líneas 20, 68-77):
```python
FIXTURE_ROOT = Path("tests/fixtures/martj42")


def test_build_historical_matches_preserves_source_semantics(test_workspace: Path) -> None:
    output_path = test_workspace / "historical_matches.parquet"

    built = build_historical_matches(
        FIXTURE_ROOT / "results.csv",
        FIXTURE_ROOT / "shootouts.csv",
        output_path=output_path,
        source_version="fixture-v1",
        resolver=TeamResolver.from_csv(),
    )
```
Para Phase 2: `tests/fixtures/models/` con mini-parquet/CSV de partidos para fits smoke sin red.

**Fixtures de workspace** (`tests/conftest.py` líneas 7-20 — YA EXISTEN, reutilizar, no redefinir):
```python
@pytest.fixture
def test_workspace() -> Path:
    """Return a unique workspace-local directory without relying on OS temp ACLs."""
    root = Path(".test-artifacts") / uuid4().hex
    root.mkdir(parents=True)
    return root
```

**Semántica de shootout para tests de Elo** (`test_ingest_martj42.py` líneas 86-93) — el fixture ya tiene un partido 3-3 con `shootout_winner_team_id == "argentina"` y `result_after_extra_time is True`; es el caso de prueba natural para "shootout ⇒ W=0.5, margen factor 1".

---

### `tests/test_validation_temporal.py` (aceptación sobre datos reales)

**Analog:** `tests/test_data01_acceptance.py` (completo, líneas 1-15):
```python
from pathlib import Path

import pytest

from cdd_mundial.data.ingest_martj42 import verify_martj42_materialization


@pytest.mark.data_acceptance
def test_data01_real_martj42_materialization() -> None:
    summary = verify_martj42_materialization(data_root=Path("data"))

    assert summary["row_count"] > 49_000
    assert summary["team_count"] > 300
    assert summary["source_version"]
```
Patrón: marker `data_acceptance` (registrado en `pyproject.toml` líneas 35-39) para tests que requieren el parquet real — usarlo para: conteos holdout exactos (64/64/51/32), corte estricto (ningún partido de entrenamiento ≥ cutoff), Spearman vs `data/processed/elo_current.parquet`, y gate D-13. Los tests rápidos sintéticos van SIN marker.

---

### `notebooks/02_modelos_baseline.ipynb` (notebook didáctico)

**Analog:** `notebooks/01_data_foundation.ipynb` (23 celdas, kernelspec `python3`).

**Estructura obligatoria verificada por gates automáticos** (`tests/test_notebooks.py` líneas 64-81 — corre automático sobre TODO `notebooks/*.ipynb`):
- Cada celda de código DEBE tener markdown previo con el string literal **"What and why"** y markdown posterior con **"Interpretation"** (en inglés exacto, aunque el texto sea español).
- Sin celdas de código vacías; sin secretos (escanea también outputs); kernel `python3`.

**Forma de las celdas del notebook 01** (celdas 4-6, patrón real a replicar):
```markdown
## 3. Identidades canónicas

**What and why:** El error clásico al combinar fuentes de fútbol es la identidad
de equipos: ... [explicación del qué y el porqué, en español]
```
```python
from cdd_mundial.data.identities import TeamResolver, build_coverage_report

resolver = TeamResolver.from_csv()
participants = resolver.teams.loc[resolver.teams['is_world_cup_2026'], 'team_id']
...
```
```markdown
**Interpretation:** Las 48 selecciones resuelven en las cinco fuentes ...
[lectura de los resultados, en español]
```

**Celda 2 — bootstrap de directorio raíz** (copiar tal cual al inicio del notebook 02):
```python
ROOT = Path.cwd() if (Path.cwd() / 'pyproject.toml').exists() else Path.cwd().parent
assert (ROOT / 'pyproject.toml').exists(), 'ejecuta desde la raiz del repo o notebooks/'
os.chdir(ROOT)
```

**Restricción dura:** el notebook importa de `cdd_mundial.models` y NUNCA contiene `def `, `class `, `import requests`, `import kagglehub`, `os.environ` (fragmentos prohibidos, `test_notebooks.py` líneas 47-53; hoy solo aplican al 01, pero D-15 y RESEARCH recomiendan extender el gate al 02). Las derivaciones D-14 (ρ, log-likelihood, gradiente) van en celdas markdown con LaTeX; el código solo INVOCA funciones de `src/`.

---

### `pyproject.toml` (mod: dependencias Wave 0)

**Analog:** el archivo mismo (líneas 10-18) — estilo de pin existente:
```toml
dependencies = [
    "pandas~=2.3.3",
    "numpy>=2,<2.5",
    "pyarrow>=18",
    "pandera[pandas]~=0.31",
    ...
]
```
Añadir con el mismo estilo: `"scipy~=1.17"`, `"scikit-learn~=1.9"`, `"matplotlib~=3.10"`, `"seaborn==0.13.2"`, `"joblib>=1.4"`. penaltyblog/statsmodels NO van en pyproject (solo instalación manual opcional de verificación).

## Shared Patterns

### Fallo ruidoso con excepciones nombradas
**Source:** `src/cdd_mundial/data/identities.py` líneas 14-19, 92-101
**Apply to:** `tournaments.py`, `dixon_coles.py` (predict_lambdas), `validation.py`
Excepciones que heredan de tipos stdlib (`LookupError`, `ValueError`) con docstring de una línea; los mensajes incluyen los valores ofensores con `!r`. Todo input no revisado/desconocido lanza — nunca matching difuso ni defaults silenciosos.

### Validación pandera en fronteras
**Source:** `src/cdd_mundial/data/contracts.py` líneas 1-13 (CanonicalSchema con `strict=True, coerce=True`); uso en `identities.py` líneas 32-33 y `ingest_martj42.py` línea 266
**Apply to:** `elo.py` (artefactos parquet), `validation.py` (carga del histórico)
Validar al construir y al serializar: `Schema.validate(df)` antes de `to_parquet` y después de `read_parquet`. Import canónico: `import pandera.pandas as pa`.

### Provenance de artefactos derivados
**Source:** `src/cdd_mundial/data/provenance.py` líneas 21-61; uso en `ingest_martj42.py` líneas 387-399
**Apply to:** `elo_history.parquet`, `elo_ratings.parquet`, `dc_params_{fecha}.json`
`ProvenanceRecord(...)` + `write_provenance_manifest(record, metadata_root)` con `sha256=file_sha256(path)`. Manifiestos en `data/metadata/{nombre}.provenance.json`.

### Defaults de ruta como Path relativos a la raíz del repo
**Source:** `identities.py` líneas 40-45, `ingest_martj42.py` líneas 49-51, 172
**Apply to:** todas las funciones de `models/` que lean/escriban archivos
Parámetros `path: Path = Path("data/...")` con override explícito en tests vía `test_workspace`/`data_root` fixtures.

### Resumen-dict como retorno de verificadores + CLI JSON
**Source:** `ingest_martj42.py` líneas 347-353 (dict resumen), 403-426 (argparse + `print(json.dumps(summary, indent=2, sort_keys=True))`)
**Apply to:** `validation.py` (reporte gate D-13), `elo.py` (resumen de recomputación)

### Estilo de código transversal
**Source:** todos los módulos Phase 1
- Docstring de módulo de una línea en la primera línea del archivo.
- `from __future__ import annotations` cuando hay type hints de clases propias.
- Type hints completos en firmas públicas (`-> None` incluso en tests).
- Funciones privadas con prefijo `_`; constantes de módulo en MAYÚSCULAS arriba (`DATASET_HANDLE`, `RAW_FILENAMES` → análogos: `HOLDOUTS`, `K_FACTORS`).
- ruff: line-length 100, target py311 (`pyproject.toml` líneas 41-43).

## No Analog Found

Archivos/secciones sin análogo en el repo — el planner debe usar los Code Examples de RESEARCH.md (verificados contra Dixon & Coles 1997 y metodología WFE):

| File | Role | Data Flow | Reason | Fallback |
|------|------|-----------|--------|----------|
| `elo.py` (matemática update) | model | transform | Primera lógica de modelado del repo | RESEARCH.md §Code Examples: `expected_score`, `margin_factor`, `elo_update` |
| `dixon_coles.py` (τ, NLL, gradiente) | model | transform | Primera MLE del repo | RESEARCH.md §Code Examples: `tau_log`, `neg_log_lik` + bounds ρ |
| `baselines.py` | model | transform | No existen comparadores naïve previos | RESEARCH.md Open Question 4 (ordered logit o binning — discreción del planner) |
| `metrics.py` | utility | transform | No existen métricas previas | RESEARCH.md §Code Examples: `rps`, `brier_multiclass`; `sklearn.metrics.log_loss` |
| Visuales matplotlib/seaborn (notebook) | notebook | — | Notebook 01 no tiene gráficas | `sklearn.calibration.calibration_curve` + matplotlib (constraint: nunca plotly) |

## Metadata

**Analog search scope:** `src/cdd_mundial/data/` (8 módulos), `tests/` (12 archivos + conftest + fixtures), `notebooks/`, `data/external/`, `pyproject.toml`
**Files scanned:** 11 leídos en profundidad (contracts.py, identities.py, ingest_martj42.py, provenance.py, __init__.py, conftest.py, test_identities.py, test_ingest_martj42.py, test_data01_acceptance.py, test_notebooks.py, pyproject.toml) + notebook 01 (estructura de celdas) + teams.csv (header)
**Pattern extraction date:** 2026-06-12

**Correcciones críticas vs CONTEXT.md (heredadas de RESEARCH, confirmadas en código):**
- API de provenance: `ProvenanceRecord` + `write_provenance_manifest`, NO `record_provenance`
- Parquet real: `data/processed/historical_matches.parquet`, NO `matches_historical.parquet`
- Snapshot Elo: `data/processed/elo_current.parquet`, NO `data/external/elo_snapshot.parquet`
- Columna `date` del contrato es `str` — convertir a datetime una sola vez al cargar
