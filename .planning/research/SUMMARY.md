# Project Research Summary

**Project:** CDD-MUNDIAL — Pronósticos del Mundial 2026
**Domain:** Football match forecasting (structural + ML ensemble) with Monte Carlo tournament simulation, live-updated per matchday
**Researched:** 2026-06-11
**Confidence:** MEDIUM-HIGH (stack fully verified against live sources; methodology HIGH from stable literature; FIFA 2026 regulation specifics LOW — flagged for in-phase verification)

## Executive Summary

This is a well-trodden product category with a converged architecture. Every credible reference system — FiveThirtyEight's SPI forecasts, the Groll et al. academic models, Opta's supercomputer, the bookmaker-consensus literature — ships the same pipeline: calibrated match probabilities → goal distributions (Poisson-family) → full-rules tournament simulation → advancement probability tables → re-run after each matchday. That pipeline IS the product; everything else is presentation. The project's design decisions (Dixon-Coles λ feeding the simulator, temporal validation, conditional simulation, static reports) match the domain consensus exactly, which means the research's main contribution is sequencing, pinning versions, and pitfall-proofing rather than redirecting the approach.

The recommended approach is a verified, conservative Python stack (pandas 2.3.x pinned — NOT 3.x, numpy 2.x, scipy, scikit-learn 1.9, XGBoost 3.2) with **custom implementations of the three core engines** — Elo (~60 lines), Dixon-Coles (~150 lines, scipy MLE), and a vectorized numpy Monte Carlo simulator — because no library implements World Football Elo, international-football DC adaptations (neutral venues, gentle time decay), or the brand-new 2026 48-team format. The single most important scheduling fact: **the simulator and the models are independent given a `predict_lambdas(team_a, team_b, ctx)` interface contract**, so the highest-risk component (the FIFA 2026 rules engine) can be built and tested in parallel with the rating models, against stub λs.

The key risks are (1) the deadline — the tournament started today and the baseline must publish before the group stage ends June 27; (2) the FIFA 2026 third-place bracket allocation, the single most error-prone piece of the system, whose exact mechanism could not be web-verified this session and must be checked against the official FIFA regulations PDF before coding `rules_fifa.py`; and (3) forecast-integrity failures — if per-matchday forecasts aren't logged and git-committed *before kickoff* from the very first report, the live calibration tracking (the project's flagship differentiator) is irrecoverably lost. Mitigations: ship Elo-driven baseline first (XGBoost is a gated upgrade, not critical path), treat regulation verification as a phase prerequisite, and put the append-only forecast log in the baseline's exit criteria.

## Key Findings

### Recommended Stack

All versions verified against PyPI on 2026-06-11. The critical pin: **pandas ~=2.3.3, not 3.x** — seaborn 0.13.2 (latest, Jan 2024) predates pandas 3.0 and its compat fix is merged but unreleased. Data acquisition is friction-free: kagglehub downloads the martj42 dataset with **no API key** (verified), and eloratings.net serves plain TSV endpoints (`World.tsv`, `en.teams.tsv` — verified live today) fetchable with `requests` — no browser automation needed. Skip numba (pins numpy <2.5; vectorized numpy already hits the <1 min/100k-sims target).

**Core technologies:**
- Python 3.11/3.12 + pandas 2.3.3 + numpy 2.x + pyarrow — runtime and data layer; numpy IS the simulation engine
- scipy 1.17 — Dixon-Coles MLE via `optimize.minimize(L-BFGS-B)` with bounded ρ
- scikit-learn 1.9 — temporal CV, calibration (`FrozenEstimator`, NOT removed `cv="prefit"`), log-loss/Brier
- XGBoost 3.2 — 3-class classifier (`multi:softprob`); chosen over LightGBM (do not run both)
- pandera 0.31 (`import pandera.pandas as pa`) — schema gates at every stage boundary
- **Custom** Elo, Dixon-Coles, and Monte Carlo in `src/` — pedagogy is a hard requirement and no library fits; penaltyblog 1.11 as verification benchmark only (never import in `src/` — heavy transitive deps including plotly)

### Expected Features

The MVP definition is dictated by the domain pattern and the June 27 deadline. A complete, publishable forecaster does NOT require the ML layer — Elo + Dixon-Coles + simulator is roughly what public club-elo-style models are.

**Must have (table stakes — v1, before June 27):**
- Canonical team master table + clean historical DB — everything depends on it; name mismatches are the #1 silent-bug source
- Dynamic Elo (with explicit draw model) + Dixon-Coles λ with temporal validation
- Full-rules 2026 Monte Carlo simulator (12 groups, 8 best thirds, tested tiebreaker cascade)
- Conditional simulation on real tournament state + per-matchday update pipeline (one command)
- **Forecast snapshot persistence from day 1, timestamped pre-kickoff** — cannot be backfilled
- Odds ingestion + de-margin + cumulative log-loss tracking vs market and naive baselines
- Static matchday reports (advancement table, P(champion) chart); didactic MD→code→MD notebooks

**Should have (differentiators — v1.x during tournament):**
- Live calibration tracking vs betting-market benchmark — the most credible claim in the field; almost no portfolio project does honest in-production evaluation
- XGBoost classifier + measured ensemble with ablation — gated on beating baseline on all holdouts
- Probability evolution charts, reliability diagrams, match leverage analysis
- A correct, tested 2026 48-team `rules_fifa.py` — genuinely scarce public artifact

**Defer (v2+ / anti-features):**
- Interactive dashboard, live in-game win probability, player-level data, deep learning, betting strategy, cloud automation — all explicitly out of scope; static reports + manual daily trigger suffice

### Architecture Approach

Five-layer pipeline with **two decoupled engines connected by a narrow interface**: the match-probability engine (Elo/DC/ML) and the tournament simulator (rules + sampling), joined only by `predict_lambdas(team_a, team_b, ctx)`. The simulator must consume λs (score distributions), never 1X2 probabilities — group tiebreakers need goal counts and knockout pairings arise dynamically across simulations. Logic lives in testable `src/` modules; notebooks narrate and call them (the didactic requirement is satisfied by notebooks *demonstrating* modules, not containing them). A single `src/pipeline.py` entry point runs the daily loop — it will be executed 30+ times under tournament pressure.

**Major components:**
1. `src/data/` — extractors (immutable raw + metadata), team master + alias table, pandera schemas as stage exit gates
2. `src/features/` — Elo as chronological fold (state *before* match i), rolling form with `shift(1)` discipline, point-in-time joins
3. `src/models/` — Dixon-Coles (time-decay, neutral-aware), XGBoost, ensemble + calibration; all expose the λ-interface
4. `src/simulation/` — `rules_fifa.py` (PURE functions, exhaustive unit tests), vectorized Monte Carlo `(n_sims, n_matches)`, TournamentState (played=fixed)
5. `src/reporting/` + notebooks — matchday reports, calibration tracker, forecast log

### Critical Pitfalls

1. **Temporal leakage** (features, validation, calibration) — `shift(1)` discipline, `merge_asof` for point-in-time FIFA ranks, three-way temporal split (train/calibrate/test), strict holdouts (WC 2018/2022, Euro 2024, Copa América 2024). Warning sign: validation log-loss < ~0.95 means a leak, not a great model.
2. **FIFA 2026 rules bugs** — World Cup tiebreakers are NOT Euro rules (overall GD before head-to-head); the best-thirds → R32 bracket allocation depends on which 8-of-12 group combination qualifies (495 cases). Naive "ranked thirds → fixed slots" is wrong in essentially every simulation. Verify against the official regulations PDF *before* coding; replay-validate against real standings as the group stage progresses.
3. **Forecast-integrity failure** — forecasts regenerable after results are known make the calibration tracking scientifically worthless. Append-only forecast log, git-committed before kickoff, with model_version and UTC timestamps, from the FIRST published forecast.
4. **Dixon-Coles misimplementation for international football** — club-football time decay leaves national teams with ~5 effective matches; 200+ sparse teams make per-team parameters degenerate. Recommended baseline: drive λ from Elo difference, use DC for the dependence correction; constrain ρ; winsorize blowouts; verify simulated draw share 24–28%.
5. **Neutral venues + Elo draw model** — zero home advantage on neutral matches (~95% of WC matches), separate host effect for Mexico/USA/Canada; Elo expected score is P(win)+0.5·P(draw), not P(win) — an explicit draw model is part of the baseline deliverable.

## Implications for Roadmap

Based on research, suggested phase structure (deadline-driven: phases 1–4 must complete before June 27):

### Phase 1: Data Foundation
**Rationale:** The team master table is the keystone — every source (Kaggle, eloratings, FIFA, fixture, odds) maps through it, and name mismatch is the documented #1 bug source in this domain. Nothing downstream can start safely without it.
**Delivers:** kagglehub ingestion, eloratings TSV scraper (requests-only), fixture 2026 frozen in `data/external/`, canonical teams.csv + alias table + predecessor map, pandera schemas, outcome-convention columns (`outcome_ft` vs `advanced`, shootouts cross-check), odds source ingestion, 48-team coverage test as a hard gate.
**Addresses:** Clean historical DB, canonical team table, reproducibility (table stakes).
**Avoids:** Pitfalls 2 (name mismatch), 3 (neutral-flag semantics verified in EDA), 11 (penalty/AET label conventions).

### Phase 2: Baseline Models (Elo + Dixon-Coles)
**Rationale:** The simulator needs λs; Elo-driven λ with DC dependence correction is the robust route for sparse international data. Custom implementations are the project's core learning content.
**Delivers:** `elo.py` (World Football Elo: K by tournament, goal-margin multiplier, conditional home/host advantage, explicit draw model), `dixon_coles.py` (bounded ρ, ξ tuned on temporal validation, neutral-aware), temporal validation harness with log-loss/Brier/RPS vs naive baselines, penaltyblog cross-check.
**Uses:** scipy MLE, custom RPS, statsmodels GLM as pedagogical stepping stone.
**Implements:** Layer 2–3 of the architecture; the λ-interface contract (defined day one of this phase).

### Phase 3: Tournament Simulator (parallel-capable with Phase 2)
**Rationale:** Independent of the models given the λ-interface — build against stub/constant λs. Highest-defect-risk component; needs the most test time, so start early.
**Delivers:** `rules_fifa.py` as pure functions (tiebreaker cascade, best-thirds ranking, R32 bracket allocation) with exhaustive unit tests (historical groups incl. WC 2018 Group H, synthetic 3/4-way ties, specific thirds combinations); vectorized Monte Carlo with per-simulation random tiebreak keys, seeded RNG, invariant assertions; TournamentState for conditional simulation.
**Avoids:** Pitfalls 7 (rules bugs) and 8 (MC noise, deterministic tie-bias, stale conditioning).
**Prerequisite:** Fetch and verify the official FIFA World Cup 26 Regulations PDF (tiebreaker order, thirds allocation annex, fair-play point values) — LOW confidence from research, must be resolved before coding.

### Phase 4: First Forecast + Daily Pipeline (SHIP ≤ June 27)
**Rationale:** Elo + DC + simulator is a complete, publishable forecaster. Shipping it starts the irreplaceable forecast archive and the live calibration experiment.
**Delivers:** `src/pipeline.py` end-to-end (ingest → re-fold ratings → refresh DC → simulate N=100k → report), manual results-entry fallback as first-class path, append-only forecast log committed pre-kickoff, first matchday report (advancement table, P(champion)), cumulative log-loss tracker vs market/Elo-only/uniform, common-random-numbers discipline for day-over-day comparisons, didactic notebooks demonstrating each module.
**Avoids:** Pitfall 9 (live-pipeline integrity — UTC timestamps, fixture-completeness assertions, forecast log in exit criteria).

### Phase 5: ML Layer + Ensemble + Calibration (gated upgrade)
**Rationale:** Genuinely optional for validity; only worth shipping if it measurably beats the baseline. Sequencing it after the baseline publishes protects the deadline.
**Delivers:** Point-in-time feature matrix, constrained XGBoost (depth ≤ 3–4, ≤ ~10 features), ensemble weighted by validation log-loss, Platt-vs-isotonic comparison (isotonic NOT assumed — small calibration sets overfit it), pre-registered acceptance gate: beats/ties baseline log-loss on all four holdout tournaments. Baseline forecasts keep running in parallel for honest comparison.
**Avoids:** Pitfalls 1 (calibration split), 6 (isotonic overfitting), 10 (small-sample XGBoost, draw-class trap).

### Phase 6: Live Operations + Post-Mortem
**Rationale:** Runs from Phase 4 onward through July 19; the post-mortem needs the full versioned forecast archive and is time-fixed at tournament end.
**Delivers:** Daily operational discipline, replay-validation of the rules engine against real standings, reliability diagrams once ~30+ matches accumulate, match leverage analysis (cheap once conditional sim exists), evolution charts, honest post-mortem vs benchmarks, Obsidian learning notes per phase.

### Phase Ordering Rationale

- **Phases 2 and 3 are parallel given the λ-interface** — the single most important scheduling fact from architecture research; the simulator never waits for a model.
- **Phase 1 first because everything joins through the team master**; coverage tests there prevent the domain's most common silent corruption.
- **Phase 4 before Phase 5 is non-negotiable**: evolution charts and live calibration cannot be backfilled — every day without a published forecast permanently shrinks the project's flagship differentiator.
- **Phase 5 is gated, not scheduled**: the design doc already blesses shipping the baseline if ML doesn't beat it; a negative result is a documented finding, not a failure.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Simulator):** FIFA 2026 official regulations — exact tiebreaker text, third-place R32 allocation mechanism, fair-play point values. LOW confidence; web verification was unavailable during research. This is a hard prerequisite, not a nice-to-have.
- **Phase 1 (Data):** Odds source availability/format for WC 2026 (football-data.co.uk vs The Odds API free tier) — LOW confidence; verify during ingestion. Also verify martj42 shootouts.csv/neutral-flag conventions at ingest.
- **Phase 2 (Baseline):** World Football Elo exact constants (K=60 WC, goal-margin multiplier, +100 home) — MEDIUM confidence; verify against eloratings.net/about when implementing.

Phases with standard patterns (skip research-phase):
- **Phase 4 (Pipeline):** Plumbing of already-built components; patterns fully specified in ARCHITECTURE.md.
- **Phase 5 (ML/Ensemble):** sklearn/XGBoost temporal-CV and calibration patterns are well-documented and version-verified in STACK.md.
- **Phase 6 (Ops/Post-mortem):** Discipline, not novelty.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 16 package versions verified against PyPI 2026-06-11; eloratings TSV endpoints and kagglehub no-auth verified live |
| Features | MEDIUM | Training-data knowledge of a stable, well-documented domain; reference systems' patterns are consistent but web verification was unavailable |
| Architecture | HIGH (decomposition) / LOW-MEDIUM (FIFA 2026 specifics) | Component layout verified against penaltyblog structure + canonical literature; thirds-allocation mechanics unverified |
| Pitfalls | MEDIUM | Methodology pitfalls (leakage, DC, calibration, Elo) HIGH from stable literature; 2026 regulation details LOW, flagged with in-phase verification steps |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **FIFA 2026 regulations (tiebreaker order, thirds → R32 allocation table, fair-play points):** fetch the official FIFA World Cup 26 Regulations PDF as the first task of the simulator phase; cross-check with Wikipedia's format article; replay-validate against real standings after matchday 2.
- **2026 odds source:** verify availability and format during Phase 1; one consistent source suffices; keep cached raw copies.
- **martj42 dataset conventions** (penalties-as-draws in results.csv, neutral-flag semantics): verify empirically at ingest with explicit assertions.
- **World Football Elo constants:** confirm from eloratings.net/about during `elo.py` implementation; tune K/home/weights on history regardless.
- **seaborn/pandas-3 timing:** revisit the pandas pin post-tournament only; never mid-tournament.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API (2026-06-11) — exact versions + requires_dist for all stack packages
- eloratings.net `World.tsv` / `en.teams.tsv` — fetched live, confirmed plain-TSV with current ratings
- github.com/Kaggle/kagglehub README — no-auth public dataset downloads; martj42 dataset handle verified HTTP 200
- penaltyblog (via Context7 + official repo) — reference implementation structure: DC weights (xi=0.0018 default), implied-odds de-margin methods, RPS
- scikit-learn stable docs — `FrozenEstimator` pattern confirmed; `cv="prefit"` removed
- Dixon & Coles (1997) — canonical model math; `PROYECTO_MUNDIAL_2026.md` + `.planning/PROJECT.md` — requirements

### Secondary (MEDIUM confidence)
- FiveThirtyEight SPI methodology, Groll et al. papers, Zeileis/Leitner/Hornik bookmaker consensus — feature landscape and architecture patterns (training data)
- Kaggle football competition norms — log-loss scoring, GBM+Elo consensus, calibration as the differentiator
- FIFA WC 2018/2022 tiebreaker order and WC 2018 Group H fair-play precedent — training data
- martj42 dataset structure (results.csv/shootouts.csv conventions) — verify at ingest

### Tertiary (LOW confidence — needs validation)
- FIFA 2026-specific regulations: exact tiebreaker text, thirds R32 allocation annex, fair-play point values — verify against official PDF before `rules_fifa.py`
- 2026 World Cup odds source availability/format — verify during data phase

---
*Research completed: 2026-06-11*
*Ready for roadmap: yes*
