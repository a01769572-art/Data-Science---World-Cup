---
phase: 01-fundaci-n-de-datos
plan: "04"
subsystem: data-ingestion
tags: [python, the-odds-api, odds, de-margining, pandera, secrets]

requires:
  - phase: 01-fundaci-n-de-datos
    provides: Canonical team identities, frozen 2026 fixture, strict dataframe contracts, bounded HTTP acquisition
provides:
  - Capability-probed odds provider policy (The Odds API v4, sport_key soccer_fifa_world_cup)
  - Multiplicative de-margining of three-way decimal prices (demargin_decimal_odds)
  - Canonical benchmark builder linking provider quotes to fixture match IDs (build_odds_benchmark)
  - Live benchmark snapshot data/processed/odds_2026.parquet (1385 rows, 71 fixtures, 24 bookmakers)
  - Manual CSV fallback template with the canonical odds contract
affects: [phase-02-models, phase-04-daily-pipeline, phase-06-evaluation]

tech-stack:
  added: []
  patterns:
    [
      env-only secrets with full redaction,
      raw payloads quarantined to gitignored paths,
      strict pandera gate before parquet serialization,
      unordered team-pair plus commence-time fixture linkage,
    ]

key-files:
  created:
    - data/external/odds_2026_template.csv
    - tests/fixtures/odds/odds.json
  modified:
    - src/cdd_mundial/data/ingest_odds.py
    - src/cdd_mundial/data/contracts.py
    - src/cdd_mundial/data/identities.py
    - data/external/team_aliases.csv
    - data/metadata/odds_provider_policy.json
    - tests/test_odds.py
    - tests/test_contracts.py

key-decisions:
  - "The Odds API v4 confirmed as provider: authenticated probe found sport_key soccer_fifa_world_cup with 71/71 three-way h2h events."
  - "Raw provider payloads are stored only under gitignored data/raw/odds/; only de-margined derivatives are publishable per provider terms."
  - "Exchange lay quotes (h2h_lay) are never consumed as back prices."
  - "Multiple reviewed alias name variants per (team, source) are legitimate coverage; resolution stays keyed by exact source_name."

patterns-established:
  - "Market quotes are accepted only as exact home/draw/away three-outcome h2h back markets; everything else raises OddsValidationError."
  - "Benchmark rows are oriented to the fixture's home/away designation by resolved team ID, immune to provider side-swaps."

requirements-completed: [DATA-05]

duration: 35min
completed: 2026-06-12
---

# Phase 1 Plan 4: Odds Benchmark Summary

**De-margined three-way World Cup market probabilities from The Odds API v4, linked to canonical fixture IDs: 1385 validated rows over all 71 upcoming matches from 24 bookmakers, with secrets and raw payloads provably excluded from the public repo**

## Performance

- **Duration:** ~35 min active execution across two sessions, excluding the credential checkpoint wait
- **Started:** 2026-06-11T23:15:00Z (Task 1) / continuation 2026-06-11T23:42:25Z
- **Completed:** 2026-06-12T00:05:00Z
- **Tasks:** 2 implementation tasks plus 1 human-action checkpoint (ODDS_API_KEY setup)
- **Files modified:** 10 unique files

## Accomplishments

- Probed The Odds API v4 with the personal credential: exactly one active men's FIFA World Cup soccer competition (`soccer_fifa_world_cup`), 71 events, all 71 with exact home/draw/away three-way h2h markets. Evidence and storage policy recorded in `data/metadata/odds_provider_policy.json`.
- Captured both raw provider payloads under gitignored `data/raw/odds/` in the same two requests as the probe (frugal with the 500-requests/month free tier).
- Implemented `demargin_decimal_odds` (multiplicative normalization; rejects non-finite or <= 1.0 prices) and `build_odds_benchmark` (provider JSON or manual CSV, exact three-way gate, alias resolution via source `odds`, fixture linkage by unordered team pair + commence-time tolerance, staleness rejection, raw probabilities + overround + normalized probabilities, `OddsSchema` validation before parquet).
- Materialized the production benchmark from the captured live payload: 1385 rows, 71 distinct `match_id`s, 24 bookmakers, max overround 1.198, probability sums exact to 2.2e-16, zero null canonical IDs.
- Authored the manual fallback template `data/external/odds_2026_template.csv` so a provider outage degrades to an editable CSV, never a blocked pipeline.
- 27 odds tests pass (probe, secrets, policy, de-margining, linkage, orientation, lay exclusion, staleness, manual fallback); full suite 90 passed; ruff clean.

## Task Commits

1. **Task 1: Probe provider capability and record the storage policy** - `7597c71` (feat) — executed pre-checkpoint by the prior session
2. **Checkpoint: ODDS_API_KEY credential setup** - completed by user ("done"); authenticated probe verified
3. **Resume: record live-probed sport key in provider policy** - `d6abc99` (docs)
4. **Task 2: Normalize three-way prices and build the benchmark snapshot** - `01900f0` (feat)

## Files Created/Modified

- `src/cdd_mundial/data/ingest_odds.py` - Probe, de-margining, benchmark builder, CLI materializer (`python -m cdd_mundial.data.ingest_odds`).
- `src/cdd_mundial/data/contracts.py` - `OddsSchema` gains nullable `provider_update_utc` freshness column.
- `src/cdd_mundial/data/identities.py` - `build_coverage_report` accepts multiple reviewed name variants per source.
- `data/external/odds_2026_template.csv` - Header-only canonical manual import contract (no fake data committable).
- `data/external/team_aliases.csv` - Live provider variants: "Bosnia & Herzegovina", "Curaçao".
- `data/metadata/odds_provider_policy.json` - Provider, terms, storage policy, authenticated probe evidence, capture paths.
- `tests/fixtures/odds/odds.json` - Offline benchmark fixture including an `h2h_lay` decoy and a side-swapped event.
- `tests/test_odds.py` - 27 gates: probe, secret redaction, policy, de-margin math, linkage, rejections, manual fallback.
- `tests/test_contracts.py` - Minimal odds frame updated for the new freshness column.

## Decisions Made

- One benchmark row per (event, bookmaker) back quote; downstream consumers aggregate (median/consensus) as needed.
- `overround` stores the booksum of raw implied probabilities (e.g. 1.05), making margin = overround - 1 trivially recoverable.
- Quotes are oriented to the fixture's home/away designation by resolved team ID, so provider side-swaps cannot flip probabilities.
- Stale quotes (provider update older than 24h before capture, parameterizable) raise instead of silently entering the benchmark.
- The CLI materializer recovers `captured_at` from the capture filename stamp, keeping reproducibility from raw + code without re-querying the API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reviewed alias variants for live provider team names**
- **Found during:** Task 2 (live payload inspection)
- **Issue:** Provider sends "Bosnia & Herzegovina" and "Curaçao" (U+00E7); the authored `odds` aliases only listed "Bosnia and Herzegovina" and ASCII "Curacao", so 4 of 71 events would fail resolution.
- **Fix:** Added two reviewed alias variant rows mapping to the same canonical IDs.
- **Files modified:** `data/external/team_aliases.csv`
- **Commit:** `01900f0`

**2. [Rule 2 - Missing critical functionality] `provider_update_utc` column in strict OddsSchema**
- **Found during:** Task 2 design
- **Issue:** The plan requires storing the provider update time (freshness field, threat T-01-07), but `OddsSchema` is `strict=True` and had no such column, so the value could not be persisted.
- **Fix:** Added nullable `provider_update_utc` (must end in `Z`) to `OddsSchema`.
- **Files modified:** `src/cdd_mundial/data/contracts.py`
- **Commit:** `01900f0`

**3. [Rule 3 - Blocking issue] Pre-existing tests broken by in-scope changes**
- **Found during:** Task 2 full-suite verification
- **Issue:** (a) `test_contracts.py` minimal odds frame lacked the new column; (b) `test_identities.py` coverage test failed because `build_coverage_report` treated multiple alias rows per (team, source) as unresolved, conflicting with legitimate name variants.
- **Fix:** Added the column to the minimal frame; changed `build_coverage_report` to treat >= 1 reviewed alias as resolved (true duplicates remain blocked by `TeamAliasesSchema` uniqueness and `AmbiguousTeamError`).
- **Files modified:** `tests/test_contracts.py`, `src/cdd_mundial/data/identities.py`
- **Commit:** `01900f0`

---

**Total deviations:** 3 auto-fixed (1 bug, 1 missing critical functionality, 1 blocking issue)
**Impact on plan:** All fixes serve the plan's own must-haves (full live coverage, freshness metadata, green suite); no scope creep.

## Authentication Gates

- **Gate:** `ODDS_API_KEY` for The Odds API v4 (Task 1 → checkpoint:human-action).
- **Resolution:** User placed the key in the gitignored repo-root `.env`; orchestrator verified format. Authenticated probe then succeeded (HTTP 200, 71 events).
- **Secret hygiene verified:** key value grepped against all committed/generated files and both raw captures — zero occurrences; probe/build error paths redact the key; policy JSON contains no key material.

## Requirements Status

- **DATA-05: Complete** — de-margined market probabilities benchmark live from a real source with manual fallback.
- **DATA-02: already complete** — reinforced: all 48 participants now also resolve through live `odds` provider names.
- **DOC-03: still pending** — this plan upholds "no keys, no restricted data" but the public GitHub repo + portfolio README remain outstanding (tracked in STATE blockers).

## Issues Encountered

- The venv python lives at `.venv/python.exe` (conda-style layout), not `.venv/Scripts/python.exe`.
- The provider exposes exchange `h2h_lay` markets alongside `h2h` (betfair); the builder ignores them as price sources and rejects any bookmaker offering no `h2h` back market at all.
- The unrelated untracked `.claude/` directory and `01-UAT.md` were left untouched.

## User Setup Required

None — the credential gate was completed; the benchmark regenerates offline from captured raw payloads via `python -m cdd_mundial.data.ingest_odds`.

## Verification

- `.\.venv\python.exe -m pytest -q tests/test_odds.py` — 27 passed.
- `.\.venv\python.exe -m pytest -q tests/` — 90 passed.
- `.\.venv\python.exe -m ruff check src tests` — all checks passed.
- Policy JSON records provider, terms, storage rules, and authenticated probe evidence with the resolved sport key.
- Production benchmark: 1385 rows / 71 fixtures / 24 bookmakers; 0 null match or team IDs; max |prob sum - 1| = 2.2e-16.
- `git ls-files data/raw/odds data/processed` — empty; secret grep across src/tests/data/external/data/metadata/.planning — clean.

## Known Stubs

None.

## Next Phase Readiness

- Phase 2 (models) and Phase 6 (evaluation) can consume `data/processed/odds_2026.parquet` as the market benchmark, regenerable from raw captures.
- Plan 01-05 remains; DATA-03 (Elo recomputation from history) and DATA-06 (live results ingestion) are still open in Phase 1 scope.

## Self-Check: PASSED

- Created/modified files exist: ingest_odds.py, contracts.py, identities.py, odds_2026_template.csv, odds.json, team_aliases.csv, policy JSON, both test files.
- Commits `7597c71`, `d6abc99`, `01900f0` exist in git history.
- All verification commands pass with `.venv/python.exe`.

---
*Phase: 01-fundaci-n-de-datos*
*Completed: 2026-06-12*
