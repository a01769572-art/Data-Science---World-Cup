---
phase: 01-fundaci-n-de-datos
plan: "02"
subsystem: data-ingestion
tags: [python, pandas, pandera, kagglehub, parquet, canonical-identities]

requires:
  - phase: 01-fundaci-n-de-datos
    provides: Strict dataframe contracts, immutable captures, and provenance manifests
provides:
  - Canonical registry and exact source-keyed aliases for 48 World Cup participants
  - Deterministic team resolution with explicit unknown and ambiguity failures
  - Immutable martj42 acquisition and validated historical parquet construction
  - Integration gates for identity coverage, score semantics, and raw-file checksums
affects: [phase-01-source-ingestion, phase-02-models, phase-03-simulator]

tech-stack:
  added: []
  patterns: [exact identity resolution, immutable versioned acquisition, semantic score preservation]

key-files:
  created:
    - data/external/teams.csv
    - data/external/team_aliases.csv
    - src/cdd_mundial/data/identities.py
    - src/cdd_mundial/data/ingest_martj42.py
    - tests/fixtures/martj42/results.csv
    - tests/fixtures/martj42/shootouts.csv
    - tests/test_identities.py
    - tests/test_ingest_martj42.py
    - tests/test_data_foundation.py
  modified: []

key-decisions:
  - "Canonical IDs are authored lowercase ASCII slugs and are never derived during ingestion."
  - "Martj42 scores remain full-time including extra time; shootout winners are stored separately."
  - "Historical match IDs use date and original source names with deterministic collision suffixes."

patterns-established:
  - "Every external name resolves by exact source, source name, and validity date or processing stops."
  - "Historical source files are copied unchanged into versioned raw directories before transformation."

requirements-completed: [DATA-01, DATA-02]

duration: 4min
completed: 2026-06-11
---

# Phase 1 Plan 2: Canonical Identities and Martj42 History Summary

**Exact canonical team identities and immutable martj42 ingestion into schema-validated parquet with shootout semantics preserved**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-11T17:50:57Z
- **Completed:** 2026-06-11T17:55:21Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Authored 48 stable team IDs with complete reviewed aliases for martj42, Elo, FIFA, fixture, and odds source labels.
- Added exact date-aware resolution that rejects unknown, ambiguous, duplicate, and orphaned identities.
- Added versioned martj42 acquisition with immutable copies, CC0 provenance, and validated parquet output.
- Preserved source scores unchanged while storing shootout advancement in a separate nullable canonical field.

## Task Commits

1. **Task 1: Create canonical teams, aliases, and deterministic resolver** - `eea2053` (feat)
2. **Task 2: Acquire and parse martj42 with exact score semantics** - `e418a89` (feat)
3. **Task 3: Enforce identity and historical-data gates** - `b75f7a4` (test)

## Files Created/Modified

- `data/external/teams.csv` - Canonical 48-team registry.
- `data/external/team_aliases.csv` - Reviewed aliases for all five Phase 1 source labels.
- `src/cdd_mundial/data/identities.py` - Strict exact resolver and coverage reporting.
- `src/cdd_mundial/data/ingest_martj42.py` - Immutable acquisition and historical parquet builder.
- `tests/fixtures/martj42/results.csv` - Ordinary, neutral, and drawn knockout match fixtures.
- `tests/fixtures/martj42/shootouts.csv` - Separate shootout winner fixture.
- `tests/test_identities.py` - Identity registry and resolver unit gates.
- `tests/test_ingest_martj42.py` - Acquisition and score-semantics contract tests.
- `tests/test_data_foundation.py` - Cross-module identity, parquet, and checksum integration gates.

## Decisions Made

- Match IDs retain original source-name identity in their deterministic key and add numeric suffixes only for collisions.
- `result_after_extra_time` is true only when the row joins to a documented shootout in the available martj42 inputs.
- Download tests mock kagglehub and use local fixtures, so normal verification never requires network access or credentials.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository-local GSD SDK was absent; metadata operations use the compatible bundled `gsd-tools.cjs` CLI.
- A concurrent user/orchestrator commit added `.gitignore` and `launch_jupyter_mcp.bat`; those files and `.claude/` were left untouched and excluded from plan commits.
- Initial Git staging was blocked by sandbox permissions; the same scoped commit command succeeded after approval.

## User Setup Required

None - tests mock acquisition and require no Kaggle authentication.

## Verification

- `.\.venv\python.exe -m pytest -q -p no:cacheprovider tests\test_identities.py tests\test_ingest_martj42.py tests\test_data_foundation.py` - 12 passed.
- `.\.venv\python.exe -m ruff check src\cdd_mundial\data tests` - all checks passed.
- Registry inspection reported 48 World Cup rows, 48 unique team IDs, 48 martj42 aliases, and all five source labels.
- Parquet integration gates assert non-null canonical IDs, distinct teams, nonnegative scores, and unchanged raw fixture checksums.

## Known Stubs

None.

## Next Phase Readiness

- Canonical identity and historical match foundations are ready for current Elo and remaining Phase 1 source ingestion.
- No blockers were introduced by this plan.

## Self-Check: PASSED

- All nine key files exist.
- Task commits `eea2053`, `e418a89`, and `b75f7a4` exist in Git history.
- All task and plan-level verification commands pass with `.venv\python.exe`.

---
*Phase: 01-fundaci-n-de-datos*
*Completed: 2026-06-11*
