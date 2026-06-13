---
phase: 04-primer-pronostico-pipeline-diario
reviewed: 2026-06-13T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/cdd_mundial/live/__init__.py
  - src/cdd_mundial/live/contracts.py
  - src/cdd_mundial/live/results.py
  - src/cdd_mundial/live/materialization.py
  - src/cdd_mundial/live/predict.py
  - src/cdd_mundial/live/snapshots.py
  - src/cdd_mundial/live/calibration.py
  - src/cdd_mundial/live/report.py
  - src/cdd_mundial/live/pipeline.py
  - src/cdd_mundial/live/__main__.py
findings:
  critical: 2
  warning: 6
  info: 5
  total: 13
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-13
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

The Phase 4 live publication layer is well-structured and the core invariants
(append-only snapshots, fail-closed results loading, atomic publish, dirty-worktree
gate) are largely honored. The staging/publish flow and the calibration ledger
append-guard are solid.

However, two BLOCKER-class defects break stated invariants under realistic inputs:
the completeness gate (`_check_completeness`) silently fails when `--as-of` is a
date-only string (the exact format the CLI advertises and the pipeline derives),
and the "content-addressed / byte-identical replay" reproducibility claim for the
live-training artifact rests on `DataFrame.to_parquet()` producing deterministic
bytes, which it does not guarantee — undermining both the immutable-write guard and
the input fingerprint that drives refit-vs-reuse. Six warnings cover a duplicate
match_id gap, a non-atomic ledger write, an inconsistent dirty-override signature,
and silent benchmark-drop fallbacks.

## Critical Issues

### CR-01: Completeness gate silently passes when `as_of` is a date-only string

**File:** `src/cdd_mundial/live/results.py:159`
**Issue:** `_check_completeness` filters due matches with a **string** comparison:
`fixture["kickoff_utc"] <= as_of`. `kickoff_utc` is a full ISO-8601 instant ending
in `Z` (e.g. `2026-06-15T18:00:00Z`, per `ingest_fixture.py`). The CLI `--as-of`
help advertises "ISO date/time" and a date-only value like `2026-06-15` is a natural
input. Lexicographically, `"2026-06-15T18:00:00Z" <= "2026-06-15"` is **False**
(the longer string sorts after), so every match on the `as_of` day — and any later —
is treated as **not yet due**. The fail-closed completeness gate (D-05) then passes
even though kicked-off matches are missing from the canonical CSV, silently
defeating the central safety invariant of this module. There is no parsing or format
validation of `as_of`, so the failure is silent.
**Fix:** Parse both sides to timezone-aware datetimes before comparing, and reject
malformed `as_of`:
```python
import pandas as pd

def _check_completeness(records, *, fixture, as_of, override):
    if as_of is None:
        return
    if "kickoff_utc" not in fixture.columns:
        raise ValueError("completeness check requires a 'kickoff_utc' fixture column")
    as_of_ts = pd.to_datetime(as_of, utc=True, errors="raise")
    kickoffs = pd.to_datetime(fixture["kickoff_utc"], utc=True, errors="coerce")
    present = {record.match_id for record in records}
    due = fixture.loc[kickoffs.notna() & (kickoffs <= as_of_ts), "match_id"]
    ...
```

### CR-02: "Byte-identical replay" reproducibility relies on non-deterministic `to_parquet`

**File:** `src/cdd_mundial/live/materialization.py:195-196, 246-251` (and `compute_input_fingerprint` at 282-297)
**Issue:** The module's contract (docstring lines 16-18, 162-167) is that "identical
canonical inputs replay to the same checksum" and `_write_immutable_parquet`
**fails loud** (`FileExistsError`) when the destination exists with different bytes.
The SHA-256 of this parquet (`live_training_sha256`) is then fed into
`compute_input_fingerprint`, which drives the refit-vs-reuse decision and the
`model_version` short SHA. The whole chain assumes `frame.to_parquet(buffer,
index=False)` is byte-deterministic. It is not: pyarrow embeds a writer-version
string in the file/schema metadata and may vary compression/row-group framing across
library versions and platforms. Identical inputs on a different pyarrow/OS can
produce different bytes, which will (a) trip the immutable-write guard and crash a
legitimate re-run, and (b) flip the fingerprint and force a spurious refit + new
`model_version`, breaking deterministic reproducibility — the explicit Phase 4
invariant. The checksum is computed over a representation that is not content-stable.
**Fix:** Fingerprint over a canonical content representation rather than parquet
bytes, and/or pin parquet writer determinism. For the fingerprint, hash the
canonical CSV/JSON serialization of the sorted frame:
```python
def _canonical_content_sha(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256(payload).hexdigest()
```
Use that content hash (not the parquet file hash) for both the immutable-write
equality check and `compute_input_fingerprint`. If parquet bytes must be compared,
pin `version`, `compression`, and `store_schema` writer options and document the
pyarrow pin as a hard reproducibility dependency.

## Warnings

### WR-01: Live/history `match_id` collision is not guarded at materialization time

**File:** `src/cdd_mundial/live/materialization.py:175-195`
**Issue:** `map_live_rows_to_canonical` validates live rows in isolation (uniqueness
holds within the live slice), but `materialize_live_training` then `pd.concat`s them
with history (line 183) and writes the combined frame **without revalidating
uniqueness across the union**. `HistoricalMatchesSchema` requires `match_id` unique;
a live `match_id` that collides with a historical one silently produces a duplicate
in the written artifact. The duplicate is only caught later when `load_matches`
revalidates (lines 199, 350) — after the dated immutable parquet and its provenance
manifest are already on disk, leaving a partial, poisoned artifact. The 2026 fixture
namespace should be disjoint from history, but nothing enforces it here.
**Fix:** Assert disjoint keys before writing:
```python
overlap = set(history_canonical["match_id"]) & set(live_rows["match_id"])
if overlap:
    raise ValueError(f"live match_id(s) collide with history: {sorted(overlap)}")
```

### WR-02: Calibration ledger append is not atomic — crash mid-write corrupts the canonical source of truth

**File:** `src/cdd_mundial/live/calibration.py:325-330`
**Issue:** `append_ledger` reads the existing ledger, concatenates, and writes back
in place with `combined.to_parquet(ledger_path, index=False)`. This is the single
canonical append-only source of truth (D-18). An interruption (crash, OneDrive lock,
disk-full) during `to_parquet` can truncate or corrupt the file, destroying all prior
calibration history — the opposite of the append-only durability guarantee the
module advertises. Note the snapshot writer goes to lengths for atomic publish
(temp + rename), but the ledger write does not.
**Fix:** Write to a temp sibling and atomically replace:
```python
tmp = ledger_path.with_suffix(ledger_path.suffix + ".tmp")
combined.to_parquet(tmp, index=False)
tmp.replace(ledger_path)
```

### WR-03: `_resolve_dirty` ignores its `allow_dirty` argument — misleading signature

**File:** `src/cdd_mundial/live/pipeline.py:94-100`
**Issue:** `_resolve_dirty(allow_dirty: bool, force_dirty: bool)` never reads
`allow_dirty`; the gating decision lives entirely in the caller (`run_official`
lines 264-269). The parameter is dead and the name implies the function honors the
override, inviting a future caller to rely on behavior that does not exist. This is a
correctness-adjacent trap around the security-relevant publication gate.
**Fix:** Drop the unused parameter (`def _resolve_dirty(*, force_dirty: bool)`),
update both call sites, and keep the gate decision explicit in `run_official`.

### WR-04: Market benchmark errors are swallowed into a silent no-benchmark fallback

**File:** `src/cdd_mundial/live/pipeline.py:144-160`
**Issue:** `_build_frozen_benchmark` catches `(OddsValidationError, ValueError)` and
returns `None`, collapsing "no odds file" with "odds file present but malformed/
unparseable." A corrupted real odds file silently publishes a snapshot with **no
market calibration rows** and `benchmark_frozen=false`, with nothing in metadata
explaining *why* the benchmark was dropped. For a calibration pipeline this hides a
data-quality regression behind a "documented fallback."
**Fix:** Distinguish absent-vs-invalid: only treat a missing file / empty template as
the silent fallback; record the exception summary in metadata when a present file
fails to parse so the dropped benchmark is auditable rather than invisible.

### WR-05: `select_model_artifact` reuses a pinned model without verifying its on-disk integrity

**File:** `src/cdd_mundial/live/materialization.py:333-345`
**Issue:** The reuse branch checks `pinned["input_fingerprint"] == fingerprint` and
`Path(pinned["model_path"]).exists()`, then returns the model as reused, recomputing
`model_sha256` from whatever is on disk. It never compares that recomputed SHA against
a SHA stored at pin time, so a model file mutated/corrupted after pinning is reused
silently and stamped with the old `model_version`, breaking the version↔inputs tie
the docstring promises (D-13).
**Fix:** Persist `model_sha256` in the fingerprint record at fit time and, on reuse,
assert the recomputed digest matches; refit (or fail loud) on mismatch.

### WR-06: `result_after_extra_time` set on a non-drawn knockout with `advanced_team` drops the real margin

**File:** `src/cdd_mundial/live/materialization.py:117-135`
**Issue:** `drew_after_et` is `advanced_team is not None and goals_a == goals_b`. The
comment claims a drawn knockout is recorded "as a 90-minute draw decided after extra
time." That is correct for true draws, but a knockout match can carry `advanced_team`
with a decided 90-minute score (the `PlayedMatchResult` invariant only requires the
advancing side to match the winner when `goals_a != goals_b`). For such rows
`drew_after_et` is `False`, so `result_after_extra_time=False` and the real margin is
kept — fine. The latent risk: `home_score`/`away_score` are written as the raw
`goals_a`/`goals_b` even when `result_after_extra_time=True`, so a 1-1 ET draw and a
"1-1 then penalties" both feed the Dixon-Coles fit as a literal 1-1 scoreline. That
matches the historical parquet convention per the docstring, but there is no guard
that the canonical results goals are 90-minute (not full-time-incl-ET) figures; a
miskeyed ET score silently trains on the wrong margin.
**Fix:** Document and (ideally) assert the 90-minute-goals contract at the results
boundary, or carry an explicit `ft_score` vs `score_90` distinction so ET matches
cannot leak post-90 goals into the goal model.

## Info

### IN-01: `OverrideToken` records missing matches even when none were excused

**File:** `src/cdd_mundial/live/results.py:171-174`
**Issue:** When `blocking` is empty (all missing IDs excused), the loop appends *all*
`missing` IDs to `override.missing_matches`. This is reached only when every missing
ID is in `allow_missing`, so it is correct, but the trace records the full missing
set rather than only the IDs the token actually excused — slightly over-broad for an
audit field.
**Fix:** Append only IDs present in `override.allow_missing` for precise traceability.

### IN-02: `_check_scraper_assist` only compares goals, ignoring participant identity

**File:** `src/cdd_mundial/live/results.py:188-201`
**Issue:** The discrepancy check compares `(goals_a, goals_b)` keyed by `match_id` but
does not verify that the assist row's `team_a`/`team_b` match the canonical row. An
assist source with swapped or wrong teams but coincidentally equal goals passes
verification silently.
**Fix:** Also compare `team_a`/`team_b` (or normalized participant set) and record a
discrepancy on mismatch.

### IN-03: Bare `except (CalledProcessError, FileNotFoundError)` returns `""` for git status

**File:** `src/cdd_mundial/live/pipeline.py:63-73`
**Issue:** If `git` is missing or errors, `_git_status_porcelain` returns `""`, which
`_resolve_dirty` interprets as a **clean** worktree — allowing an official publish to
proceed on a repo whose cleanliness could not actually be determined. Low likelihood
in CI/dev, but it fails open on the publication gate.
**Fix:** Distinguish "git unavailable" from "clean" — fail closed (treat as dirty) or
surface an explicit `git_status_unknown` flag in metadata.

### IN-04: `_published_at` falls back to `snapshot_dir.name` for ordering, mixing key spaces

**File:** `src/cdd_mundial/live/report.py:67-69, 87-97`
**Issue:** Baseline ordering sorts on `published_at_utc`, defaulting to the directory
name when the key is absent. Directory names (`<ts>_<model_version>`) and ISO
instants do not share a sort space, so a metadata bundle missing
`published_at_utc` could order incorrectly relative to well-formed ones. All official
bundles set the field, so this is latent.
**Fix:** Treat a missing `published_at_utc` as a hard error during discovery rather
than silently substituting the directory name.

### IN-05: Magic constants for retry/backoff and figure DPI lack named rationale at use sites

**File:** `src/cdd_mundial/live/snapshots.py:42-43`; `src/cdd_mundial/live/report.py:144,161`
**Issue:** `_PUBLISH_RETRIES`/`_PUBLISH_BACKOFF_SECONDS` are documented, but the
`dpi=110` literals in the report plots are unexplained magic numbers repeated across
functions.
**Fix:** Hoist `dpi` into a module constant (e.g. `_FIG_DPI = 110`) for a single point
of control and a clear determinism rationale.

---

_Reviewed: 2026-06-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
