# Architecture Research

**Domain:** Football (soccer) match forecasting + Monte Carlo tournament simulation
**Researched:** 2026-06-11
**Confidence:** HIGH on component decomposition and data flow (verified against penaltyblog's structure via Context7 + established Dixon-Coles literature); MEDIUM on details sourced from training data (FiveThirtyEight-style methodology); LOW-MEDIUM on exact FIFA 2026 third-place bracket allocation (must be verified against the official FIFA regulations document during implementation — web access unavailable during this research)

## Standard Architecture

Football forecasting systems converge on the same five-layer pipeline, whether academic (Dixon & Coles 1997), commercial (FiveThirtyEight SPI, Opta), or open-source (penaltyblog, club-elo derivatives). The defining characteristic is **two decoupled engines connected by a narrow interface**: a *match-level probability engine* (ratings + goal models) and a *tournament-level simulator* (rules + sampling). Everything else is plumbing around them.

### System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│  LAYER 1: DATA (src/data)                                          │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │
│  │ Kaggle   │ │ eloratings   │ │ FIFA rankings│ │ Fixture 2026  │  │
│  │ extract  │ │ scraper      │ │ scraper      │ │ + venues      │  │
│  └────┬─────┘ └──────┬───────┘ └──────┬───────┘ └───────┬───────┘  │
│       └──────────────┴───────┬────────┴─────────────────┘          │
│                              ▼                                     │
│        ┌──────────────────────────────────────┐                    │
│        │ TEAM MASTER TABLE (canonical names)  │ ← keystone; every  │
│        │ + cleaning + pandera schema checks   │   source maps here │
│        └──────────────────┬───────────────────┘                    │
│                           ▼  data/processed/*.parquet              │
├────────────────────────────────────────────────────────────────────┤
│  LAYER 2: FEATURES (src/features)                                  │
│  ┌─────────────────┐ ┌────────────────┐ ┌──────────────────────┐   │
│  │ Elo engine      │ │ Rolling form   │ │ Context features     │   │
│  │ (stateful fold  │ │ (last 5/10,    │ │ (host, rest days,    │   │
│  │  over history)  │ │  GF/GA rolling)│ │  match importance)   │   │
│  └────────┬────────┘ └───────┬────────┘ └──────────┬───────────┘   │
│           └──────────────────┴────────┬────────────┘               │
│                                       ▼  point-in-time feature mat │
├────────────────────────────────────────────────────────────────────┤
│  LAYER 3: MODELS (src/models)                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │ Dixon-Coles      │  │ XGBoost 3-class  │  │ Market implied  │   │
│  │ (attack/defense  │  │ classifier (1X2) │  │ probs (de-margin│   │
│  │  params → λ for  │  │                  │  │  — benchmark)   │   │
│  │  ANY team pair)  │  │                  │  │                 │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬────────┘   │
│           └─────────────────────┴──────────┬──────────┘            │
│                          ▼                 ▼                       │
│            Weighted ensemble → isotonic calibration                │
│            OUTPUT INTERFACE: predict_lambdas(team_A, team_B, ctx)  │
│                             predict_1x2(team_A, team_B, ctx)       │
├────────────────────────────────────────────────────────────────────┤
│  LAYER 4: SIMULATION (src/simulation)                              │
│  ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────────┐  │
│  │ Tournament state│ │ rules_fifa.py    │ │ monte_carlo.py      │  │
│  │ (played=fixed,  │ │ (PURE functions: │ │ (vectorized numpy:  │  │
│  │  pending=sim)   │ │  group ranking,  │ │  sample scores for  │  │
│  │                 │ │  tiebreakers,    │ │  N sims at once,    │  │
│  │                 │ │  best-thirds,    │ │  ET/penalty model)  │  │
│  │                 │ │  bracket mapping)│ │                     │  │
│  └────────┬────────┘ └────────┬─────────┘ └──────────┬──────────┘  │
│           └───────────────────┴─────────┬────────────┘             │
│                                         ▼                          │
│           Aggregates: P(advance to round R), P(champion), brackets │
├────────────────────────────────────────────────────────────────────┤
│  LAYER 5: REPORTING + ORCHESTRATION (src/reporting, notebooks)     │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────────┐  │
│  │ Matchday report  │ │ Calibration      │ │ Daily update loop  │  │
│  │ (matplotlib/     │ │ tracker (running │ │ (ingest → recompute│  │
│  │  seaborn tables, │ │ log-loss vs.     │ │  → re-simulate →   │  │
│  │  bracket figs)   │ │ benchmarks)      │ │  report)           │  │
│  └──────────────────┘ └──────────────────┘ └────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Extractors (`src/data/extract.py`) | Pull each source into `data/raw/` unchanged; record extraction metadata | requests/BS4 per source; Kaggle CSV download; cache everything |
| Team master (`data/external/teams.csv` + `src/data/clean.py`) | Single canonical team ID; every source's names map to it; coverage tests on ingest | Lookup table + fuzzy-match assist; fail loudly on unmapped names |
| Schemas (`src/data/schemas.py`) | Validate processed DataFrames at each stage boundary | pandera schemas as stage exit gates |
| Elo engine (`src/features/elo.py`) | Sequential fold over chronologically sorted matches; rating snapshot at any date t uses only matches < t | Stateful class or fold function; params (K, home adv, tournament weight) tuned on history |
| Form/features (`src/features/form.py`, `build_features.py`) | Point-in-time feature matrix per match | Rolling windows with `shift()` discipline; no full-history aggregates |
| Dixon-Coles (`src/models/dixon_coles.py`) | Fit attack/defense/home params with time-decay weights; produce (λ_home, λ_away) for **any** team pair on demand | scipy.optimize MLE; ~xi=0.0018 decay default per penaltyblog (verify on your data) |
| ML classifier (`src/models/ml_models.py`) | 1X2 probabilities for scheduled matches with known features | XGBoost, strict temporal CV |
| Ensemble + calibration (`ensemble.py`, `calibration.py`) | Blend layers by validation log-loss; isotonic calibration of final probs | sklearn isotonic per class + renormalize |
| Rules engine (`src/simulation/rules_fifa.py`) | Group ranking with full tiebreaker cascade; best-thirds ranking; R32 bracket slot assignment | Pure functions on arrays/dicts; exhaustive unit tests; NO sampling logic here |
| Monte Carlo (`src/simulation/monte_carlo.py`, `tournament.py`) | Sample N tournaments conditional on real results; aggregate | Vectorized numpy `(N_sims, n_matches)` Poisson sampling; seeded RNG |
| Tournament state | Authoritative record of played results + remaining fixtures | Parquet/CSV updated daily; played matches injected as fixed outcomes |
| Reporting (`src/reporting/`) | Tables, plots, daily markdown/HTML report; calibration log | matplotlib/seaborn; report notebook re-executed per matchday |

## Recommended Project Structure

The repo layout in `PROYECTO_MUNDIAL_2026.md` matches ecosystem convention (cookiecutter-data-science lineage + penaltyblog's module split). Keep it. One refinement worth adding:

```
src/
├── data/            # extract.py, clean.py, schemas.py
├── features/        # elo.py, form.py, build_features.py
├── models/          # dixon_coles.py, ml_models.py, ensemble.py, calibration.py
│                    #   → all expose predict_lambdas(team_a, team_b, ctx)
├── simulation/      # rules_fifa.py (pure), monte_carlo.py, tournament.py
├── reporting/       # tables.py, plots.py
└── pipeline.py      # NEW: single entry point for the daily loop
                     #   (ingest → features → predict → simulate → report)
tests/
└── test_rules_fifa.py   # NEW: tiebreaker/bracket unit tests — non-negotiable
```

### Structure Rationale

- **`src/` modules + thin notebooks:** notebooks import from `src/` and narrate (MD→code→MD); logic lives in testable modules. This is the single biggest structural decision for a daily re-run system — notebook-trapped logic cannot be re-executed reliably under tournament time pressure.
- **`rules_fifa.py` isolated and pure:** group ranking and bracket mapping are the highest-defect-risk code in the system (see Anti-Patterns). Pure functions over plain arrays make them unit-testable against historical group tables without touching the sampler.
- **`pipeline.py` as one entry point:** the daily loop must be one command (`python -m src.pipeline --date 2026-06-18`). During the live tournament you will run this 30+ times; every manual step is a failure point.
- **`models/` artifacts versioned by date:** each daily run must record which model artifact produced which forecast, or the post-mortem (E6) cannot attribute errors.

## Architectural Patterns

### Pattern 1: λ-Interface Decoupling (the load-bearing boundary)

**What:** The simulator never knows which model produced its inputs. Its only dependency is a callable `predict_lambdas(team_a, team_b, context) -> (λ_a, λ_b)`. Dixon-Coles satisfies it naturally because it fits per-team attack/defense parameters, so λ is computable for **arbitrary pairings** — which is mandatory: knockout pairings are unknown until each simulation determines them.

**When to use:** Always, in any tournament simulator. This is why the design decision "Dixon-Coles produces the λs, not the classifier" is correct: a fixture-feature-based classifier can only score *scheduled* matches; the simulator needs score distributions for the ~2,000 distinct hypothetical pairings that arise across 10k simulated brackets.

**Trade-offs:** The ML ensemble's influence on knockout matches is indirect (it can adjust λs or re-weight outcomes for known fixtures, or you blend at the ratings level). Accept this — it is the standard compromise (FiveThirtyEight's SPI does the same: team-level offensive/defensive ratings feed the simulator, not match-level classifiers — MEDIUM confidence, training data).

**Example:**
```python
# src/simulation/monte_carlo.py never imports dixon_coles directly
def simulate_tournament(state: TournamentState,
                        predict_lambdas: Callable[[str, str, MatchCtx], tuple[float, float]],
                        n_sims: int, rng: np.random.Generator) -> SimResults: ...
# Baseline ships with Elo-derived λs; Dixon-Coles swaps in without touching the simulator.
```

### Pattern 2: Conditional Simulation via Tournament State Object

**What:** A single `TournamentState` holds (a) results of played matches (fixed), (b) remaining fixtures, (c) current group tables. Every simulation starts from this state, not from the pre-tournament bracket. Aggregated outputs are therefore conditional probabilities given the real tournament so far.

**When to use:** Required here — the tournament started today. Also what makes the project resilient to schedule slip: the system is valid whenever it ships.

**Trade-offs:** State ingestion (yesterday's results) becomes a daily manual-or-scraped step; make it a small CSV the Director can edit by hand as a fallback (`data/external/results_2026.csv`) so a broken scraper never blocks the daily run.

### Pattern 3: Stateful Rating Engine as a Chronological Fold

**What:** Elo (and rolling form) are computed by folding over matches sorted by date; the feature value attached to match *i* is the state *before* match *i* is processed. Persist a ratings snapshot per date so training features and live-tournament features come from the identical code path.

**When to use:** All sequential rating systems. The #1 leakage source in sports forecasting is computing ratings/aggregates over the full dataset and joining them back onto historical matches.

**Trade-offs:** Recomputing the fold from 1872 on every daily run is acceptable here (~48k matches, sub-second in pandas/numpy); do not build incremental-state caching complexity you don't need.

### Pattern 4: Vectorized Monte Carlo over Simulation Axis

**What:** Sample all N simulations simultaneously: goals array of shape `(n_sims, n_matches)` via `rng.poisson(lam=...)`, group resolution via argsort over `(n_sims, 12, 4)` points tensors. Loop over the ~5 knockout rounds, never over simulations.

**When to use:** N ≥ 10k. A per-simulation Python loop with full rules logic runs minutes-to-hours; vectorized runs in seconds, which matters because you will re-simulate daily and want fast iteration while debugging rules.

**Trade-offs:** Tiebreaker cascades (head-to-head, fair play, drawing of lots) are awkward to fully vectorize. Pragmatic hybrid: vectorize points/GD/GF ranking (resolves the vast majority of tables), fall back to a per-simulation Python resolver only for the small fraction of sims with residual ties. Correctness first; numba only if profiling demands it.

## Data Flow

### Daily Production Flow (the system's main loop)

```
Yesterday's results (scrape or hand-edited CSV)
    ↓
[src/data] ingest → validate (pandera) → append to processed match table
    ↓
[src/features] re-fold Elo + rolling form  →  updated ratings snapshot
    ↓
[src/models] refresh Dixon-Coles fit (time-decay includes new matches)
             (re-train XGBoost only on schedule, not daily)
    ↓
[ensemble + calibration] → predict_lambdas / predict_1x2 callables
    ↓
[src/simulation] TournamentState(played=fixed) + Monte Carlo (N=10k, seeded)
    ↓
[src/reporting] reports/pronostico_YYYY-MM-DD.md + figures
    ↓
[calibration tracker] append realized log-loss/Brier vs. market benchmark
```

### Training/Validation Flow (offline, before and during)

```
data/raw (immutable) → clean + team-master mapping → data/processed/*.parquet
    → point-in-time features → temporal split (train < t ≤ validate)
    → fit DC / XGBoost → ensemble weights via validation log-loss
    → isotonic calibration → models/artifact_YYYY-MM-DD.pkl
```

### Key Data Flows

1. **Names flow through the team master once:** every extractor's output passes the canonical-name mapping before reaching `data/processed/`. Downstream code never sees source-specific names.
2. **Probabilities flow one direction:** features → models → λ/probs → simulator → aggregates → report. The simulator never feeds back into models within a run.
3. **Real results flow into two places:** (a) the match history (updating ratings/models), and (b) the TournamentState (fixing outcomes). These are distinct writes — a classic bug is updating one and not the other.

## Build Order (deadline-driven: baseline live before June 27)

Dependencies, with the critical parallelization opportunity flagged:

```
F0 Setup ──► F1 Data foundation (team master is the keystone — blocks everything)
                 │
        ┌────────┴────────────────────────────┐
        ▼                                     ▼
F2a Elo + Dixon-Coles                F2b Simulator (rules_fifa + monte_carlo)
   (needs processed data)               (needs ONLY the fixture + λ-interface
                                         contract — build against an Elo-stub
                                         or even constant λs; unit-test
                                         tiebreakers on historical groups)
        └────────┬────────────────────────────┘
                 ▼
F2c First end-to-end run → reports/ + daily pipeline.py   ◄── SHIP THIS ≤ June 27
                 ▼
F3 XGBoost + ensemble + isotonic calibration (swaps in behind the λ-interface;
   must beat baseline on temporal validation before replacing it in production)
                 ▼
F4 Live ops: daily loop + calibration tracking (runs from F2c onward; F3 upgrades it)
                 ▼
F5 Post-mortem (needs versioned forecasts from every matchday — start logging at F2c)
```

**Build-order implications for the roadmap:**

- **F2a and F2b are independent given the λ-interface contract.** This is the single most important scheduling fact: the simulator (the highest-risk, most test-heavy component) does not wait for any model. Define `predict_lambdas` on day one of F2.
- **The team master table is the bottleneck of F1** — budget real time for it; name mismatches across Kaggle/eloratings/FIFA/fixture are the documented #1 bug source in this domain.
- **Forecast logging starts the moment the first report ships**, not at F4 — the post-mortem and calibration tracking are only as good as the forecast archive.
- **XGBoost/ensemble is genuinely optional for a valid system.** Elo + Dixon-Coles + simulator is a complete, publishable forecaster (this is roughly what club-elo-style public models are). Treat F3 as an upgrade gated on beating the baseline.

## Scaling Considerations

Scaling here is simulation-count and re-run frequency, not users.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 10k sims, daily run | Vectorized numpy is comfortably sub-minute on a laptop. No further work. |
| 100k sims (smoother tail probabilities) | Same code; memory for `(100k, 104)` int arrays is trivial (~80 MB). Watch the per-sim Python fallback for residual ties — keep its hit-rate low. |
| Re-fit experiments (model iteration) | Dixon-Coles MLE over ~48k matches with scipy can take minutes per fit; restrict training window (e.g., post-1990) and reuse previous params as warm start for daily refreshes. |

### Scaling Priorities

1. **First bottleneck:** Dixon-Coles fit time during model iteration → warm starts + training-window cut.
2. **Second bottleneck:** un-vectorized group/tiebreaker resolution → hybrid vectorization (Pattern 4).

## Anti-Patterns

### Anti-Pattern 1: Simulating from 1X2 probabilities instead of score distributions

**What people do:** Feed the classifier's win/draw/loss probabilities into the simulator and sample outcomes directly.
**Why it's wrong:** Group tiebreakers require goal difference and goals scored; best-thirds ranking compares across groups on the same stats. Outcome-only sampling cannot produce them, and knockout pairings need probabilities for pairs the classifier never saw as fixtures.
**Do this instead:** Sample full scorelines from (λ_a, λ_b) Poisson (with the Dixon-Coles low-score adjustment). This is already the project's stated decision — it is correct; protect it.

### Anti-Pattern 2: Temporal leakage via full-history features

**What people do:** Compute Elo/rolling stats over the entire dataset, then join onto matches; or use random CV splits.
**Why it's wrong:** Features for match *t* contain information from matches after *t*; validation metrics become fantasy. The #1 documented failure mode in sports prediction.
**Do this instead:** Chronological fold (Pattern 3), strict temporal splits, validation on held-out tournaments (WC 2018/2022, Euro 2024, Copa América 2024). Director reviews features for leakage before accepting metrics.

### Anti-Pattern 3: Hand-rolled bracket logic scattered through the simulator

**What people do:** Embed group ranking and bracket slotting inline in the Monte Carlo loop.
**Why it's wrong:** The 2026 format is new (first 48-team/12-group edition); the best-thirds → R32 slot allocation depends on *which combination* of groups produces the qualifying thirds, defined by an official FIFA allocation table. Inline logic is untestable and this is where forecasts silently go wrong.
**Do this instead:** `rules_fifa.py` as pure functions + a unit-test suite: tiebreaker cascade tested against known historical group tables; bracket allocation tested against the official FIFA 2026 regulations document. **Flag: verify the exact third-place allocation table and tiebreaker order from the official FIFA regulations PDF during implementation — this research could not web-verify it (LOW-MEDIUM confidence on specifics).**

### Anti-Pattern 4: Logic trapped in notebooks

**What people do:** Build the whole pipeline in `04_simulacion.ipynb` and re-run cells manually each day.
**Why it's wrong:** A daily-rerun production system with hidden notebook state and manual cell order will break exactly when time pressure is highest (knockout rounds).
**Do this instead:** Notebooks narrate and call `src/` functions; `src/pipeline.py` runs the whole daily loop headlessly. The didactic MD→code→MD requirement is satisfied by notebooks *demonstrating* the modules, not *containing* them.

### Anti-Pattern 5: Updating match history but not tournament state (or vice versa)

**What people do:** Ingest yesterday's results into the ratings data but forget to fix them in the simulator's state, so simulations re-simulate played matches.
**Why it's wrong:** Forecasts stop being conditional on reality; probabilities for eliminated teams stay non-zero — instantly visible credibility failure.
**Do this instead:** Single ingestion function that writes both stores atomically, plus a pre-simulation assertion: every fixture dated before today must have a fixed result.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Kaggle (`martj42/international-football-results`) | One-time CSV download (manual, no API key configured) → `data/raw/` | Dataset updates with new results; decide whether daily results come from re-download or your own results CSV (recommend the latter — fewer moving parts) |
| eloratings.net | Light scraping (requests/BS4; Playwright fallback) → cache raw HTML | Use as initialization/cross-check; your own Elo fold is the primary rating to keep the code path uniform |
| FIFA rankings | Scrape or Kaggle mirror, monthly cadence | Static-ish feature; snapshot once, refresh if a new ranking drops mid-tournament |
| Official 2026 fixture + venues | One-time structured table (FIFA/Wikipedia) → `data/external/` | Must carry FIFA match IDs/slots so bracket mapping is data-driven, not hard-coded |
| Daily results | Scrape OR hand-edited `results_2026.csv` | Keep the manual fallback first-class — it is the reliability floor for the daily loop |
| Odds (football-data.co.uk / The Odds API) | CSV/API → de-margin via multiplicative or Shin's method | Benchmark only in v1; penaltyblog's `implied` module implements both methods (verified, HIGH confidence) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| data ↔ features | Parquet files in `data/processed/` validated by pandera | Files-as-interface keeps stages independently re-runnable |
| features ↔ models | Point-in-time feature matrix (parquet) + ratings snapshot | Same builder used for training and live prediction — one code path |
| models ↔ simulation | `predict_lambdas(team_a, team_b, ctx)` callable (+ optional `predict_1x2`) | THE contract of the system; defined before either side is built |
| simulation ↔ reporting | `SimResults` aggregate (per-team round probabilities, bracket counts) as plain DataFrame | Reporting never touches simulator internals |
| pipeline ↔ everything | `src/pipeline.py` orchestrates by calling stage entry points | One command per daily run; seeded RNG recorded in report metadata |

## Sources

- `PROYECTO_MUNDIAL_2026.md` (project design doc) and `.planning/PROJECT.md` — primary requirements source
- penaltyblog (`/martineastwood/penaltyblog` via Context7) — verified reference implementation: `ratings.Elo` (K-factor + home-field advantage), `models.DixonColesGoalModel` + `dixon_coles_weights` (time-decay, default xi=0.0018), `implied` (multiplicative/Shin/power margin removal), `metrics` (RPS etc.) — HIGH confidence
- Dixon & Coles (1997), "Modelling Association Football Scores and Inefficiencies in the Football Betting Market" — canonical model structure (training data, stable — MEDIUM-HIGH)
- FiveThirtyEight SPI methodology (team offensive/defensive ratings → match λs → Monte Carlo) — training data, MEDIUM confidence; web verification unavailable in this session
- FIFA 2026 format (48 teams, 12 groups, top-2 + 8 best thirds, R32) — consistent with project docs; **exact tiebreaker cascade and third-place bracket allocation table must be verified against official FIFA regulations during `rules_fifa.py` implementation** (web access denied during research)

---
*Architecture research for: World Cup 2026 forecasting + Monte Carlo tournament simulation*
*Researched: 2026-06-11*
