# Phase 04: Primer Pronostico + Pipeline Diario - Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 18
**Analogs found:** 16 / 18

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `data/external/results_2026.csv` | config | file-I/O | `data/external/odds_2026_template.csv` + `tests/fixtures/tournament/conditioned_results.json` contract via `src/cdd_mundial/simulation/state.py` | partial |
| `src/cdd_mundial/live/__init__.py` | provider | request-response | `src/cdd_mundial/simulation/__init__.py` | exact |
| `src/cdd_mundial/live/contracts.py` | model | transform | `src/cdd_mundial/data/contracts.py` | exact |
| `src/cdd_mundial/live/results.py` | service | file-I/O | `src/cdd_mundial/data/ingest_fixture.py` + `src/cdd_mundial/simulation/state.py` | role-match |
| `src/cdd_mundial/live/predict.py` | service | transform | `src/cdd_mundial/simulation/outputs.py` + `src/cdd_mundial/models/validation.py` | role-match |
| `src/cdd_mundial/live/calibration.py` | service | transform | `src/cdd_mundial/data/ingest_odds.py` + `src/cdd_mundial/models/validation.py` + `src/cdd_mundial/models/metrics.py` | role-match |
| `src/cdd_mundial/live/snapshots.py` | service | file-I/O | `src/cdd_mundial/data/provenance.py` + `src/cdd_mundial/models/validation.py` | role-match |
| `src/cdd_mundial/live/report.py` | service | file-I/O | no close in-repo renderer; borrow artifact-writing/CLI patterns from `src/cdd_mundial/models/validation.py` | partial |
| `src/cdd_mundial/live/__main__.py` | controller | request-response | `src/cdd_mundial/models/validation.py` main + `src/cdd_mundial/data/ingest_martj42.py` main | exact |
| `templates/report_base.html.jinja` | component | request-response | no close analog in repo | none |
| `templates/report_daily.html.jinja` | component | request-response | no close analog in repo | none |
| `pyproject.toml` | config | request-response | existing `[project]` dependency block | exact |
| `tests/test_live_results.py` | test | file-I/O | `tests/test_tournament_state.py` + `tests/test_fixture.py` | exact |
| `tests/test_live_snapshots.py` | test | file-I/O | `tests/test_provenance.py` + `tests/test_validation_temporal.py` | exact |
| `tests/test_live_report.py` | test | file-I/O | `tests/test_simulation_outputs.py` | role-match |
| `tests/test_live_calibration.py` | test | transform | `tests/test_odds.py` + `tests/test_metrics.py` + `tests/test_validation_temporal.py` | exact |
| `tests/test_live_pipeline.py` | test | batch | `tests/test_simulation_engine.py` + `tests/test_validation_temporal.py` | exact |
| `tests/test_live_reproducibility.py` | test | batch | `tests/test_simulation_engine.py` + `tests/test_provenance.py` | exact |

## Pattern Assignments

### `src/cdd_mundial/live/__init__.py` and package exports

**Analog:** `src/cdd_mundial/simulation/__init__.py`

**Export surface pattern** ([src/cdd_mundial/simulation/__init__.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/__init__.py:3)):
```python
from cdd_mundial.simulation.engine import (
    SimulationResult,
    simulate_tournaments,
)
...
__all__ = [
    "PlayedMatchResult",
    "SimulationResult",
    "TournamentState",
    ...
]
```

**Reuse:** keep `live` as a thin public API package that re-exports stable entrypoints instead of hiding them behind deep paths.

---

### `src/cdd_mundial/live/contracts.py`

**Analog:** `src/cdd_mundial/data/contracts.py`

**Imports/config pattern** ([src/cdd_mundial/data/contracts.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/contracts.py:3)):
```python
import pandas as pd
import pandera.pandas as pa
from pandera.typing.pandas import Series

class CanonicalSchema(pa.DataFrameModel):
    class Config:
        strict = True
        coerce = True
```

**Validation pattern** ([src/cdd_mundial/data/contracts.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/contracts.py:151)):
```python
@pa.dataframe_check
def probabilities_are_normalized(cls, frame: pd.DataFrame) -> Series[bool]:
    probability_sum = frame["prob_home"] + frame["prob_draw"] + frame["prob_away"]
    return (probability_sum - 1.0).abs() <= 1e-9
```

**Reuse:** define `LiveResultsSchema`, `UpcomingPredictionsSchema`, `FrozenBenchmarkSchema`, `CalibrationMatchesSchema`, and snapshot-table schemas as strict/coercing `DataFrameModel`s with `dataframe_check`s for normalization, uniqueness, and append-only keys.

---

### `src/cdd_mundial/live/results.py`

**Analogs:** `src/cdd_mundial/data/ingest_fixture.py`, `src/cdd_mundial/simulation/state.py`

**Load-and-fail-loud shape** ([src/cdd_mundial/data/ingest_fixture.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_fixture.py:123)):
```python
def load_fixture_2026(path: Path = Path("data/external/fixture_2026.csv"), ...) -> pd.DataFrame:
    fixture = pd.read_csv(path, dtype=str, keep_default_na=True)
    missing_columns = set(FIXTURE_COLUMNS) - set(fixture.columns)
    if missing_columns:
        raise ValueError(f"fixture is missing columns: {sorted(missing_columns)}")
    return validate_fixture_structure(fixture, resolver=resolver)
```

**State-construction pattern** ([src/cdd_mundial/simulation/state.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/state.py:115)):
```python
@classmethod
def from_results(cls, results: Iterable[PlayedMatchResult], *, fixture: pd.DataFrame) -> TournamentState:
    ...
    if record.match_id in played:
        raise ValueError(f"duplicate played result for match_id {record.match_id!r}")
    if record.match_id not in stage_by_match:
        raise ValueError(f"match_id {record.match_id!r} is not in the fixture")
```

**Contract keys to mirror** ([src/cdd_mundial/simulation/state.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/state.py:29)):
```python
_REQUIRED_RESULT_KEYS = ("match_id", "team_a", "team_b", "goals_a", "goals_b")
_OPTIONAL_RESULT_KEYS = ("fair_play_a", "fair_play_b", "advanced_team")
```

**Reuse:** CSV loader should read only those columns, validate with pandera, instantiate `PlayedMatchResult` rows, then call `TournamentState.from_results(...)`. Keep completeness and override gates in this module, not in notebooks.

---

### `src/cdd_mundial/live/predict.py`

**Analogs:** `src/cdd_mundial/simulation/outputs.py`, `src/cdd_mundial/models/validation.py`

**Counts-to-table pattern** ([src/cdd_mundial/simulation/outputs.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/outputs.py:27)):
```python
def advancement_table(result: SimulationResult) -> pd.DataFrame:
    probs = result.advancement_counts / result.n_sims
    frame = pd.DataFrame({...})
    return frame[_ADVANCEMENT_COLUMNS]
```

**Per-match prediction loop** ([src/cdd_mundial/models/validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:96)):
```python
def dc_predictions(model: Any, holdout_matches: pd.DataFrame) -> np.ndarray:
    rows = []
    for row in holdout_matches.itertuples(index=False):
        lam, mu = model.predict_lambdas(..., {"neutral": bool(row.neutral), "date": row.date, "tournament_type": ...})
        rows.append(wdl_from_lambdas(lam, mu, model.rho))
```

**Reuse:** build upcoming-match prediction tables by iterating fixture rows for unresolved matches, always using `predict_lambdas(...)`/`wdl_from_lambdas(...)`, and derive tournament tables from `advancement_table(...)` and `group_position_table(...)` rather than recomputing probabilities manually.

---

### `src/cdd_mundial/live/calibration.py`

**Analogs:** `src/cdd_mundial/data/ingest_odds.py`, `src/cdd_mundial/models/validation.py`, `src/cdd_mundial/models/metrics.py`

**Quote normalization + validation pattern** ([src/cdd_mundial/data/ingest_odds.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_odds.py:382)):
```python
def build_odds_benchmark(...):
    ...
    prob_home, prob_draw, prob_away = demargin_decimal_odds([price_home, price_draw, price_away])
    ...
    frame = pd.DataFrame(rows, columns=list(BENCHMARK_COLUMNS))
    validated = OddsSchema.validate(frame)
```

**Metric computation pattern** ([src/cdd_mundial/models/validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:149)):
```python
def _metrics(probs: np.ndarray, outcome_idx: np.ndarray) -> dict[str, float]:
    return {
        "log_loss": float(log_loss(outcome_idx, probs, labels=[0, 1, 2])),
        "brier": float(brier_multiclass(probs, outcome_idx)),
        "rps": float(rps(probs, outcome_idx)),
    }
```

**RPS implementation to reuse** ([src/cdd_mundial/models/metrics.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/metrics.py:8)):
```python
def rps(probs: np.ndarray, outcome_idx: np.ndarray) -> float:
    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(np.eye(3)[outcome_idx], axis=1)
    return float(((cum_p - cum_o) ** 2).sum(axis=1).mean() / 2)
```

**Reuse:** keep Phase 4 calibration as a derived ledger over canonical snapshot predictions plus frozen benchmark rows. Reuse odds semantics and metrics directly; only add aggregation logic for bookmaker median/mean and cumulative time-series.

---

### `src/cdd_mundial/live/snapshots.py`

**Analogs:** `src/cdd_mundial/data/provenance.py`, `src/cdd_mundial/models/validation.py`

**Deterministic JSON metadata pattern** ([src/cdd_mundial/data/provenance.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/provenance.py:52)):
```python
def write_provenance_manifest(record: ProvenanceRecord, metadata_root: Path = Path("data/metadata")) -> Path:
    metadata_root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    manifest_path.write_text(payload, encoding="utf-8", newline="\n")
```

**Append-only/immutable copy pattern** ([src/cdd_mundial/data/provenance.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/provenance.py:64)):
```python
def copy_immutable_capture(source_path: Path, destination_path: Path) -> Path:
    if destination_path.exists():
        if file_sha256(destination_path) != source_checksum:
            raise FileExistsError(...)
        return destination_path
```

**Artifact materialization pattern** ([src/cdd_mundial/models/validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:246)):
```python
def materialize_validation(data_root: Path = Path("data")) -> dict[str, Any]:
    ...
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", ...)
    validated_predictions.to_parquet(predictions_path, index=False)
```

**Reuse:** snapshot writer should create one new timestamped folder, write deterministic JSON and parquet files, store SHA-256s for critical inputs/artifacts, and reject overwrite/mutation. Add git-clean/dirty override logic here.

---

### `src/cdd_mundial/live/report.py`

**Analogs:** `src/cdd_mundial/models/validation.py` for CLI/materialization shape, `src/cdd_mundial/simulation/outputs.py` for stable tabular inputs

**Stable artifact IO pattern** ([src/cdd_mundial/models/validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:253)):
```python
report_path = models_root / f"validation_report_{artifact_date}.json"
report_path.write_text(..., encoding="utf-8", newline="\n")
validated_predictions.to_parquet(predictions_path, index=False)
```

**Table-source discipline** ([src/cdd_mundial/simulation/outputs.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/outputs.py:37)):
```python
frame = pd.DataFrame({...})
return frame[_ADVANCEMENT_COLUMNS]
```

**Reuse:** renderer should accept a snapshot directory path, read parquet/JSON artifacts only, derive HTML tables from those frozen tables, then write `report.html` plus static image assets into the snapshot. There is no existing Jinja analog in repo; planner should use the research Jinja2 pattern, not invent a second business-logic path inside templates.

---

### `src/cdd_mundial/live/__main__.py`

**Analogs:** `src/cdd_mundial/models/validation.py`, `src/cdd_mundial/data/ingest_martj42.py`, `src/cdd_mundial/data/ingest_odds.py`

**CLI skeleton pattern** ([src/cdd_mundial/models/validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:353)):
```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Run or verify ...")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--verify-only", action="store_true", help="...")
    args = parser.parse_args()
    summary = verify_...(args.data_root) if args.verify_only else materialize_...(args.data_root)
    print(json.dumps(summary, indent=2, sort_keys=True))
```

**Alternative flag pattern** ([src/cdd_mundial/data/ingest_odds.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_odds.py:524)):
```python
parser.add_argument("--raw-payload", type=Path, default=None, help="...")
parser.add_argument("--manual-csv", type=Path, default=None, help="...")
parser.add_argument("--output", type=Path, default=ODDS_PARQUET_PATH)
```

**Reuse:** one-command official run should follow the same argparse + JSON summary convention. If the planner adds `--official`, `--allow-dirty`, `--manual-odds`, `--results-csv`, or `--verify-only`, keep the flag parsing and printed summary consistent with existing CLIs.

---

### `pyproject.toml`

**Analog:** existing dependency blocks in `pyproject.toml`

**Dependency declaration pattern** ([pyproject.toml](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/pyproject.toml:5)):
```toml
[project]
dependencies = [
    "pandas~=2.3.3",
    ...
    "joblib>=1.4",
]
```

**Reuse:** if the baseline renderer uses Jinja2, add it as a direct dependency in `[project].dependencies`, not only as a local transitive install.

---

### `tests/test_live_results.py`

**Analogs:** `tests/test_tournament_state.py`, `tests/test_fixture.py`

**Mini-fixture factory pattern** ([tests/test_tournament_state.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_tournament_state.py:22)):
```python
def mini_fixture() -> pd.DataFrame:
    return pd.DataFrame([...])
```

**Fail-loud assertion style** ([tests/test_tournament_state.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_tournament_state.py:119)):
```python
with pytest.raises(ValueError, match="duplicate"):
    TournamentState.from_results(...)
```

**Reuse:** keep tests table-driven, explicit, and fixture-backed. Focus on duplicate rows, fixture conflicts, incomplete already-played matches, and override traces.

---

### `tests/test_live_snapshots.py`

**Analogs:** `tests/test_provenance.py`, `tests/test_validation_temporal.py`

**Determinism/append-only pattern** ([tests/test_provenance.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_provenance.py:61)):
```python
manifest = write_provenance_manifest(record, data_root / "metadata")
first = manifest.read_bytes()
write_provenance_manifest(record, data_root / "metadata")
assert manifest.read_bytes() == first
```

**Artifact verification pattern** ([tests/test_validation_temporal.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_validation_temporal.py:89)):
```python
summary = verify_model04_materialization(Path("data"))
assert isinstance(summary["gate_passed"], bool)
```

**Reuse:** assert byte-stable metadata, append-only folder creation, and git gate behavior through verification-style tests that inspect written artifacts rather than internal helpers only.

---

### `tests/test_live_calibration.py`

**Analogs:** `tests/test_odds.py`, `tests/test_metrics.py`, `tests/test_validation_temporal.py`

**Numeric normalization style** ([tests/test_odds.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_odds.py:279)):
```python
probability_sum = frame["prob_home"] + frame["prob_draw"] + frame["prob_away"]
assert ((probability_sum - 1.0).abs() <= 1e-9).all()
```

**Metric oracle style** ([tests/test_metrics.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_metrics.py:15)):
```python
assert rps(probs, outcome_idx) == pytest.approx(5 / 18)
assert brier_multiclass(probs, outcome_idx) == pytest.approx(2 / 3)
```

**Reuse:** test median-vs-mean bookmaker aggregation, frozen benchmark timestamps, and cumulative `log_loss`/`rps` with small hand-checkable examples.

---

### `tests/test_live_pipeline.py` and `tests/test_live_reproducibility.py`

**Analogs:** `tests/test_simulation_engine.py`, `tests/test_validation_temporal.py`, `tests/test_provenance.py`

**Injected predictor / deterministic seed pattern** ([tests/test_simulation_engine.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_simulation_engine.py:27)):
```python
class RecordingPredictor:
    def __call__(self, team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
        self.calls.append((team_a, team_b))
        ...
```

**Bit-reproducibility pattern** ([tests/test_simulation_engine.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_simulation_engine.py:72)):
```python
a = simulate_tournaments(..., seed=11)
b = simulate_tournaments(..., seed=11)
assert np.array_equal(a.advancement_counts, b.advancement_counts)
```

**Reuse:** official pipeline tests should inject/pin model behavior and assert that the same inputs yield identical snapshot tables and metadata-critical hashes.

## Shared Patterns

### Canonical Validation
**Source:** [src/cdd_mundial/data/contracts.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/contracts.py:8)

Apply strict `pandera.pandas` `DataFrameModel`s with `Config.strict = True` and `Config.coerce = True`. Add `@pa.dataframe_check` methods for uniqueness, normalization, and append-only invariants instead of ad hoc assertions scattered across modules.

### Deterministic JSON and Checksums
**Source:** [src/cdd_mundial/data/provenance.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/provenance.py:12)

Use `file_sha256(...)`, deterministic `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=True) + "\n"`, and append-only write semantics for snapshot metadata. Snapshot code should extend this pattern rather than inventing a second provenance format.

### Official CLI Convention
**Source:** [src/cdd_mundial/models/validation.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/validation.py:353), [src/cdd_mundial/data/ingest_martj42.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_martj42.py:403)

Keep CLI entrypoints as `main()` with `argparse`, `Path`-typed args, optional `--verify-only`, and a final `print(json.dumps(summary, indent=2, sort_keys=True))`.

### Consume Existing Simulation Contracts
**Source:** [src/cdd_mundial/simulation/state.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/state.py:115), [src/cdd_mundial/simulation/outputs.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/simulation/outputs.py:27)

Phase 4 should end in `TournamentState.from_results(...)`, call `simulate_tournaments(...)` with the full canonical fixture, and derive publication tables from `advancement_table(...)` / `group_position_table(...)`. Do not fork state logic, RNG logic, or probability-table logic.

### Odds/Calibration Semantics
**Source:** [src/cdd_mundial/data/ingest_odds.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_odds.py:215), [src/cdd_mundial/models/metrics.py](/C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/metrics.py:8)

Reuse `demargin_decimal_odds(...)`, fixture-linking semantics, and the existing `rps(...)`/`brier_multiclass(...)` helpers. Phase 4 adds benchmark aggregation and ledger persistence, not a replacement odds model.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `templates/report_base.html.jinja` | component | request-response | No existing HTML/Jinja template files in repo. Use the research Jinja inheritance pattern and keep business logic out of templates. |
| `templates/report_daily.html.jinja` | component | request-response | No existing report-rendering analog in codebase. Source all data from snapshot parquet/JSON and keep template output deterministic. |

## Metadata

**Analog search scope:** `src/cdd_mundial/data/`, `src/cdd_mundial/models/`, `src/cdd_mundial/simulation/`, `tests/`, `pyproject.toml`, `notebooks/03_simulador_torneo.ipynb`

**Files scanned:** 17 code/test/config files plus Phase 04 context/research inputs and `CLAUDE.md`

**Pattern extraction date:** 2026-06-13
