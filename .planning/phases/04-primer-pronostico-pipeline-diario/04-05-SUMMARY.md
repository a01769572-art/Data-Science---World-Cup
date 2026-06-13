---
phase: 04-primer-pronostico-pipeline-diario
plan: "05"
subsystem: live
tags: [official-publication, e2e-integration, frozen-benchmark, calibration-ledger, report-render, notebook-interface, runbook, pre-kickoff, append-only]
requires:
  - "src/cdd_mundial/live/pipeline.py (run_official/verify_official order enforcement)"
  - "src/cdd_mundial/live/materialization.py (immutable live-training + reuse/refit)"
  - "src/cdd_mundial/live/snapshots.py (SnapshotWriter staging/atomic publish)"
  - "src/cdd_mundial/live/report.py (snapshot-only HTML renderer)"
  - "src/cdd_mundial/live/calibration.py (freeze_market_benchmark, ledger, publish_calibration)"
  - "src/cdd_mundial/data/ingest_odds.py (build_odds_benchmark manual fallback)"
provides:
  - "One-command official publication chain: results -> materialize -> reuse/refit -> simulate -> stage -> freeze benchmark -> ledger append + slice -> report render -> one-shot metadata -> atomic publish"
  - "metadata.json nested provenance contract (generated_at_utc, kickoff_boundary_utc, git_commit, git_dirty, live_training_provenance, model_provenance, seed, preflight, publication_row_ids, checksums)"
  - "notebooks/04_primer_pronostico_pipeline.ipynb (thin interface over python -m cdd_mundial.live)"
  - "docs/live_pipeline_runbook.md (daily operator runbook)"
  - "First official append-only pre-kickoff snapshot bundle + canonical calibration ledger (versioned)"
affects:
  - "Phase 5/6 (ensemble + retrospectives consume the published snapshot/ledger surface)"
  - "DOC-02 portfolio publication (report.html is the daily shareable artifact)"
tech-stack:
  added: []
  patterns:
    - "Manual-odds fallback freezes a median de-margined market benchmark at publication time (D-20/D-21)"
    - "Ledger rows only for the intersection(upcoming predictions, frozen benchmark); unresolved outcomes stay <NA>"
    - "Report rendered post-publish beside the byte-frozen bundle; assets grouped under assets/"
    - "Kickoff boundary auto-derived from the earliest still-future unresolved fixture kickoff"
    - "Official snapshot bundles + canonical calibration ledger are versioned via data/processed/** + reports/snapshots re-inclusion (D-12/D-18)"
    - "Bounded retry around the atomic staging->destination rename survives transient Windows/OneDrive directory locks"
key-files:
  created:
    - "tests/test_live_reproducibility.py"
    - "notebooks/04_primer_pronostico_pipeline.ipynb"
    - "docs/live_pipeline_runbook.md"
    - "reports/snapshots/2026-06-13T22-02-08Z_baseline-v1-2026-06-13-50d98ab/ (first official bundle)"
    - "reports/snapshots/2026-06-13T22-07-38Z_baseline-v1-2026-06-13-50d98ab/ (verification re-publish)"
    - "data/processed/live/calibration/calibration_matches.parquet (canonical ledger)"
  modified:
    - "src/cdd_mundial/live/pipeline.py"
    - "src/cdd_mundial/live/report.py"
    - "src/cdd_mundial/live/snapshots.py"
    - "src/cdd_mundial/live/__main__.py"
    - "data/external/odds_2026_template.csv"
    - ".gitignore"
    - "tests/test_live_pipeline.py"
    - "tests/test_live_report.py"
    - "tests/test_repository.py"
decisions:
  - "Kickoff boundary = earliest still-future unresolved fixture kickoff; after a block kicks off the boundary auto-advances (pre-kickoff publication for the NEXT block)"
  - "metadata.json restructured into nested live_training_provenance / model_provenance with kickoff boundary + preflight + publication_row_ids; back-compat flat fields kept for the renderer"
  - "Calibration ledger rows are built only for upcoming predictions that have a frozen market benchmark (intersection), so an empty/partial odds slice never blocks publication"
  - "Official snapshot bundles and the canonical calibration ledger ARE versioned (D-12/D-18); dated live-training artifacts remain ignored runtime byproducts"
  - "data/external/odds_2026_template.csv populated with next-block bookmaker quotes as the approved manual-odds fallback (no provider key configured, D-04)"
metrics:
  duration: "~40 min (wall: includes a deliberate wait past the 22:00Z kickoff so the boundary advanced to 01:00Z)"
  completed: "2026-06-13"
  tasks: 3
  files: 12
requirements:
  - LIVE-01
  - LIVE-02
  - LIVE-03
  - LIVE-04
  - DOC-02
---

# Phase 4 Plan 05: Official Publication End-to-End + First Pre-Kickoff Snapshot Summary

One command (`python -m cdd_mundial.live --official ...`) now runs the entire publication chain — validate canonical results, materialize an immutable live-training artifact, deterministically reuse/refit the dated Dixon-Coles model, simulate the conditioned tournament, stage the snapshot, freeze the publication-time median market benchmark, append the authoritative calibration ledger plus a snapshot-local slice, render the static HTML report, finalize `metadata.json` exactly once, and atomically publish an append-only bundle — and Phase 4 shipped its **first official pre-kickoff publication** (`2026-06-13T22:02:08Z`), committed before the next kickoff boundary (`2026-06-14T01:00:00Z`).

## What Was Built

- **`src/cdd_mundial/live/pipeline.py`** — `run_official` extended into the full chain: derives the kickoff boundary, freezes the market benchmark from the manual-odds fallback (`build_odds_benchmark` -> `freeze_market_benchmark`), registers the frozen slice, builds ledger rows for the intersection of upcoming predictions and benchmarked matches, runs `publish_calibration` (ledger append + snapshot slice), writes nested-provenance metadata once, publishes, then renders the report beside the bundle. New helpers `_kickoff_boundary` (earliest still-future unresolved kickoff) and `_build_frozen_benchmark` (graceful no-benchmark fallback on empty/unusable odds).
- **`src/cdd_mundial/live/report.py`** — image assets moved into an `assets/` subdirectory (HTML references `assets/<name>`); the renderer now tolerates a missing ledger (treats it as an empty calibration history) so a pre-kickoff snapshot with no resolved matches still renders.
- **`src/cdd_mundial/live/snapshots.py`** — `publish()` retries the atomic staging→destination rename with bounded backoff to survive transient Windows/OneDrive directory locks, while re-checking the append-only destination-exists invariant before every attempt.
- **`src/cdd_mundial/live/__main__.py`** — CLI accepts `--official` (explicit no-op marker), `--results-csv` (alias of `--results-path`), and `--manual-odds` (manual odds fallback feeding the benchmark).
- **`notebooks/04_primer_pronostico_pipeline.ipynb`** — notebook-as-interface (MD→code→MD) that calls `verify_official`/`run_official` and inspects the published bundle, never duplicating production logic (D-07).
- **`docs/live_pipeline_runbook.md`** — operator runbook: official command shape, preflight checklist, publication + commit flow, failure-mode table (missing results, materialization drift, odds fallback, dirty worktree, snapshot collision, OneDrive lock), the `--allow-dirty` override, and daily cadence.
- **`data/external/odds_2026_template.csv`** — populated with three bookmakers each for the next-block fixtures (WC26-005/006/007) so the publication freezes a real median benchmark.
- **First official bundle** under `reports/snapshots/2026-06-13T22-02-08Z_baseline-v1-2026-06-13-50d98ab/`: `team_probabilities`, `group_positions`, `upcoming_match_predictions`, `frozen_benchmark`, `report_inputs/calibration_publication_slice`, `report.html`, `assets/*.png`, and immutable `metadata.json`. The canonical append-only ledger `data/processed/live/calibration/calibration_matches.parquet` seeded with the publication rows.

## Task-by-Task

| Task | Name | Commits | Files |
| ---- | ---- | ------- | ----- |
| 1 (TDD) | Wire report + calibration into the official command with reproducibility tests | `a5f591a` (RED), `b2d2fce` (GREEN), `f790701` (test fix) | pipeline.py, report.py, snapshots.py, tests/test_live_pipeline.py, tests/test_live_report.py, tests/test_live_reproducibility.py |
| 2 (checkpoint:decision, conditional) | Resolve the dirty-worktree gate if it triggers | (no-op — gate passed clean) | — |
| 3 | Publish the first official snapshot + document the operator interface | `dc7c52c`, `7269efb`, `14c237a` (first publish), `fd8836b` (verify re-publish), `e23045a` | __main__.py, runbook, notebook, odds template, .gitignore, snapshot bundles, ledger, tests/test_repository.py |

## Checkpoint Resolution (Task 2)

Task 2 was a **conditional blocking decision checkpoint** that applies only if the official publication fails the default git-clean gate. Per D-11, the Director (Jesús) pre-chose "clean commit first." The worktree was committed clean before publishing, so the default git-clean gate **passed clean** (`dirty=false` in both the verify-only check and the published metadata). Task 2 was therefore a **no-op**: no dirty file list, no `--allow-dirty`, and no human decision was required. The gate remained fail-closed by default; it simply never triggered.

## Pre-Kickoff Boundary Note

At publish time (~22:00Z) the literal next unresolved kickoff was WC26-007 @ 22:00Z — too close to safely commit before. The execution waited until just past 22:00Z so `_kickoff_boundary` auto-advanced to **WC26-005 @ 2026-06-14T01:00:00Z**, giving a ~3-hour pre-kickoff margin. Both publications and their commits landed well before that boundary, satisfying the LIVE-02/DOC-02 "committed before kickoff" criterion (verified: snapshot commit ISO < `kickoff_boundary_utc`). WC26-007 was published with `outcome_idx=<NA>` (a frozen pre-result benchmark row), consistent with the append-only ledger semantics.

## Verification

- `pytest tests/test_live_pipeline.py tests/test_live_reproducibility.py -x` → **16 passed** (Task 1 + Task 3 automated check).
- Official publication command → exit 0; first bundle `2026-06-13T22-02-08Z_...` with `dirty=false`, 3 `publication_row_ids`, `kickoff_boundary_utc=2026-06-14T01:00:00Z`, report rendered.
- Plan's PowerShell metadata verification block → **VERIFY-OK**: all required fields (`generated_at_utc`, `kickoff_boundary_utc`, `git_commit`, `git_dirty`, nested live-training/model provenance, `seed`, `preflight`, `checksums`), all required artifacts (`team_probabilities`, `upcoming_match_predictions`, `frozen_benchmark`, `report.html`, `report_inputs/calibration_publication_slice.parquet`, `assets/`), ledger present, `generated_at < boundary`, and snapshot commit ISO < boundary.
- Ledger integrity: 6 rows / 2 snapshots / **0 duplicate** `(snapshot_id, match_id)` keys.
- Combined regression (`test_live_snapshots`, `test_live_report`, `test_live_calibration`, `test_live_pipeline`, `test_live_reproducibility`, `test_repository`) → **47 passed**.
- `ruff check src/cdd_mundial/live/` → clean.

## TDD Gate Compliance

- Task 1 RED: `a5f591a` (`test(04-05)`) — `run_official` lacked `manual_odds_path` / nested metadata → 4 failing chain tests (1 verify-only test passed, as designed).
- Task 1 GREEN: `b2d2fce` (`feat(04-05)`) — full chain wired; the Task 1 verify suite green (16 passed). A follow-up `f790701` made the provenance test's dirty assertion deterministic via `_force_dirty`.
- REFACTOR: none required beyond the deterministic-test adjustment.

## Threat Model Coverage

| Threat ID | Disposition | How mitigated |
|-----------|-------------|----------------|
| T-04-13 (first publication repudiation) | mitigate | Default git-clean gate enforced; the publication ran clean (`git_dirty=false`) with the commit recorded in `metadata.json`. No `--allow-dirty` was used. |
| T-04-14 (notebook as alternate source of truth) | mitigate | `notebooks/04_*.ipynb` only calls `verify_official`/`run_official` and inspects returned/published artifacts; the publish cell is commented to avoid accidental re-publication on re-run. |
| T-04-15 (reproducibility of the first publish) | mitigate | Fixed-seed reruns reproduce identical live-training fingerprints, identical critical snapshot tables, and stable calibration row ids (`test_same_seed_reproduces_tables_and_fingerprints`); the bundle was committed before the recorded kickoff boundary. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Snapshot bundles + canonical ledger were gitignored, blocking the mandated pre-kickoff commit**
- **Found during:** Task 3 (committing the published bundle)
- **Issue:** Plan 04-02 added `reports/snapshots/` and `data/processed/` to `.gitignore` as runtime byproducts, but D-12/D-18 and this plan's verify require the official snapshot bundle and the canonical calibration ledger to be **versioned and committed before kickoff**. A bare directory exclusion (`data/processed/`) also prevented git from descending to re-include nested paths.
- **Fix:** Changed `data/processed/` to `data/processed/**` with targeted re-inclusions for `data/processed/live/calibration/calibration_matches.parquet`; removed the blanket `reports/snapshots/` exclusion (kept `.stg-*` staging ignored). Dated `live_training_*.parquet` byproducts stay ignored.
- **Files modified:** `.gitignore`, `tests/test_repository.py` (guardrail acknowledgement)
- **Commits:** `14c237a`, `e23045a`

**2. [Rule 1 - Bug] Transient `PermissionError` on the atomic snapshot rename (Windows/OneDrive)**
- **Found during:** Task 1 (reproducibility suite, intermittent)
- **Issue:** `SnapshotWriter.publish()` used a single `staging_dir.rename(destination)`; under OneDrive sync the directory rename intermittently raised `PermissionError [WinError 5]`, which would also threaten the real publication.
- **Fix:** Bounded retry with backoff around the rename, re-checking the append-only destination-exists invariant before each attempt; raises a clear `RuntimeError` only after exhausting retries.
- **Files modified:** `src/cdd_mundial/live/snapshots.py`
- **Commit:** `b2d2fce`

**3. [Rule 3 - Blocking] Report renderer assumed an existing calibration ledger**
- **Found during:** Task 1 (no-odds run path)
- **Issue:** `render_snapshot_report` unconditionally read `ledger_path`; a pre-kickoff snapshot with no market benchmark writes no ledger, so the render raised `FileNotFoundError`.
- **Fix:** The renderer now treats a missing ledger as an empty (no resolved matches) calibration history.
- **Files modified:** `src/cdd_mundial/live/report.py`
- **Commit:** `b2d2fce`

**4. [Rule 3 - Blocking] Windows MAX_PATH overflow on nested calibration slice in deep test workspaces**
- **Found during:** Task 1 (reproducibility suite)
- **Issue:** `.test-artifacts/<32-hex>/<...>/.stg-<53-char id>/report_inputs/calibration_publication_slice.parquet` exceeded the 260-char Windows limit (same pitfall as 04-02/04-03).
- **Fix:** Reproducibility tests use short snapshot ids (`_snapshot_id`) and short snapshot-root names. The real publication path (234 chars) is comfortably under the limit; the runtime code is unchanged.
- **Files modified:** `tests/test_live_reproducibility.py`
- **Commit:** `b2d2fce`

### Plan-file notes

- The official command shape in the plan (`--official`, `--results-csv`, `--manual-odds`) did not yet exist on the CLI; Task 3 added them (`dc7c52c`).
- The plan's Task 3 verify command re-publishes a snapshot as part of verification; this produced a second deterministic bundle (`22-07-38Z`), committed alongside the ledger update (`fd8836b`). Both bundles are byte-distinct only in timestamp; the simulation tables match under the fixed seed.

## Known Stubs

None. The report's `calibration_evolution.png` is intentionally absent in the first bundle because there are zero resolved matches pre-kickoff (cumulative metrics are empty by design); the renderer renders it as soon as the ledger has resolved outcomes. The benchmark/ledger/report are all wired to real data — no placeholder values.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundaries beyond those already in the Phase 4 threat register were introduced.

## Self-Check: PASSED

- `tests/test_live_reproducibility.py` — FOUND on disk.
- `notebooks/04_primer_pronostico_pipeline.ipynb` — FOUND on disk (valid nbformat, 17 cells, MD→code→MD).
- `docs/live_pipeline_runbook.md` — FOUND on disk.
- `reports/snapshots/2026-06-13T22-02-08Z_baseline-v1-2026-06-13-50d98ab/metadata.json` — FOUND on disk and committed (`14c237a`).
- `data/processed/live/calibration/calibration_matches.parquet` — FOUND on disk and committed.
- Commits `a5f591a`, `b2d2fce`, `dc7c52c`, `7269efb`, `14c237a`, `f790701`, `fd8836b`, `e23045a` — present in git history.
