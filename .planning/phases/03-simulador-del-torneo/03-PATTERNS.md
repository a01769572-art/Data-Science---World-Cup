# Phase 03: Simulador del Torneo - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 23
**Analogs found:** 23 / 23

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/cdd_mundial/simulation/__init__.py` | config | transform | `src/cdd_mundial/models/__init__.py` | exact |
| `src/cdd_mundial/simulation/state.py` | model | transform | `src/cdd_mundial/data/provenance.py` + `src/cdd_mundial/models/dixon_coles.py` | role-match |
| `src/cdd_mundial/simulation/rules_fifa.py` | utility | transform | `src/cdd_mundial/models/loading.py` + `src/cdd_mundial/models/metrics.py` | partial |
| `src/cdd_mundial/simulation/slots.py` | utility | transform | `src/cdd_mundial/data/ingest_fixture.py` | role-match |
| `src/cdd_mundial/simulation/engine.py` | service | batch | `src/cdd_mundial/models/dixon_coles.py` | partial |
| `src/cdd_mundial/simulation/knockout.py` | utility | transform | `src/cdd_mundial/models/dixon_coles.py` | partial |
| `src/cdd_mundial/simulation/outputs.py` | utility | transform | `src/cdd_mundial/data/ingest_elo.py` + `src/cdd_mundial/models/metrics.py` | partial |
| `tests/test_rules_fifa.py` | test | transform | `tests/test_contracts.py` + `tests/test_fixture.py` | role-match |
| `tests/test_slot_resolution.py` | test | transform | `tests/test_fixture.py` | role-match |
| `tests/test_tournament_state.py` | test | transform | `tests/test_provenance.py` + `tests/test_dixon_coles.py` | role-match |
| `tests/test_simulation_engine.py` | test | batch | `tests/test_dixon_coles.py` + `tests/test_loading.py` | role-match |
| `tests/test_simulation_outputs.py` | test | transform | `tests/test_metrics.py` + `tests/test_contracts.py` | role-match |
| `tests/test_knockout.py` | test | transform | `tests/test_metrics.py` + `tests/test_dixon_coles.py` | role-match |
| `tests/test_simulation_performance.py` | test | batch | `tests/test_dixon_coles.py` | partial |
| `tests/fixtures/tournament/wc2018_group_h.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/two_way_head_to_head.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/three_way_tie.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/four_way_tie.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/fair_play_tie.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/drawing_lots_tie.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/best_thirds.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |
| `tests/fixtures/tournament/third_place_mapping_official.json` | config | file-I/O | `data/metadata/fixture_2026.csv.provenance.json` via provenance pattern | partial |
| `tests/fixtures/tournament/conditioned_results.json` | config | file-I/O | `tests/fixtures/fixture/fixture_2026_sample.csv` | partial |

## Pattern Assignments

### `src/cdd_mundial/simulation/__init__.py` (config, transform)

**Analog:** `src/cdd_mundial/models/__init__.py`

**Package export pattern** ([src/cdd_mundial/models/__init__.py:1](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/__init__.py:1)):
```python
"""Baseline structural models: dynamic Elo, Dixon-Coles, metrics, validation."""

from cdd_mundial.models.dixon_coles import DixonColesModel, predict_lambdas

__all__ = ["DixonColesModel", "predict_lambdas"]
```

Use the same minimal style: module docstring, explicit re-exports, small `__all__`.

### `src/cdd_mundial/simulation/state.py` (model, transform)

**Analogs:** `src/cdd_mundial/data/provenance.py`, `src/cdd_mundial/models/dixon_coles.py`

**Frozen dataclass contract pattern** ([src/cdd_mundial/data/provenance.py:21](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/provenance.py:21), [src/cdd_mundial/models/dixon_coles.py:123](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:123)):
```python
@dataclass(frozen=True)
class ProvenanceRecord:
    ...

@dataclass(frozen=True)
class DixonColesModel:
    ...
    def __post_init__(self) -> None:
        ...
```

**Fail-loudly invariant pattern** ([src/cdd_mundial/models/dixon_coles.py:137](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:137)):
```python
def __post_init__(self) -> None:
    if not (len(self.att) == len(self.dfn) == len(self.teams)):
        raise ValueError(...)
    if not -0.2 <= self.rho <= 0.2:
        raise ValueError(...)
```

**Identity validation pattern** ([src/cdd_mundial/data/identities.py:92](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/identities.py:92)):
```python
if matches.empty:
    raise UnknownTeamError(...)
if len(matches) > 1:
    raise AmbiguousTeamError(...)
```

Apply this to `TournamentState`: frozen dataclasses, `team_a`/`team_b` fields only, no derived standings, reject duplicate `match_id`, negative goals, unknown teams, and conflicting fixture participants.

### `src/cdd_mundial/simulation/rules_fifa.py` (utility, transform)

**Analogs:** `src/cdd_mundial/models/loading.py`, `src/cdd_mundial/models/metrics.py`

**Pure transform pattern** ([src/cdd_mundial/models/loading.py:17](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/loading.py:17)):
```python
def load_matches(... ) -> pd.DataFrame:
    raw = frame.copy() if frame is not None else pd.read_parquet(path)
    matches = HistoricalMatchesSchema.validate(raw)
    ...
    return matches.sort_values(["date", "match_id"]).reset_index(drop=True)
```

**Small NumPy-first pure function pattern** ([src/cdd_mundial/models/metrics.py:8](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/metrics.py:8)):
```python
def rps(probs: np.ndarray, outcome_idx: np.ndarray) -> float:
    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(np.eye(3)[outcome_idx], axis=1)
    return float(((cum_p - cum_o) ** 2).sum(axis=1).mean() / 2)
```

Use the same style for standings, mini-tables, best-thirds, and seeded lots: pure functions returning deterministic arrays/dataframes, no hidden global state, clear sorting at the boundary.

### `src/cdd_mundial/simulation/slots.py` (utility, transform)

**Analog:** `src/cdd_mundial/data/ingest_fixture.py`

**Fixture contract import pattern** ([src/cdd_mundial/data/ingest_fixture.py:7](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_fixture.py:7)):
```python
import pandas as pd

from cdd_mundial.data.contracts import FixtureSchema
from cdd_mundial.data.identities import TeamResolver
```

**Slot integrity pattern** ([src/cdd_mundial/data/ingest_fixture.py:64](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_fixture.py:64)):
```python
pairings = validated[["home_slot", "away_slot"]].apply(
    lambda row: "::".join(sorted((str(row.iloc[0]), str(row.iloc[1])))),
    axis=1,
)
if pairings.duplicated().any():
    raise ValueError(...)
```

**Frozen fixture gate** ([src/cdd_mundial/data/ingest_fixture.py:117](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_fixture.py:117)):
```python
knockout = validated[validated["stage"] != "group"]
if knockout[["home_slot", "away_slot"]].isna().any().any():
    raise ValueError("knockout matches must retain both participant slot references")
```

Use this module to resolve `1A`, `3CDFGH`, `W74`, `L101` directly from the frozen fixture, never from a duplicated manual bracket.

### `src/cdd_mundial/simulation/engine.py` (service, batch)

**Analog:** `src/cdd_mundial/models/dixon_coles.py`

**NumPy import pattern** ([src/cdd_mundial/models/dixon_coles.py:11](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:11)):
```python
import numpy as np
import pandas as pd
```

**Vectorized core pattern** ([src/cdd_mundial/models/dixon_coles.py:57](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:57)):
```python
log_lam = c + att[home_idx] - dfn[away_idx] + gamma * is_home
log_mu = c + att[away_idx] - dfn[home_idx]
lam, mu = np.exp(log_lam), np.exp(log_mu)
```

**Aggregation pattern** ([src/cdd_mundial/models/dixon_coles.py:106](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:106)):
```python
grad_att = np.bincount(home_idx, weights=glam, minlength=n_teams) + np.bincount(
    away_idx, weights=gmu, minlength=n_teams
)
```

**Frozen predictor contract** ([src/cdd_mundial/models/dixon_coles.py:252](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:252), [tests/test_dixon_coles.py:177](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:177)):
```python
def predict_lambdas(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    ...

assert parameters == ["team_a", "team_b", "ctx"]
```

The engine should accept injected `predict_lambdas`-compatible callables and keep `ctx["neutral"]` semantics unchanged.

### `src/cdd_mundial/simulation/knockout.py` (utility, transform)

**Analog:** `src/cdd_mundial/models/dixon_coles.py`

**Probability normalization pattern** ([src/cdd_mundial/models/dixon_coles.py:220](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/dixon_coles.py:220)):
```python
def wdl_from_lambdas(...) -> tuple[float, float, float]:
    matrix = score_matrix(lam, mu, rho, max_goals)
    p_win = float(np.tril(matrix, -1).sum())
    p_draw = float(np.trace(matrix))
    p_loss = float(np.triu(matrix, 1).sum())
    return p_win, p_draw, p_loss
```

Copy the style, not the exact logic: small deterministic helpers over probabilities, explicit `float(...)` casting, symmetry testability, and no side effects.

### `src/cdd_mundial/simulation/outputs.py` (utility, transform)

**Analogs:** `src/cdd_mundial/data/ingest_elo.py`, `src/cdd_mundial/models/metrics.py`

**Validated artifact pattern** ([src/cdd_mundial/data/ingest_elo.py:141](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/ingest_elo.py:141)):
```python
output = selected[[...]]
validated = EloRatingsSchema.validate(output)
output_path.parent.mkdir(parents=True, exist_ok=True)
validated.to_parquet(output_path, index=False)
return validated
```

**Array-to-table pattern** ([src/cdd_mundial/models/metrics.py:8](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/models/metrics.py:8)):
```python
cum_p = np.cumsum(probs, axis=1)
...
return float(...)
```

`outputs.py` should turn integer counts into stable tabular artifacts with explicit column ordering, then validate before writing.

### `tests/test_rules_fifa.py` (test, transform)

**Analogs:** `tests/test_contracts.py`, `tests/test_fixture.py`

**Minimal frame factory pattern** ([tests/test_contracts.py:19](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_contracts.py:19)):
```python
def teams_frame() -> pd.DataFrame:
    return pd.DataFrame([...])
```

**Fail-loudly assertion pattern** ([tests/test_fixture.py:68](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_fixture.py:68)):
```python
with pytest.raises(ValueError, match="exactly 104"):
    validate_fixture_structure(fixture)
```

Use hand-authored fixtures with explicit expected order fields. Do not derive expected rankings from production logic.

### `tests/test_slot_resolution.py` (test, transform)

**Analog:** `tests/test_fixture.py`

**Contract regression pattern** ([tests/test_fixture.py:36](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_fixture.py:36)):
```python
fixture = load_fixture_2026(FIXTURE_PATH)
group = fixture[fixture["stage"] == "group"]
knockout = fixture[fixture["stage"] != "group"]
...
assert knockout[["home_slot", "away_slot"]].notna().all().all()
```

Use the real frozen fixture to test token compatibility and unresolved-slot elimination.

### `tests/test_tournament_state.py` (test, transform)

**Analogs:** `tests/test_provenance.py`, `tests/test_dixon_coles.py`

**Workspace fixture pattern** ([tests/conftest.py:7](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/conftest.py:7)):
```python
@pytest.fixture
def test_workspace() -> Path:
    root = Path(".test-artifacts") / uuid4().hex
    root.mkdir(parents=True)
    return root
```

**Dataclass round-trip pattern** ([tests/test_dixon_coles.py:219](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:219)):
```python
toy_model.save(path)
loaded = DixonColesModel.load(path)
assert loaded == toy_model
```

Mirror this for state serialization only if Phase 3 actually persists state; otherwise keep tests focused on constructor invariants.

### `tests/test_simulation_engine.py` (test, batch)

**Analogs:** `tests/test_dixon_coles.py`, `tests/test_loading.py`

**Seeded RNG pattern** ([tests/test_dixon_coles.py:32](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:32)):
```python
rng = np.random.default_rng(7)
```

**Scalar oracle pattern** ([tests/test_loading.py:29](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_loading.py:29)):
```python
frame = pd.DataFrame([_match_row(home_score=2, away_score=1)])
loaded = load_matches(frame=frame)
assert loaded.loc[0, "outcome_90"] == "home_win"
```

Use tiny deterministic fixtures plus stub lambdas for vectorized-vs-scalar comparisons.

### `tests/test_simulation_outputs.py` (test, transform)

**Analogs:** `tests/test_metrics.py`, `tests/test_contracts.py`

**Invariant-style assertion pattern** ([tests/test_metrics.py:7](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_metrics.py:7)):
```python
assert rps(probs, outcome_idx) == 0.0
assert brier_multiclass(probs, outcome_idx) == 0.0
```

**Schema-minded test data pattern** ([tests/test_contracts.py:154](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_contracts.py:154)):
```python
validated = schema.validate(frame_factory())
assert len(validated) == 1
```

Output tests should check monotonicity, totals, uniqueness, and `[0,1]` bounds as invariants, not exact Monte Carlo values.

### `tests/test_knockout.py` (test, transform)

**Analogs:** `tests/test_metrics.py`, `tests/test_dixon_coles.py`

**Approximation pattern** ([tests/test_metrics.py:20](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_metrics.py:20), [tests/test_dixon_coles.py:208](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:208)):
```python
assert value == pytest.approx(expected)
assert p_win + p_draw + p_loss == pytest.approx(1.0, abs=1e-9)
```

Use `pytest.approx` for complement and symmetry properties; keep identical-strength checks exact or near-exact.

### `tests/test_simulation_performance.py` (test, batch)

**Analog:** `tests/test_dixon_coles.py`

**Benchmark setup pattern** ([tests/test_dixon_coles.py:56](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_dixon_coles.py:56)):
```python
@pytest.fixture(scope="module")
def synthetic_fit() -> tuple:
    rng = np.random.default_rng(42)
    ...
```

Keep performance inputs module-scoped and seeded. The validation artifact already requires `@pytest.mark.performance`; no current repo analog exists for that marker.

### `tests/fixtures/tournament/*.json` (config, file-I/O)

**Analogs:** `tests/fixtures/fixture/fixture_2026_sample.csv`, `data/metadata/*.provenance.json`

**Reviewable fixture pattern** ([tests/test_fixture.py:21](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/tests/test_fixture.py:21)):
```python
sample = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=True)
validated = FixtureSchema.validate(sample[FIXTURE_COLUMNS])
```

**Provenance payload pattern** ([src/cdd_mundial/data/provenance.py:40](C:/Users/jesus/OneDrive%20-%20Instituto%20Tecnologico%20y%20de%20Estudios%20Superiores%20de%20Monterrey/Documents/CDD-MUNDIAL/src/cdd_mundial/data/provenance.py:40)):
```python
{
    "license": self.license,
    "local_path": self.local_path.as_posix(),
    "retrieved_at_utc": ...,
    "sha256": self.sha256,
    "source": self.source,
    "source_url": self.source_url,
    "source_version": self.source_version,
}
```

Tournament JSON fixtures should be minimal, explicit, and reviewable. `third_place_mapping_official.json` should carry provenance fields or a sibling manifest-like block because the validation phase makes source evidence a gate.

## Shared Patterns

### Frozen Model Contract

**Source:** `src/cdd_mundial/models/dixon_coles.py`, `tests/test_dixon_coles.py`
**Apply to:** `engine.py`, `knockout.py`, engine tests
```python
def predict_lambdas(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    ...

assert parameters == ["team_a", "team_b", "ctx"]
```

Never rename to home/away inside public simulation contracts. Host advantage remains in `ctx["neutral"]`.

### Frozen Fixture Contract

**Source:** `src/cdd_mundial/data/ingest_fixture.py`, `tests/test_fixture.py`
**Apply to:** `slots.py`, `engine.py`, slot tests
```python
if len(validated) != 104:
    raise ValueError(...)
...
if knockout[["home_slot", "away_slot"]].isna().any().any():
    raise ValueError(...)
```

Drive the bracket from `fixture_2026.csv` slot strings; do not create a second topology source.

### Pandera Validation

**Source:** `src/cdd_mundial/data/contracts.py`
**Apply to:** any new persisted output tables
```python
class CanonicalSchema(pa.DataFrameModel):
    class Config:
        strict = True
        coerce = True
```

If Phase 3 emits parquet artifacts, define strict schemas first, then validate before write.

### Provenance and Immutable Evidence

**Source:** `src/cdd_mundial/data/provenance.py`, `tests/test_provenance.py`
**Apply to:** regulatory annex fixture, any archived official mapping artifact
```python
payload = json.dumps(record.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
manifest_path.write_text(payload, encoding="utf-8", newline="\n")
```

Regulatory evidence should be deterministic UTF-8 JSON with checksum and retrieval timestamp.

### Validated Artifact Writing

**Source:** `src/cdd_mundial/data/ingest_elo.py`, `src/cdd_mundial/data/ingest_martj42.py`
**Apply to:** probability outputs if materialized
```python
validated = Schema.validate(output)
output_path.parent.mkdir(parents=True, exist_ok=True)
validated.to_parquet(output_path, index=False)
```

### NumPy-First Pure Functions

**Source:** `src/cdd_mundial/models/dixon_coles.py`, `src/cdd_mundial/models/metrics.py`
**Apply to:** `rules_fifa.py`, `engine.py`, `knockout.py`, output aggregation
```python
lam, mu = np.exp(log_lam), np.exp(log_mu)
...
cum_p = np.cumsum(probs, axis=1)
```

Prefer vectorized arrays and explicit return values over object-heavy mutable flows.

### Pytest Structure

**Source:** `tests/conftest.py`, `tests/test_fixture.py`, `tests/test_contracts.py`
**Apply to:** all new tests
```python
@pytest.fixture
def test_workspace() -> Path:
    ...

with pytest.raises(ValueError, match="..."):
    ...
```

Use small inline frame factories, seeded RNGs, and invariant assertions.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| None | — | — | The repo has usable analogs for every implied Phase 3 file, but `simulation/` itself is a new package so most matches are partial rather than exact. |

## Metadata

**Analog search scope:** `src/cdd_mundial/data/`, `src/cdd_mundial/models/`, `tests/`
**Files scanned:** 13 primary analog files
**Pattern extraction date:** 2026-06-12

## PATTERN MAPPING COMPLETE
