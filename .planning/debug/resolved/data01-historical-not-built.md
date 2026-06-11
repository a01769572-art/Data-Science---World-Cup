---
status: resolved
trigger: "DATA-01 was marked complete although the real martj42 historical dataset was never downloaded or materialized."
created: 2026-06-11
updated: 2026-06-11
---

# Debug Session: DATA-01 Historical Dataset Not Built

## Symptoms

### Expected Behavior

Download the real martj42 dataset and create `data/processed/historical_matches.parquet`.

### Actual Behavior

Only temporary test fixtures were processed. The real parquet artifact does not exist.

### Error Messages

None. Automated tests passed and produced a false positive.

### Timeline

The issue originated during execution of Phase 01 Plan 02.

### Reproduction

Run the current DATA-01 acceptance checks. They pass even though the real historical dataset is absent.

## Current Focus

hypothesis: Confirmed and fixed. Fixture-only completion evidence omitted production materialization and complete historical identity coverage.
test: Run real acquisition/materialization, explicit DATA-01 acceptance, full pytest suite, Ruff, and provenance verification.
expecting: Real parquet contains every completed raw result, all source identities resolve exactly, and every checksum matches provenance.
next_action: none
reasoning_checkpoint: Snapshot 2026-06-11 materialized 49,405 completed matches across 336 identities; 72 unplayed fixtures were excluded with strict partial-score rejection.
tdd_checkpoint:

## Evidence

- timestamp: 2026-06-11T00:00:01Z
  observation: Fixture-focused DATA-01 tests pass (6 passed) while data/processed/historical_matches.parquet and data/raw/martj42 are absent.
  implication: Existing automated evidence can mark DATA-01 complete without its required production artifact.
- timestamp: 2026-06-11T00:00:02Z
  observation: Authored registry contains 48 teams and 48 martj42 aliases.
  implication: Coverage gate measures World Cup participants, not the historical source domain.
- timestamp: 2026-06-11T00:00:03Z
  observation: Real kagglehub snapshot downloaded successfully with 49,477 results, 678 shootouts, and 336 distinct team names.
  implication: Network acquisition is viable and exposes a much larger identity domain than fixtures.
- timestamp: 2026-06-11T00:00:04Z
  observation: Real build stops at unknown alias martj42/Wales on 1877-03-05.
  implication: Production materialization was never exercised before DATA-01 completion.

## Eliminated

- hypothesis: Kaggle authentication prevents real acquisition.
  evidence: Public kagglehub download completed successfully without an API key.
- hypothesis: The existing 48-team registry is sufficient because martj42 normalizes names.
  evidence: Snapshot contains 336 exact names and the first real build failed on Wales.

## Specialist Review

specialist_hint: python
requested_skill: python-expert-best-practices-code-review
result: SUGGEST_CHANGE - requested skill was unavailable; fallback gsd-code-review identified source-version path validation and manifest path anchoring improvements, both applied before completion.

## Resolution

root_cause: DATA-01 was marked complete from mocked download and tiny fixture round-trips; there was no production command or acceptance gate, and the identity registry covered only 48 names instead of the real snapshot's 336.
fix: Added exact historical identities, aggregate coverage auditing, safe end-to-end materialization, raw and derived provenance verification, strict handling of unplayed rows, and a real-artifact acceptance test.
verification: Real materialization produced 49,405 rows and SHA-256 067ada821b9e33e987525f66e668e89301b9945b7f7526509868dd8c7b22b239; acceptance test passed; full suite 63 passed; Ruff passed.
files_changed: src/cdd_mundial/data/{contracts,identities,ingest_martj42}.py; data/external/{historical_teams,team_aliases}.csv; data/raw/martj42/2026-06-11/*; data/metadata/*martj42* provenance; tests/test_{ingest_martj42,data01_acceptance}.py; pyproject.toml; GSD requirement/state/summary/validation metadata.
