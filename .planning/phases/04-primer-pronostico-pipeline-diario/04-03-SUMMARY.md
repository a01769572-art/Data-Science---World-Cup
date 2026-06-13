---
phase: 04-primer-pronostico-pipeline-diario
plan: "03"
subsystem: live
tags: [report, jinja2, matplotlib, seaborn, html, snapshot-only, calibration, doc-02]
requires:
  - phase: 04-02
    provides: "frozen snapshot bundle (team_probabilities, group_positions, upcoming_match_predictions, frozen_benchmark) + SnapshotWriter staging hooks"
  - phase: 04-04
    provides: "calibration_publication_slice + canonical append-only ledger + cumulative_metrics helper"
provides:
  - "cdd_mundial.live.render_snapshot_report (snapshot-only HTML + PNG renderer)"
  - "templates/report_base.html.jinja + templates/report_daily.html.jinja (logic-free Jinja2 report templates)"
  - "Jinja2 declared as a direct project dependency for clean-clone rendering"
affects:
  - "Phase 4 plan 05 (e2e) renders a report from the official snapshot it publishes"
  - "DOC-02 portfolio documentation (the publishable daily HTML artifact)"
tech-stack:
  added: ["Jinja2>=3.1,<4"]
  patterns:
    - "Snapshot-only rendering: renderer reads frozen parquet/JSON + canonical ledger; never fits a model or simulates (D-12, T-04-07)"
    - "Headless deterministic visuals via matplotlib Agg backend + seaborn fixed theme/palette"
    - "Temporal baselines discovered from frozen snapshot metadata (published_at_utc), not mutable state (D-17, T-04-09)"
    - "Cumulative + evolution series are pure derived aggregations over the canonical ledger, never a second stored summary (D-22)"
    - "Jinja2 templates carry zero business logic; the renderer builds all view-models"
key-files:
  created:
    - "src/cdd_mundial/live/report.py"
    - "templates/report_base.html.jinja"
    - "templates/report_daily.html.jinja"
    - "tests/test_live_report.py"
  modified:
    - "pyproject.toml"
    - "src/cdd_mundial/live/__init__.py"
    - "tests/test_repository.py"
key-decisions:
  - "Renderer is snapshot-only: inputs are snapshot-local parquet/JSON + the top-level canonical calibration ledger; no model/simulation calls (D-12, T-04-07)."
  - "Matplotlib Agg backend + fixed seaborn theme/palette make PNG assets headless and re-renders deterministic."
  - "Temporal comparison baselines (previous + first-ever) are resolved by ordering snapshot dirs on frozen published_at_utc metadata (D-17, T-04-09)."
  - "Cumulative model-vs-market log-loss/RPS and the per-snapshot evolution series are recomputed from base ledger rows via the Phase 4 cumulative_metrics helper (D-22)."
  - "Jinja2 pinned >=3.1,<4 (tournament-safe bounded major) and added to the repository dependency-guardrail test."
patterns-established:
  - "Snapshot -> publishable static HTML report without recomputing forecasts."
  - "Logic-free Jinja2 inheritance (report_base -> report_daily) sourcing every value from frozen artifacts."
requirements-completed: [LIVE-03]
duration: ~18min
completed: 2026-06-13
---

# Phase 4 Plan 03: Static Daily Report Renderer Summary

**Snapshot-only Jinja2 + Matplotlib/Seaborn renderer that turns any frozen official snapshot plus the canonical calibration ledger into a publishable static HTML report — executive KPIs with a highlighted champion visual, next-block 1/X/2 cards, tournament probabilities, temporal deltas vs the previous and first-ever snapshots, cumulative model-vs-market log-loss/RPS with a calibration-evolution series, and a methodology note — without ever refitting a model or rerunning a simulation.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-13T18:59:36Z
- **Completed:** 2026-06-13T19:20:00Z (approx)
- **Tasks:** 2 (TDD)
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments

- `render_snapshot_report(snapshot_dir, *, snapshots_root, ledger_path, output_dir=None)` reads only finalized snapshot-local artifacts (`team_probabilities`, `upcoming_match_predictions`, `metadata.json`) plus the top-level authoritative `calibration_matches.parquet` ledger, and emits `report.html` with deterministic PNG assets beside the bundle.
- HTML carries all required D-15 sections (`executive-summary`, `next-block`, `tournament-probabilities`, `temporal-evolution`, `methodology`); the executive top block mixes KPI figures with a highlighted champion visual (D-16).
- Temporal evolution compares the current snapshot's champion probabilities against both the immediately previous and the first-ever published snapshot, with baselines discovered from frozen `published_at_utc` metadata (D-17, T-04-09).
- Cumulative model-vs-market log-loss / RPS / Brier and a per-snapshot evolution time series are derived from the canonical ledger via the Phase 4 `cumulative_metrics` helper (D-22); a Matplotlib/Seaborn evolution PNG is embedded.
- Jinja2 declared as a direct dependency so a fresh clone renders reports without transitive notebook installs; `report_base`/`report_daily` templates carry zero business logic.

## Task Commits

1. **Task 1: Freeze the static-report interface and dependency declaration (RED)** — `c011564` (test)
2. **Task 2: Implement the snapshot-only HTML renderer (GREEN)** — `2464d52` (feat)

_Single RED gate then single GREEN gate: the renderer (Task 2) and its dependency/contract tests (Task 1) form one cohesive feature, so the plan's two TDD tasks share a RED commit (Task 1 wrote the contract tests + Jinja2 pin) and a GREEN commit (Task 2 implemented the renderer + templates that turn the suite green)._

## Files Created/Modified

- `src/cdd_mundial/live/report.py` — snapshot-only renderer: artifact reads, baseline discovery, ledger-derived cumulative/evolution series, Matplotlib/Seaborn visuals, Jinja2 rendering.
- `templates/report_base.html.jinja` — base layout (styles, header/footer, KPI/section scaffolding).
- `templates/report_daily.html.jinja` — daily report extending the base; renders all required sections from injected view-models.
- `tests/test_live_report.py` — contract suite: data-source discipline (no model/sim calls), required sections, mixed KPI/visual top block, previous+first temporal comparison, single-snapshot edge case, cumulative metrics + evolution.
- `pyproject.toml` — added `Jinja2>=3.1,<4` to `[project].dependencies`.
- `src/cdd_mundial/live/__init__.py` — re-exports `render_snapshot_report`.
- `tests/test_repository.py` — added the sanctioned Jinja2 pin to the dependency-guardrail expected set.

## Decisions Made

- **Snapshot-only inputs.** The renderer's only file inputs are snapshot-local parquet/JSON and the canonical ledger; it never imports/calls `fit_dixon_coles` or `simulate_tournaments`. A dedicated test monkeypatches both to raise if invoked (D-12, T-04-07).
- **Headless deterministic visuals.** `matplotlib.use("Agg")` is set at import; seaborn uses a fixed theme/palette so re-rendering the same snapshot yields byte-identical HTML and reproducible PNGs.
- **Frozen-metadata baselines.** Previous/first snapshots are resolved by sorting sibling snapshot dirs on `published_at_utc` from each bundle's `metadata.json`, not from mutable ad-hoc state (D-17, T-04-09).
- **Ledger as the single source of truth.** Cumulative metrics and the evolution series are pure derived aggregations recomputed from base ledger rows (reusing `cumulative_metrics`), never a second stored summary (D-22).
- **Tournament-safe Jinja2 pin.** `Jinja2>=3.1,<4` matches the project's bounded-major pinning policy; the repository guardrail test was updated to acknowledge it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Windows MAX_PATH overflow in the report test fixture**
- **Found during:** Task 2 (bringing the report suite green)
- **Issue:** The frozen-snapshot test fixture wrote `report_inputs/calibration_publication_slice.parquet` under `.test-artifacts/<32-hex>/snapshots/<53-char snapshot id>/...`, pushing the absolute path to 270 chars (> Windows 260 MAX_PATH) and raising `FileNotFoundError` on the nested parquet write — the same pitfall plan 04-02 hit on staging paths.
- **Fix:** Shortened the test workspace nesting (`snapshots/` -> `s/`) and the test snapshot ids (`..._baseline-v1-2026-06-13-aaaaaaa` -> `..._v1`). The contract assertions are unchanged; only path lengths shrank.
- **Files modified:** `tests/test_live_report.py`
- **Verification:** `pytest tests/test_live_report.py` -> 7 passed.
- **Committed in:** `2464d52` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] Dependency-guardrail test rejected the sanctioned Jinja2 pin**
- **Found during:** Task 2 (full non-network suite)
- **Issue:** `tests/test_repository.py::test_python_and_tournament_safe_dependency_pins` asserts the exact dependency set; adding the plan-mandated `Jinja2>=3.1,<4` made the guardrail fail (1 failed, 320 passed).
- **Fix:** Added `Jinja2>=3.1,<4` to the test's `expected` set. Task 1 explicitly required declaring Jinja2 as a direct dependency, so this is the guardrail acknowledging a sanctioned addition, not a policy relaxation.
- **Files modified:** `tests/test_repository.py`
- **Verification:** `pytest tests/test_repository.py tests/test_live_report.py` -> 13 passed.
- **Committed in:** `2464d52` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking).
**Impact on plan:** Both were blocking environment/guardrail issues required to land the plan's mandated work; neither altered the report contract or added scope.

## Issues Encountered

- The full non-network suite is slow (~6 min, dominated by the 100k-sim engine and notebook tests); the targeted report + repository suites (~24 s) were used for the iteration loop, with the full suite run once for regression confirmation.

## TDD Gate Compliance

- RED gate: `c011564` (`test(04-03)`) — `from cdd_mundial.live import report` raised `ImportError` (module absent) before any logic.
- GREEN gate: `2464d52` (`feat(04-03)`) — all 7 report tests pass; full non-network suite green after the guardrail update.
- REFACTOR: none required. The MAX_PATH fix was applied while bringing the suite green, not as a post-green cleanup.

## Verification

- `pytest tests/test_live_report.py` -> **7 passed**.
- `pytest tests/test_repository.py tests/test_live_report.py` -> **13 passed**.
- Full non-network suite (`-m "not network and not manual"`) -> **321 passed** (320 + the re-greened repository pin test; was 314 before this plan, +7 report tests).
- `ruff check src/cdd_mundial/live/report.py tests/test_live_report.py` -> clean.

## Threat Model Coverage

| Threat ID | Disposition | How mitigated |
|-----------|-------------|----------------|
| T-04-07 (report rendering data source) | mitigate | Renderer inputs are restricted to snapshot-local artifacts + the canonical ledger; a test monkeypatches `fit_dixon_coles`/`simulate_tournaments` to raise, proving no business-logic call path. |
| T-04-08 (HTML table injection) | mitigate | Jinja2 `Environment` uses `select_autoescape` for html/xml/jinja and the templates inject only escaped text view-models; no raw/unsafe HTML. |
| T-04-09 (temporal comparison repudiation) | mitigate | Previous/first baselines are derived by ordering snapshot dirs on frozen `published_at_utc` metadata, not mutable runtime state. |

## Known Stubs

None. Stub scan over `report.py` and both templates found no `TODO`/`FIXME`/placeholder/`NotImplementedError` patterns. The optional group-detail section is intentionally deferred (the plan marks it optional/data-driven) and is not a stub; all rendered sections are wired to real frozen artifacts.

## Next Phase Readiness

- `render_snapshot_report` is ready for plan 04-05 (e2e) to call against the snapshot the official run publishes, closing the publish-then-render loop.
- No blockers. Note for 04-05: the renderer writes report assets into the snapshot dir by default; if the e2e flow requires the bundle to stay byte-frozen after publish, pass `output_dir` to render into a sibling location.

## Self-Check: PASSED

- `src/cdd_mundial/live/report.py` — FOUND on disk.
- `templates/report_base.html.jinja` — FOUND on disk.
- `templates/report_daily.html.jinja` — FOUND on disk.
- `tests/test_live_report.py` — FOUND on disk.
- Commits `c011564` (RED) and `2464d52` (GREEN) — FOUND in git history.

---
*Phase: 04-primer-pronostico-pipeline-diario*
*Completed: 2026-06-13*
