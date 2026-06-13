---
phase: 03-simulador-del-torneo
plan: "03"
subsystem: testing
tags: [fifa-2026, rules, slots, pytest, tdd, red-gate, best-thirds]

requires:
  - phase: 03-simulador-del-torneo
    plan: "01"
    provides: official regulations provenance and reviewed 495-case Annexe C mapping
  - phase: 03-simulador-del-torneo
    plan: "02"
    provides: simulation package bootstrap and frozen fixture/state contracts
provides:
  - Reviewable historical and synthetic fixtures for the official Article 13 ranking sequence
  - Failing pure-rules tests for head-to-head, residual reapplication, conduct score, and successive FIFA ranking editions
  - Failing slot tests consuming all 495 reviewed best-third assignments and the frozen fixture topology
  - PowerShell-safe validator that accepts only the intended missing rules_fifa or slots behavior
affects: [03-04, rules_fifa, slots, SIM-01]

tech-stack:
  added: []
  patterns:
    - Explicit fixture expectations independent from production ranking logic
    - Fail-closed RED validator over selected pytest nodes
    - Frozen fixture tokens plus reviewed mapping as the slot-resolution authority

key-files:
  created:
    - tests/fixtures/tournament/wc2018_group_h.json
    - tests/fixtures/tournament/two_way_head_to_head.json
    - tests/fixtures/tournament/three_way_tie.json
    - tests/fixtures/tournament/four_way_tie.json
    - tests/fixtures/tournament/fair_play_tie.json
    - tests/fixtures/tournament/fifa_ranking_tie.json
    - tests/fixtures/tournament/best_thirds.json
    - tests/test_rules_fifa.py
    - tests/test_slot_resolution.py
    - tests/validators/assert_phase03_red.py
  modified: []

key-decisions:
  - "The Wave 0 contract exposes calculate_group_table, rank_group, and rank_best_thirds as pure rules functions for 03-04 to implement"
  - "The slot contract resolves group-position, third-place, winner, and loser tokens from frozen fixture context; the 495-case mapping is consumed rather than re-derived"
  - "The official final fallback remains successive FIFA ranking editions; no drawing-of-lots behavior is tested or permitted"
  - "SIM-01 remains pending until 03-04 implements rules_fifa.py and slots.py and turns these RED tests green"

patterns-established:
  - "Expected-order fixtures: every rules case stores expected_order and criterion_note in JSON"
  - "Intentional RED gate: selected nodes must fail only on missing module/export or deliberate NotImplementedError"

requirements-completed: []

duration: 15min
completed: 2026-06-13
---

# Phase 3 Plan 03: Wave 0 Rules and Slot Contracts Summary

**Reviewable FIFA 2026 rules and bracket fixtures now lock the official head-to-head-first cascade, successive-ranking fallback, and all 495 best-third assignments before production implementation begins.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-13T01:31:30Z
- **Completed:** 2026-06-13T01:47:01Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Authored seven explicit JSON fixtures covering World Cup 2018 Group H, two-way head-to-head, residual three-way reapplication, four-way ties, conduct score, successive FIFA ranking editions, and best-third ordering.
- Added pure-rules tests whose expected outputs come directly from fixture payloads, including a deliberate cross-group head-to-head noise field proving best-third ranking ignores it.
- Added slot tests covering every reviewed Annexe C combination, compatibility with the real `3...` token families, and `1A`, `2L`, `W74`, and `L101` fixture references.
- Added `assert_phase03_red.py`, which executes selected pytest nodes and rejects unrelated failures as an invalid RED state.

## Task Commits

1. **Task 1: Create reviewable group and best-third fixtures plus failing rules tests** - `d32f191`
2. **Task 2: Create failing slot-resolution tests from the reviewed official mapping** - `35cf9f0`

## Files Created/Modified

- `tests/fixtures/tournament/*.json` - Explicit match records, conduct scores, ranking editions, criterion notes, and expected orders.
- `tests/test_rules_fifa.py` - Wave 0 contract for pure FIFA group and best-third rules.
- `tests/test_slot_resolution.py` - Wave 0 contract for official mapping and fixture-token resolution.
- `tests/validators/assert_phase03_red.py` - Fail-closed intentional RED-state validator.

## Decisions Made

- Rules tests target `calculate_group_table`, `rank_group`, and `rank_best_thirds`; these remain unimplemented by design.
- Slot tests target reviewed mapping lookup plus context-based token resolution; fixture slot strings remain authoritative.
- `SIM-01` is not complete in this plan because production rules and slot modules are intentionally absent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Planning contract] Removed stale drawing-of-lots wording**
- **Found during:** Plan metadata update
- **Issue:** `ROADMAP.md` still described `03-03` as testing seeded lots and `REQUIREMENTS.md` still defined drawing of lots, contradicting the official 2026 regulations verified in `03-01`.
- **Fix:** Replaced both stale descriptions with conduct score and successive FIFA ranking editions while leaving `SIM-01` pending.
- **Files modified:** `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- **Verification:** Planning metadata now matches the revised plan/context and the authored fixtures.

**Total deviations:** 1 auto-fixed planning-contract bug. **Impact:** No implementation scope added; the fix prevents the next plan from implementing a non-official fallback.

## Issues Encountered

- Git staging initially failed because the sandbox could not create `.git/index.lock`; the same scoped staging and commit commands succeeded after approved escalation.

## TDD Gate Compliance

- Task 1 RED: `d32f191` - selected rules nodes fail only because `cdd_mundial.simulation.rules_fifa` is missing.
- Task 2 RED: `35cf9f0` - selected slot nodes fail only because `cdd_mundial.simulation.slots` is missing.
- GREEN commits are intentionally deferred to `03-04`; this plan is the Wave 0 authoring gate and must end RED.

## Verification

```text
.\.venv\python.exe tests/validators/assert_phase03_red.py all
-> PASS: intended RED state confirmed for rules_fifa and slots

.\.venv\python.exe tests/validators/validate_third_place_mapping.py all
-> PASS: 495 exhaustive, bijective, token-compatible cases

.\.venv\python.exe -m ruff check tests/test_rules_fifa.py tests/test_slot_resolution.py tests/validators/assert_phase03_red.py
-> All checks passed!
```

Production `src/cdd_mundial/simulation/rules_fifa.py` and `slots.py` remain absent, as required.

## Known Stubs

None. Missing production modules are the explicit RED boundary for plan `03-04`, not stubs introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Wave 0 gate is ready for `03-04` to implement the pure rules and slot modules.
- No `03-04` work was executed in this plan.

## Self-Check: PASSED

- All ten created paths exist.
- Commits `d32f191` and `35cf9f0` exist in git history.
- The combined RED validator and official mapping validator pass.

---
*Phase: 03-simulador-del-torneo*
*Completed: 2026-06-13*
