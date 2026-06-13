---
phase: 03-simulador-del-torneo
plan: "04"
subsystem: simulation
tags: [fifa-rules, tiebreakers, bracket-resolution, pure-functions, pandas]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Pinned FIFA 2026 regulations (Art. 13 cascade) and reviewed Annexe C third-place mapping (495 combinations) with provenance"
  - phase: 03-03
    provides: "Wave 0 RED contract tests (test_rules_fifa.py, test_slot_resolution.py) and tournament JSON fixtures"
provides:
  - "rules_fifa.py: pure group standings, Article 13 tie-break cascade, and best-third ranking"
  - "slots.py: fixture-token parsing (1A/2L, 3ABCDF, W74, L101) and official R32 third-place resolution"
  - "Public cdd_mundial.simulation API for rules and slot resolution"
affects: [03-05-engine, 03-06-outputs, simulation, monte-carlo]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recursive tie-break resolution via descending key-blocks (overall -> head-to-head -> conduct -> FIFA editions)"
    - "Official mapping consumed (never re-derived) with fail-loud token-compatibility validation"
    - "lru_cache on regulation-evidence JSON load keyed by path string"

key-files:
  created:
    - src/cdd_mundial/simulation/rules_fifa.py
    - src/cdd_mundial/simulation/slots.py
  modified:
    - src/cdd_mundial/simulation/__init__.py

key-decisions:
  - "Tie-breaks use a recursive block-splitter on descending sort keys so head-to-head reapplication and successive FIFA editions fall out naturally; branchy dict logic chosen over NumPy vectorization because the cascade is inherently conditional."
  - "rank_best_thirds reads only points/GD/GF/conduct/FIFA and structurally ignores cross_group_head_to_head_points (third places never met)."
  - "Residual ties that cannot be resolved from supplied official data raise loudly; drawing of lots is not implemented (no such rule in the 2026 regulation, D-03)."

patterns-established:
  - "Pure deterministic rules functions returning ordered team-id lists, no hidden state"
  - "Slot resolver keeps frozen fixture tokens authoritative (D-06) and validates assignments against token families"

requirements-completed: [SIM-01]

# Metrics
duration: 12min
completed: 2026-06-13
---

# Phase 3 Plan 04: Rules and Slot Resolution Layer Summary

**Pure FIFA 2026 Article 13 tie-break cascade (overall -> head-to-head -> conduct -> successive FIFA editions) plus official Annexe C third-place slot resolution against the frozen fixture, closing SIM-01.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-13
- **Completed:** 2026-06-13
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- `slots.py` parses all four knockout token families (`1A`/`2L`, `3ABCDF`, `W74`, `L101`) and resolves Round-of-32 participants, selecting third-place groups from the reviewed official mapping while keeping fixture tokens authoritative.
- `rules_fifa.py` implements `calculate_group_table`, `rank_group` (full Art. 13 cascade with residual head-to-head reapplication), and `rank_best_thirds`.
- All 20 Wave 0 SIM-01 gate tests pass (8 slot + 12 rules); the 67-test simulation subsuite is green.

## Task Commits

Each task was committed atomically (tests were authored RED in 03-03; these are the GREEN implementations):

1. **Task 1: Fixture-token parsing and official R32 slot resolution** - `0f29674` (feat)
2. **Task 2: Pure FIFA group and best-third rules** - `5ee0a83` (feat)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified
- `src/cdd_mundial/simulation/slots.py` - Token parsing and official third-place mapping consumption with fail-loud token-compatibility checks.
- `src/cdd_mundial/simulation/rules_fifa.py` - Pure group table and the recursive Article 13 ranking cascade plus best-third ranking.
- `src/cdd_mundial/simulation/__init__.py` - Re-exports the new public rules and slot functions.

## Decisions Made
- Implemented the cascade as a recursive descending-key block splitter (`_group_by_key` -> `_resolve_head_to_head` -> `_resolve_tail` -> `_resolve_by_fifa_ranking`). This makes head-to-head residual reapplication and "use the next FIFA edition only on a remaining tie" emerge from the structure rather than ad hoc branching.
- Chose branchy dict-based logic over NumPy vectorization for the tie-break engine (PATTERNS suggested NumPy-first, but the cascade is inherently conditional and per-block; the analog `metrics.py` NumPy style does not fit). The pure-function, deterministic-output contract from the patterns is preserved.
- `resolve_third_place_assignments` reads the official mapping and validates each assigned group lives in the corresponding fixture slot token (`group in token[1:]`), rejecting absent/duplicate/incompatible cases loudly (T-03-10).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Exported new public functions from the simulation package**
- **Found during:** Tasks 1 and 2
- **Issue:** The plan listed only the module files, but the package `__init__.py` follows an explicit-re-export pattern (matching `models/__init__.py`); leaving the new functions unexported would make `cdd_mundial.simulation` inconsistent for the downstream engine/notebook.
- **Fix:** Added `slots` and `rules_fifa` re-exports and `__all__` entries.
- **Files modified:** `src/cdd_mundial/simulation/__init__.py`
- **Verification:** Full SIM-01 gate and the 67-test simulation subsuite pass.
- **Committed in:** `0f29674` and `5ee0a83` (task commits)

**2. [Rule 1 - Bug] Removed unused `numpy` import in rules_fifa.py**
- **Found during:** Task 2
- **Issue:** Initial draft imported `numpy` (PATTERNS NumPy-first hint) but the final dict-based cascade does not use it, leaving a dead import.
- **Fix:** Dropped the `import numpy as np` line before committing.
- **Files modified:** `src/cdd_mundial/simulation/rules_fifa.py`
- **Verification:** Tests pass; no unused-import.
- **Committed in:** `5ee0a83` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 missing-critical export consistency, 1 dead-import cleanup)
**Impact on plan:** Both keep the package consistent and clean. No scope creep; no architectural change.

## Issues Encountered
None. The Bash tool mangled the Windows venv path on a literal `.\.venv\python.exe` invocation; using the POSIX form `./.venv/python.exe` from the project root ran pytest correctly.

## TDD Gate Compliance
This plan is the GREEN half of a split TDD cycle: the failing contract tests (`test_rules_fifa.py`, `test_slot_resolution.py`) were committed in 03-03 (`35cf9f0`, `d32f191`); plan 03-04 supplies the implementations that turn them green. RED -> GREEN sequence is satisfied across the two plans; no separate REFACTOR commit was needed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The pure rules and bracket-resolution layer is production-ready and independently tested, ready for the vectorized Monte Carlo engine (SIM-02+) to consume group rankings, best-third ranking, and R32 slot resolution.
- No blockers introduced.

## Self-Check: PASSED

- FOUND: src/cdd_mundial/simulation/slots.py
- FOUND: src/cdd_mundial/simulation/rules_fifa.py
- FOUND: .planning/phases/03-simulador-del-torneo/03-04-SUMMARY.md
- FOUND commit: 0f29674
- FOUND commit: 5ee0a83

---
*Phase: 03-simulador-del-torneo*
*Completed: 2026-06-13*
