---
phase: 03-simulador-del-torneo
plan: 01
subsystem: regulatory-evidence
tags: [fifa-2026, regulations, provenance, third-place-mapping, fail-closed, annexe-c]

requires:
  - phase: 01-fundacion-de-datos
    plan: 04
    provides: frozen fixture_2026.csv with the eight round-of-32 third-place slot tokens
provides:
  - Pinned official FIFA World Cup 26 regulations evidence (URL, timestamp, SHA-256, article and annex pointers)
  - Independent expected-combinations fixture with all 495 C(12,8) qualifying-group sets
  - Reviewed official best-third mapping (495 Annexe C cases keyed by real fixture match_id positions)
  - Fail-closed stdlib validator (provenance / mapping / all modes)
affects: [03-02, 03-03, rules_fifa, slot-resolution, SIM-01]

tech-stack:
  added: [pypdf (dev-only, extraction tooling, not a runtime dependency)]
  patterns: [deterministic sorted-key JSON provenance, fail-closed contract validator, sha256 cross-referenced fixtures]

key-files:
  created:
    - data/metadata/fifa_2026_regulations.provenance.json
    - tests/fixtures/tournament/third_place_expected_combinations.json
    - tests/fixtures/tournament/third_place_mapping_official.json
    - tests/validators/validate_third_place_mapping.py
  modified:
    - .gitignore

key-decisions:
  - "Official 2026 tie-break cascade (Art. 13) differs from the assumed wording: head-to-head criteria come FIRST, and the final fallback is FIFA/Coca-Cola Men's World Ranking editions, NOT drawing of lots"
  - "Raw FIFA PDF stays uncommitted (data/raw/regulations/ gitignored); committed evidence is the extracted manifest plus sha256-cross-referenced fixtures"
  - "Expected combinations are independently authored from Article 12.6's '495 different possible combinations' statement plus C(12,8) enumeration, never derived from the parsed mapping table"
  - "SIM-01 is NOT marked complete: this plan delivers its regulatory verification prerequisite; the executable rules_fifa.py and unit tests land in later Phase 3 plans"

requirements-completed: []

duration: 14min
completed: 2026-06-13
---

# Phase 3 Plan 01: Regulatory Evidence Gate Summary

**Official FIFA World Cup 26 regulations (MAY 2026 edition) pinned from digitalhub.fifa.com with SHA-256 provenance; all 495 Annexe C best-third combinations extracted, structurally verified, cross-checked against rendered page images, and guarded by a fail-closed stdlib validator wired to the frozen fixture.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-13T00:11:27Z
- **Completed:** 2026-06-13T00:25:00Z
- **Tasks:** 2 (+1 fix commit)
- **Files modified:** 5

## Accomplishments

- Downloaded the official `FWC2026_regulations_EN.pdf` (98 physical pages, MAY 2026 edition) directly from FIFA's digital hub over HTTPS and pinned it locally with SHA-256 `bad4ea83cf1f51055598b0c12c3dab280a78777e08a623b9e9098508b4ecc8d9`.
- Committed `data/metadata/fifa_2026_regulations.provenance.json` with article pointers (Art. 10 cards, Art. 12.5-12.6 R32 pairings, Art. 13 tie-breaks and best-third ranking, Art. 14 ET/penalties) and Annexe C pointers (495 options, physical pages 80-98), plus reviewed-extraction metadata.
- Authored `third_place_expected_combinations.json`: all 495 C(12,8) qualifying-group sets, lexicographic, justified by Article 12.6's official count statement — independent of the mapping table by construction.
- Extracted and committed `third_place_mapping_official.json`: 495 Annexe C cases, each assigning the eight qualifying third-place groups to explicit real fixture selector positions (match_id + away side), with provenance back to the manifest.
- Extraction integrity evidence: 495 contiguous options; 8 distinct groups per row; parsed qualifying sets equal the complete C(12,8) enumeration; every assignment allowed by its real fixture token; 14 rows cross-checked character-by-character against rendered page images with zero mismatches.
- Built `tests/validators/validate_third_place_mapping.py` (stdlib-only, PowerShell-safe): provenance mode (official FIFA HTTPS host, UTC timestamp, 64-hex sha256, pointer and review fields, local-PDF checksum when present) and mapping mode (selector cross-check against `fixture_2026.csv`, exhaustive coverage vs the independent expected set, per-case bijection, token compatibility, sha256 cross-references). Six tamper scenarios (removed case, duplicated combination, duplicated group, token-incompatible assignment, unknown selector, tampered sha) all fail closed with precise messages.

## Key Regulatory Findings (affect later Phase 3 plans)

1. **The official tie-break order differs from the assumed cascade.** Article 13 Step 1 applies head-to-head criteria FIRST (points, GD, goals among teams concerned), Step 2 reapplies them then falls to overall GD, overall GF, and the team conduct score, and Step 3's fallback is the FIFA/Coca-Cola Men's World Ranking (most recent, then preceding editions) — **there is NO drawing of lots** in the 2026 group-ranking text. SIM-01's current wording ("puntos -> DG -> GF -> head-to-head -> fair play -> sorteo") and D-03's "drawing of lots" must follow the official text when `rules_fifa.py` is implemented.
2. **Conduct score, not Annexe B, breaks ties.** The fair-play tie-break input is the conduct score inside Article 13 (yellow -1, indirect red -3, direct red -4, yellow + direct red -5, one deduction per player per match). Annexe B's Fair Play Contest is a separate award.
3. **Best-third ranking** (Art. 13, p. 27): points, GD, GF in all group matches, conduct score, then FIFA ranking editions. Head-to-head never applies across groups.
4. **Annexe C is the unique assignment authority.** The fixture tokens (`3ABCDF` etc.) constrain but do not determine assignments; the committed 495-case lookup resolves every combination exactly once.

## Task Commits

1. **Task 1: official-rule provenance manifest + validator provenance mode** - `0bd8faa`
2. **Task 2: independent expected combinations + reviewed official mapping + validator mapping mode** - `62f8c80`
3. **Fix: extraction timestamps recorded in the future corrected to actual times** - `6ac5d4e`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical protection] Gitignored `data/raw/regulations/`**
- **Found during:** Task 1
- **Issue:** The raw FIFA PDF would have been committable; redistribution terms are unclear and the repo constraint forbids versioning restricted-license data.
- **Fix:** Added `data/raw/regulations/` to `.gitignore`; the committed evidence is the extracted manifest (D-04 preference).
- **Files modified:** `.gitignore`
- **Commit:** `0bd8faa`

**2. [Rule 3 - Blocking tooling gap] Installed pypdf into the venv for annex extraction**
- **Found during:** Task 1/2 preparation
- **Issue:** No PDF text-extraction library existed locally and the 495-row Annexe C table cannot be transcribed by hand reliably.
- **Fix:** `pip install pypdf` (dev-time only). Not added to `pyproject.toml` because the runtime path and the committed validator are stdlib-only; the manifest documents the extraction method for reproducibility.
- **Files modified:** none committed
- **Commit:** n/a

**3. [Rule 1 - Bug] Extraction timestamps recorded in the future**
- **Found during:** Summary preparation
- **Issue:** `extracted_at_utc` values (00:30Z/00:40Z) were estimates that landed after the actual wall-clock time (00:22Z) — impossible provenance.
- **Fix:** Corrected to the actual extraction times (00:15Z/00:19Z); re-ran `all` validation.
- **Files modified:** `data/metadata/fifa_2026_regulations.provenance.json`, `tests/fixtures/tournament/third_place_mapping_official.json`
- **Commit:** `6ac5d4e`

## Verification

```text
.\.venv\python.exe tests/validators/validate_third_place_mapping.py all
-> PASS: all checks satisfied (provenance + mapping)
```

Six negative (tampering) scenarios verified to exit 1 with explicit reasons; restored artifacts pass. Existing contract tests (`tests/test_fixture.py`, `tests/test_provenance.py`) remain green (14 passed).

## Requirements Status

- **SIM-01:** NOT marked complete. This plan delivers the regulatory verification prerequisite (official rule evidence + the unique best-third assignment authority). The executable `rules_fifa.py`, slot resolution, and historical unit tests land in later Phase 3 plans, which must consume these artifacts and follow the official Article 13 order (see Key Regulatory Findings).

## Known Stubs

None — all artifacts carry real extracted official data; the validator's checks are fully implemented.

## Self-Check: PASSED

- `data/metadata/fifa_2026_regulations.provenance.json` — FOUND
- `tests/fixtures/tournament/third_place_expected_combinations.json` — FOUND
- `tests/fixtures/tournament/third_place_mapping_official.json` — FOUND
- `tests/validators/validate_third_place_mapping.py` — FOUND
- Commits `0bd8faa`, `62f8c80`, `6ac5d4e` — FOUND in git log
