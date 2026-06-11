# Phase 1: Fundacion de Datos - Research

**Researched:** 2026-06-11
**Domain:** Reproducible ingestion, canonical football-team identities, schema validation, and public data provenance
**Confidence:** HIGH for martj42, kagglehub, pandera, and repository architecture; MEDIUM for the live 2026 fixture and odds provider until probed during execution

<user_constraints>
## User Constraints

No phase CONTEXT.md exists. The user explicitly requested planning from project requirements and research without a separate design discussion.

### Locked Project Decisions
- Python 3.11+ with pandas/numpy/pyarrow and pandera.
- Pin pandas to `~=2.3.3`; do not adopt pandas 3.x during the tournament.
- `data/raw/` is immutable. Transformations write new artifacts under `data/processed/`.
- Every source must resolve through a canonical team table before downstream use.
- The GitHub repository is public and must contain no secrets or restrictively licensed raw data.
- Notebooks use the didactic markdown -> code -> interpretation pattern; production logic lives in importable `src/` modules.
- Phase 1 covers historical data, team identity, current Elo, official fixture, market odds, repository scaffold, and documentation. Live result ingestion remains Phase 4.

### Agent Discretion
- Exact module boundaries and filenames within the project architecture.
- Canonical team ID format and alias-table schema.
- Which odds provider is selected after a capability probe.
- Whether a source artifact is committed, ignored, or represented by a derived snapshot, subject to license review.

### Deferred Ideas
- Live tournament result ingestion and daily orchestration.
- Model features, Elo recomputation, Dixon-Coles, simulation, and reporting.
- Dashboard, player-level data, cloud automation, and betting recommendations.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

Single-tier local Python data pipeline. External HTTP/Kaggle sources enter through `src/data/`, immutable captures live under `data/raw/`, reviewed reference data lives under `data/external/`, and validated canonical outputs live under `data/processed/`.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Source acquisition | API/Backend | Storage | Python adapters fetch or import source-native files and record provenance. |
| Team identity resolution | API/Backend | Storage | Deterministic aliases map source names to stable canonical IDs. |
| Schema contracts | API/Backend | Test infrastructure | Pandera validates stage boundaries; pytest verifies invariants and coverage. |
| Reproducible artifacts | Storage | API/Backend | Raw captures are immutable; processed parquet is regenerated from code. |
| Portfolio documentation | Static/documentation | Test infrastructure | README and notebooks explain the pipeline and are checked structurally. |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 1 should be planned as four independently testable slices: project/test scaffold, historical ingestion plus canonical identity, current tournament reference sources, and public-repository documentation. The canonical identity layer is the load-bearing contract: source adapters preserve original names, alias rows translate them to stable `team_id` values, and no processed table may contain an unresolved team.

The martj42 source semantics are now explicit. `results.csv` scores include extra time and exclude shootout goals; `shootouts.csv` separately names the winner. Its team names use current successor identities, while venue-country names retain their historical form. The source is CC0, so it can be mirrored with provenance, but the implementation should still retain the exact dataset version, retrieval timestamp, checksums, and source URL.

The 2026 fixture and odds remain execution-time capability probes. FIFA should be the authority for match IDs, pairings, venues, and kickoff times; a manually reviewed committed CSV is the stable runtime artifact. The odds adapter must first query provider capabilities for a World Cup sport key and three-way `h2h` markets. If unavailable, execution must produce a documented blocker or import template rather than fabricate benchmark data.

**Primary recommendation:** Build deterministic source adapters around a canonical `team_id`, validate every output with strict pandera schemas, and make source capability/license checks explicit gates rather than hidden assumptions.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11 or 3.12 | Runtime | Stable Windows wheels across the selected data-science stack. |
| pandas | `~=2.3.3` | Tabular transforms | Project pin avoids pandas 3.x compatibility churn during the tournament. |
| pyarrow | compatible current pin | Parquet engine | Required for typed, compact processed artifacts. |
| pandera | `~=0.31` with `[pandas]` | Runtime dataframe contracts | `DataFrameModel`, strict schemas, coercion, and dataframe-level checks fit stage boundaries. |
| kagglehub | `~=1.0` | Dataset acquisition | Official Kaggle client supports public dataset download without authentication unless consent/private access is required. |
| requests | current compatible pin | HTTP adapters | Sufficient for TSV/JSON/CSV sources and explicit timeout/status handling. |
| pytest | current compatible pin | Automated gates | Fast unit and integration tests for schemas, aliases, coverage, and source fixtures. |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `python-dotenv` | Local secret loading | Only if an odds API key is needed; `.env` remains ignored. |
| `ruff` | Formatting/linting | Keep the new repository scaffold consistent with minimal overhead. |
| `jupyterlab` + `ipykernel` | Didactic EDA | Notebooks call functions from `src/`; no production-only logic in cells. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `kagglehub.dataset_download` | Manual Kaggle download | Manual is a fallback only; it loses reproducible acquisition metadata. |
| Pandera `DataFrameModel` | Ad hoc assertions | Assertions do not provide reusable typed stage contracts or structured failure cases. |
| Stable canonical IDs | Joining normalized names | Name normalization cannot safely distinguish teams such as Korea DPR and Korea Republic. |
| The Odds API capability probe | Hard-code a provider/sport key | Hard-coding can silently fail when competition keys or plan access change. |

**Installation:**
```bash
python -m pip install "pandas~=2.3.3" pyarrow "pandera[pandas]~=0.31" kagglehub requests pytest ruff jupyterlab ipykernel python-dotenv
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### System Architecture Diagram

```text
Kaggle martj42 ----\
eloratings TSV -----\
FIFA fixture --------> source adapters -> immutable capture + metadata/checksum
odds provider -------/                         |
                                               v
                                    source-specific parsing
                                               |
                                               v
teams.csv <-> team_aliases.csv -> deterministic canonical resolution
                                               |
                         unresolved names? ----+---- yes -> fail + coverage report
                                               |
                                               no
                                               v
                                  strict pandera validation
                                               |
                                               v
                              data/processed/*.parquet
                                               |
                                               v
                                 pytest gates + notebook EDA
```

### Recommended Project Structure
```text
.
|-- pyproject.toml
|-- README.md
|-- .env.example
|-- .gitignore
|-- data/
|   |-- raw/                  # immutable source captures; commit only when license permits
|   |-- external/             # reviewed teams, aliases, fixture, and import templates
|   |-- processed/            # canonical validated parquet outputs
|   `-- metadata/             # JSON provenance manifests and checksums
|-- notebooks/
|   `-- 01_data_foundation.ipynb
|-- src/
|   `-- cdd_mundial/
|       `-- data/
|           |-- contracts.py
|           |-- provenance.py
|           |-- identities.py
|           |-- ingest_martj42.py
|           |-- ingest_elo.py
|           |-- ingest_fixture.py
|           `-- ingest_odds.py
`-- tests/
    |-- fixtures/
    |-- test_contracts.py
    |-- test_identities.py
    |-- test_ingest_martj42.py
    |-- test_ingest_elo.py
    |-- test_fixture.py
    `-- test_odds.py
```

### Pattern 1: Source-native raw, canonical processed
**What:** Preserve source payloads unchanged, then write canonical outputs separately.
**When to use:** Every ingestion adapter.
**Implementation contract:** A fetch/import operation records `source`, `source_url`, `retrieved_at_utc`, `source_version`, `sha256`, `license`, and local path. Processed rows retain source identifiers and original names for auditability.

### Pattern 2: Explicit aliases keyed by source
**What:** Use `(source, source_name) -> team_id`, not one global normalized-name lookup.
**When to use:** Every table with a team name.
**Implementation contract:** Runtime fuzzy matching is forbidden. A helper may suggest aliases during development, but committed alias rows are the only accepted mappings.

### Pattern 3: Pandera at stage exits
**What:** Validate parsed source tables and canonical outputs with named `DataFrameModel` contracts.
**When to use:** Immediately before writing parquet or reviewed CSV artifacts.
**Implementation contract:** Use `import pandera.pandas as pa`; strict canonical schemas reject unexpected columns and dataframe checks enforce cross-column invariants.

### Pattern 4: Capability probes for unstable providers
**What:** Query provider metadata before depending on a competition key or market.
**When to use:** Odds and any fixture endpoint that can change.
**Implementation contract:** Probe results are cached as metadata. Missing World Cup/three-way support yields an explicit `SourceUnavailableError` and a manual import template.

### Anti-Patterns to Avoid
- Joining downstream tables on display names.
- Mutating or cleaning files in `data/raw/`.
- Fuzzy matching during production ingestion.
- Treating shootout winners as changes to martj42 score columns.
- Using the latest FIFA ranking for historical matches; Phase 1 only establishes source-ready snapshot contracts.
- Committing API keys, provider responses without license review, or notebook outputs containing secrets.
- Embedding the whole pipeline in a notebook.
</architecture_patterns>

<data_contracts>
## Recommended Data Contracts

### `teams.csv`
Required columns:
`team_id`, `canonical_name`, `fifa_code`, `elo_code`, `confederation`, `is_world_cup_2026`, `active_from`, `active_to`.

- `team_id`: lowercase ASCII slug that never changes after publication.
- `canonical_name`: current FIFA-facing display name.
- `fifa_code`: nullable for historical/non-FIFA entities, unique when present.
- `is_world_cup_2026`: exactly 48 true rows.

### `team_aliases.csv`
Required columns:
`source`, `source_name`, `team_id`, `valid_from`, `valid_to`, `mapping_note`.

- Unique key: `(source, source_name, valid_from)`.
- `team_id` must exist in `teams.csv`.
- No runtime-generated aliases.

### Canonical historical matches parquet
Required columns:
`match_id`, `date`, `home_team_id`, `away_team_id`, `home_team_source_name`,
`away_team_source_name`, `home_score`, `away_score`, `tournament`, `city`,
`country`, `neutral`, `shootout_winner_team_id`, `result_after_extra_time`,
`source`, `source_version`.

- `home_score` and `away_score` preserve martj42 full-time-including-extra-time semantics.
- `shootout_winner_team_id` is populated only through `shootouts.csv`.
- Do not claim 90-minute labels because martj42 does not provide separate 90-minute scores.

### Fixture 2026
Required columns:
`match_id`, `stage`, `group`, `home_slot`, `away_slot`, `home_team_id`,
`away_team_id`, `kickoff_utc`, `venue`, `host_city`, `host_country`, `status`,
`source_url`, `verified_at_utc`.

- Exactly 104 unique `match_id` values.
- Group stage contains 72 matches across groups A-L.
- Unknown knockout participants remain slot references, not invented team IDs.

### Odds benchmark
Required columns:
`provider`, `bookmaker`, `event_id`, `match_id`, `captured_at_utc`,
`commence_time_utc`, `home_team_id`, `away_team_id`, `market`,
`price_home`, `price_draw`, `price_away`, `prob_home_raw`, `prob_draw_raw`,
`prob_away_raw`, `overround`, `prob_home`, `prob_draw`, `prob_away`.

- Market must be three-way 90-minute `h2h`.
- De-margin v1 uses multiplicative normalization: inverse decimal prices divided by their sum.
- Probabilities must sum to one within tolerance.
</data_contracts>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Kaggle downloads | Custom cookies/scraper | `kagglehub.dataset_download` | Official client handles caching and public-resource access. |
| Dataframe validation | Scattered `assert` statements | Pandera `DataFrameModel` | Reusable contracts and structured failures. |
| Parquet serialization | Custom binary format | pandas + pyarrow | Stable ecosystem interoperability. |
| Team matching | Automatic fuzzy join | Reviewed source alias table | False matches corrupt every downstream model silently. |
| Secret handling | Keys in notebooks/config | Environment variables and `.env.example` | Public repository requirement. |
| Odds de-margin v1 | Complex bookmaker model | Multiplicative normalization | Transparent benchmark sufficient for v1; Shin is deferred. |

**Key insight:** Phase 1 is primarily contract engineering. The value comes from deterministic identity and provenance, not clever parsing.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Conflating match score and advancement
**What goes wrong:** A shootout winner is encoded as a normal win or extra shootout goals are added to scores.
**Why it happens:** `results.csv` and `shootouts.csv` are joined without preserving their distinct semantics.
**How to avoid:** Keep scores unchanged; add a nullable shootout winner field and document that scores include extra time.
**Warning signs:** A drawn knockout match becomes non-drawn after joining shootouts.

### Pitfall 2: Overengineering historical successor mappings
**What goes wrong:** The pipeline remaps historical teams a second time and creates identity inconsistencies.
**Why it happens:** The martj42 README is not read: its team names already use current successor identities.
**How to avoid:** Preserve martj42 team names and map those names directly to canonical IDs; use `former_names.csv` only for audit/context.
**Warning signs:** Duplicate historical rows for "Germany" and "West Germany" created by local logic.

### Pitfall 3: Partial 48-team coverage hidden by inner joins
**What goes wrong:** A tournament participant silently disappears or receives null ratings/odds.
**Why it happens:** Inner joins and row-count checks replace explicit entity coverage.
**How to avoid:** Produce a per-source coverage matrix and fail the phase gate unless every required source mapping is either present or explicitly marked unavailable with evidence.
**Warning signs:** Row count decreases after identity resolution; any unresolved 2026 participant.

### Pitfall 4: Fixture source drift
**What goes wrong:** Scraped fixture order, kickoff timezone, or knockout slots change without review.
**Why it happens:** A dynamic page is treated as a stable runtime API.
**How to avoid:** Freeze a reviewed 104-row CSV with UTC timestamps, source URL, checksum, and verification date; test structural invariants.
**Warning signs:** Duplicate match IDs, local-time strings, or named knockout teams before qualification.

### Pitfall 5: Odds provider assumption
**What goes wrong:** The plan depends on a World Cup key or free historical access that the selected provider does not offer.
**Why it happens:** Generic API documentation is mistaken for competition availability.
**How to avoid:** Put the capability probe first. Select one bookmaker/provider snapshot only after confirming 3-way market availability and terms.
**Warning signs:** Two-outcome arrays for soccer, no draw quote, or provider event names that cannot resolve to fixture match IDs.

### Pitfall 6: Public repository leakage
**What goes wrong:** API keys or non-redistributable raw payloads are committed.
**Why it happens:** All raw data is treated alike.
**How to avoid:** Store license in each provenance manifest; commit CC0 and authored reference files, ignore restricted provider captures, publish schemas/derived probabilities where permitted.
**Warning signs:** `.env` tracked, API key in notebook output, or unknown license metadata.
</common_pitfalls>

<code_examples>
## Code Examples

### Official kagglehub download pattern
```python
import kagglehub

path = kagglehub.dataset_download(
    "martj42/international-football-results-from-1872-to-2017"
)
```
Source: https://github.com/Kaggle/kagglehub

### Pandera class-based contract
```python
import pandera.pandas as pa
from pandera.typing.pandas import Series


class HistoricalMatchSchema(pa.DataFrameModel):
    home_team_id: Series[str]
    away_team_id: Series[str]
    home_score: Series[int] = pa.Field(ge=0, coerce=True)
    away_score: Series[int] = pa.Field(ge=0, coerce=True)

    class Config:
        strict = True
        coerce = True
```
Source: https://pandera.readthedocs.io/en/stable/dataframe_models.html

### Multiplicative de-margin
```python
from collections.abc import Sequence


def demargin_decimal_odds(prices: Sequence[float]) -> list[float]:
    implied = [1.0 / price for price in prices]
    total = sum(implied)
    return [probability / total for probability in implied]
```

### Provenance checksum
```python
from hashlib import sha256
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```
</code_examples>

<validation_architecture>
## Validation Architecture

### Test layers
1. **Unit:** canonical ID normalization helpers, de-margin math, checksum/provenance serialization, and pandera failure behavior.
2. **Contract:** each source parser runs against committed small fixtures and validates exact canonical columns.
3. **Integration:** optional network-marked tests fetch provider metadata; normal CI uses local fixtures and never requires secrets.
4. **Data gates:** generated artifacts are checked for row counts, uniqueness, nulls, source coverage, UTC timestamps, and probability sums.
5. **Documentation gates:** notebook cell ordering and README sections are checked programmatically.

### Requirement-to-test mapping
| Requirement | Automated evidence |
|-------------|--------------------|
| DATA-01 | Historical parser fixture, strict pandera schema, immutable raw checksum test, parquet round-trip. |
| DATA-02 | Alias foreign-key/uniqueness tests plus 48-team per-source coverage matrix gate. |
| DATA-03 | Elo TSV parser fixture, unique code/team mappings, ratings numeric/range checks. |
| DATA-04 | Fixture schema with 104 unique matches, 72 group matches, groups A-L, timezone-aware UTC. |
| DATA-05 | Capability probe test via mocked response, three-way odds schema, de-margin sum-to-one test. |
| DOC-01 | Notebook structure test enforcing markdown -> code -> markdown interpretation blocks. |
| DOC-03 | README section checks, secret scan, `.gitignore` checks, clean install/test commands. |

### Execution sampling
- Every implementation task runs a targeted pytest file.
- Every plan runs `python -m pytest -q` before completion.
- Network tests are opt-in (`pytest -m network`) and cannot be required for normal verification.
- No test should mutate a pre-existing raw capture; use temporary directories.
</validation_architecture>

<open_questions>
## Open Questions

1. **Which official FIFA artifact is easiest to transform into the final 104-row fixture?**
   - Known: FIFA is the authority and the tournament uses 104 matches.
   - Unclear: whether the current official page exposes a stable downloadable table in this environment.
   - Recommendation: implement an import adapter for a reviewed CSV first; retain the official URL and manually cross-check counts/times.

2. **Does the chosen odds provider currently expose World Cup 2026 three-way markets under the available account tier?**
   - Known: The Odds API v4 exposes a sports metadata endpoint and three-way soccer `h2h` markets when supported.
   - Unclear: current competition key and subscription availability.
   - Recommendation: make provider selection the first task of the odds plan; never fabricate or silently substitute two-way quotes.

3. **Can all 48 teams resolve in every source before odds markets exist for every match?**
   - Known: team identity coverage and market event coverage are different concepts.
   - Unclear: future matches may not yet be quoted.
   - Recommendation: require alias coverage for all 48 teams, but measure odds event coverage against currently published provider events and document the capture timestamp.
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- https://github.com/Kaggle/kagglehub - authentication behavior and `dataset_download`.
- https://github.com/martj42/international_results - dataset columns, extra-time/shootout semantics, successor-name policy, neutral flag, CC0 license.
- https://pandera.readthedocs.io/en/stable/dataframe_models.html - `pandera.pandas`, `DataFrameModel`, strict/coerce configuration, dataframe checks.
- https://www.eloratings.net/World.tsv - current Elo TSV endpoint identified by project research.
- https://www.eloratings.net/en.teams.tsv - Elo code/name/alias endpoint identified by project research.
- https://the-odds-api.com/liveapi/guides/v4/ - sports capability endpoint, soccer `h2h` market, UTC commence times, decimal prices.

### Project Sources (HIGH confidence)
- `.planning/PROJECT.md` - constraints and locked project decisions.
- `.planning/REQUIREMENTS.md` - Phase 1 requirement definitions.
- `.planning/ROADMAP.md` - Phase 1 boundary and success criteria.
- `.planning/research/STACK.md` - verified package/version recommendations.
- `.planning/research/ARCHITECTURE.md` - system boundaries and data flow.
- `.planning/research/PITFALLS.md` - identity, label, licensing, and leakage risks.

### Execution-time validation (MEDIUM until confirmed)
- FIFA World Cup 26 official schedule page/download - authoritative fixture fields and kickoff revisions.
- Selected odds provider terms and live sports list - competition availability and redistribution constraints.
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Python ingestion pipeline and dataframe contracts.
- Ecosystem: kagglehub, requests, pandas/pyarrow, pandera, pytest.
- Patterns: immutable raw captures, provenance manifests, canonical identity, capability probes.
- Pitfalls: score semantics, identity mismatches, fixture drift, odds availability, public-repository leakage.

**Confidence breakdown:**
- Standard stack: HIGH - official docs and existing verified project research.
- Architecture: HIGH - stable data-engineering patterns aligned with project constraints.
- Dataset semantics: HIGH - martj42 official repository README.
- Live source availability: MEDIUM - must be probed during execution.
- Code examples: HIGH for kagglehub/pandera; HIGH for simple local utilities.

**Research date:** 2026-06-11
**Valid until:** 2026-06-18 for fixture/odds availability; 2026-07-11 for stable library patterns.
</metadata>

---

*Phase: 01-fundacion-de-datos*
*Research completed: 2026-06-11*
*Ready for planning: yes*
