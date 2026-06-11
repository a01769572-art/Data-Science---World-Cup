# Feature Research

**Domain:** Football (soccer) tournament forecasting — World Cup 2026 match prediction + Monte Carlo tournament simulation
**Researched:** 2026-06-11
**Confidence:** MEDIUM (training-data knowledge of a stable, well-documented domain; WebSearch/WebFetch unavailable in this session — flagged items need verification during build)

## Reference Systems Surveyed

The feature landscape below synthesizes what these systems actually ship:

| System | Type | Key Traits |
|--------|------|-----------|
| FiveThirtyEight SPI World Cup forecasts (2018, 2022) | Media/public model | SPI off/def ratings → match probs → ~20k Monte Carlo sims → advancement tables updated after every match; match "leverage" highlights |
| Groll et al. (2018/2019/2021, hybrid random forest + ranking) | Academic | Team covariates (FIFA rank, Elo, market value, CL players, coach, host) → expected goals → 100k tournament sims; evaluated with RPS/log-loss |
| Zeileis/Leitner/Hornik bookmaker consensus | Academic | De-margined aggregated odds → implied abilities → tournament simulation; consistently hard benchmark to beat |
| Dixon-Coles (1997) and descendants | Statistical canon | Bivariate Poisson, low-score correction, time decay → λ per team; the standard goals model |
| Opta / The Analyst (Stats Perform) supercomputer | Commercial | Match probabilities + ~10k tournament sims, updated per matchday; power rankings |
| Kaggle football prediction competitions/solutions | Community | Gradient boosting on Elo/form features; scored on log-loss; calibration is what separates winners |

**Consistent pattern across all of them:** calibrated match probabilities → goal distributions → full-rules tournament simulation → advancement probability tables → re-run after each matchday. That pipeline IS the product. Everything else is presentation.

## Feature Landscape

### Table Stakes (Must Have or the Project Isn't Credible)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Clean historical match database + canonical team table | Every reference system builds on a unified historical record; fuzzy team-name mismatches are the #1 silent-bug source | MEDIUM | Kaggle `martj42` + Elo ratings + fixture; pandera schemas; coverage tests per source |
| Dynamic Elo rating system | Universal baseline strength signal (538 SPI is Elo-family; Groll uses Elo as covariate); also the simplest sanity check | MEDIUM | Tune K, home advantage, tournament weights on historical data |
| Match W/D/L probability model | The atomic forecast unit; every system outputs 1/X/2 probabilities | MEDIUM | Draw probability is the hard class — pure Elo logistic underestimates draws; Poisson-derived probs handle it naturally |
| Expected-goals model (Dixon-Coles λ) | Monte Carlo needs goal *distributions*, not just outcome probs; D-C is the canonical approach | HIGH | Time-decay weighting + low-score correction; optimization via scipy; this is the methodological core |
| Probability calibration | Kaggle winners and academic papers agree: raw model probs are miscalibrated; proper scoring rules punish this directly | LOW–MEDIUM | Isotonic/Platt on temporal validation folds; never calibrate on training data |
| Full-rules Monte Carlo tournament simulator (≥10k runs) | The headline product (P(champion), P(reach round R)); 538/Opta/Groll all do this | HIGH | 2026 format is NEW: 12 groups, 8 best third-place teams, Round of 32. FIFA tiebreaker cascade (points → GD → GF → head-to-head → fair play → drawing of lots) + extra-time/penalty model. Needs unit tests against known historical group outcomes |
| Advancement probability table per team | The single most consumed output of every public forecast (538's iconic table) | LOW | Direct aggregation over sims: P(R32), P(R16), P(QF), P(SF), P(F), P(champion) |
| Conditional simulation on real tournament state | Tournament started 2026-06-11; a forecast ignoring played matches is instantly wrong | MEDIUM | Fix played results, simulate only remaining matches; ratings/form update with real results |
| Per-matchday update pipeline | 538/Opta update after every match; a static pre-tournament snapshot has no value mid-tournament | MEDIUM | Ingest results → update Elo/form → re-simulate → regenerate report; must be one command/notebook re-run |
| Temporal validation with proper scoring rules | Log-loss/Brier/RPS on held-out tournaments (WC 2018/2022, Euro 2024, Copa América 2024) is the academic and Kaggle standard; accuracy alone is disqualifying | MEDIUM | Strict temporal splits; RPS preferred for ordered W/D/L outcomes |
| Static matchday reports (tables + charts) | Forecast nobody can read doesn't exist; matplotlib/seaborn per project constraint | MEDIUM | Probability tables, group standings distributions, P(champion) bars, evolution lines |
| Reproducibility (fixed seeds, versioned data, immutable raw) | Portfolio credibility; any published number must be regenerable | LOW | Seeds for sims, parquet + extraction metadata, model artifacts versioned by date |

### Differentiators (Portfolio Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live calibration tracking vs betting-market benchmark | Almost no portfolio project does honest *in-production* evaluation; 104 real matches give a real out-of-sample test no pre-tournament model gets. "Did we beat the market in log-loss?" is the most credible question in the field | MEDIUM | Requires de-margined implied probabilities (basic normalization; Shin's method optional). Cumulative log-loss/RPS chart: model vs market vs Elo-only vs uniform |
| Reliability diagrams in production | Calibration plots over real tournament matches demonstrate genuine statistical literacy; rare outside academia | LOW | 104 matches is small for binning — use grouped bins and say so honestly |
| Measured ensemble (structural + ML) with ablation | Most projects ship one model; showing the ML layer's *marginal* contribution over Dixon-Coles baseline (or honestly reporting it adds nothing) is the portfolio story | MEDIUM | Weights fit via log-loss on validation; report per-layer and ensemble metrics |
| Probability evolution charts (P(champion) over time) | 538's most shareable artifact; tells the tournament's story; only possible because the system updates live | LOW | Persist every matchday's forecast snapshot from day 1 — cannot be reconstructed later if not saved |
| 2026 48-team format simulator (best thirds → Round of 32) | New format, few public implementations exist; a correct, tested `rules_fifa.py` is a genuinely scarce artifact | HIGH | Already table stakes for *this* tournament, but differentiating in the ecosystem; test the best-thirds bracket-assignment rules carefully (FIFA's allocation table) |
| Didactic notebooks (MD→code→MD) | Hard requirement; turns the repo into teaching material — differentiator vs typical Kaggle-dump repos | MEDIUM | Discipline cost on every notebook, not technical difficulty |
| Match leverage/importance analysis | 538-style "what's at stake in this match": ΔP(advance) between win/draw/loss branches | MEDIUM | Cheap once conditional simulation exists — run sims conditioned on each outcome of an upcoming match |
| Feature importance + model interpretation | Which features matter (Elo diff vs form vs FIFA rank vs host)? Standard for portfolio-grade ML; feeds the post-mortem | LOW | XGBoost gain/SHAP; goes in post-mortem and notebooks |
| Honest post-mortem report | Pre-committed final evaluation vs benchmarks, including failures and lessons; signals scientific integrity | LOW | Template the metrics from day 1 so the post-mortem writes itself |
| Skill scores vs naive baselines | Beating uniform (33/33/33), Elo-only, and FIFA-rank-only baselines contextualizes every metric | LOW | Cheap; compute alongside main metrics every matchday |

### Anti-Features (Deliberately NOT Building)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Interactive dashboard (Streamlit/Dash) | "Forecasts should be a web app" | Frontend time competes directly with modeling time during a 5-week live tournament; static reports satisfy the consumer (Director + portfolio readers) | Matplotlib/seaborn static reports per matchday (already decided); dashboard = possible future milestone |
| Live in-game win probability | 538 had it; looks impressive | Requires event-level/minute-by-minute data feeds and a completely different model class; zero value for pre-match + tournament forecasting | Pre-match probabilities updated per matchday |
| Player-level modeling (lineups, injuries, suspensions) | "Better models use player data" | High extraction cost (scraping lineups daily), small marginal gain at national-team level, huge leakage surface | Team-level features; squad market value (Transfermarkt) as optional P2 single scalar |
| Deep learning models | "ML project should use neural nets" | ~48k international matches with weak covariates is small data; GBMs + structural models are the documented ceiling (Kaggle + academic consensus) | XGBoost/LightGBM + Dixon-Coles ensemble |
| Exact-scoreline prediction as headline output | Intuitive, "predict 2-1" | Single most likely score has ~8-12% probability; chasing scoreline accuracy degrades probabilistic quality | Report λ (expected goals) and scoreline *distributions* from the Poisson model |
| Betting strategy / Kelly staking / value-bet alerts | Natural extension of beating the market | Scope creep, ethical/legal exposure, distracts from the academic benchmark purpose | Odds used strictly as de-margined benchmark in evaluation |
| Automated cloud deployment / cron scheduling | "Production system needs automation" | Infra time for a 5-week project with one daily manual trigger; failure modes multiply | Manual re-run of `99_reporte_diario.ipynb` (one command); document the runbook |
| In-tournament model retraining/feature additions ad hoc | "Model is underperforming, let's fix it live" | Untracked mid-tournament changes destroy the validity of the live calibration experiment | Freeze methodology per version; if revising, version the model (v1/v2) and report metrics per version |
| Heavy multi-source odds aggregation | More bookmakers = better benchmark | API costs/rate limits; one consistent source is sufficient for an academic benchmark | One source (football-data.co.uk or The Odds API free tier), cached in raw/ |

## Feature Dependencies

```
Canonical team table (teams.csv)
    └──required-by──> ALL data ingestion (Kaggle, Elo, FIFA rank, fixture, odds)

Historical match DB
    └──required-by──> Elo ratings ──required-by──> ML features ──required-by──> XGBoost classifier
    └──required-by──> Dixon-Coles (λ) ──required-by──> Monte Carlo simulator

Dixon-Coles λ + FIFA 2026 rules engine
    └──required-by──> Tournament simulator ──required-by──> Advancement tables
                                           ──required-by──> Match leverage analysis

Conditional simulation ──requires──> Simulator + results-ingestion pipeline
Per-matchday update    ──requires──> Conditional simulation + Elo/form recompute
Probability evolution charts ──require──> Per-matchday snapshots PERSISTED FROM DAY 1

Odds ingestion (de-margin) ──required-by──> Market benchmark ──required-by──> Live calibration tracking
Calibration (isotonic) ──requires──> Temporal validation folds
Ensemble ──requires──> Dixon-Coles + ML model + validation metrics (for weights)
Post-mortem ──requires──> Live calibration tracking accumulated over tournament
```

### Dependency Notes

- **Everything requires the canonical team table:** name mismatches across Kaggle/Elo/FIFA/fixture sources silently corrupt features. Build it first with coverage tests.
- **Simulator requires λ, not W/D/L probs:** the classifier alone cannot drive Monte Carlo (group tiebreakers need goal counts). This is why Dixon-Coles is on the critical path and the ML classifier is not.
- **Evolution charts and live calibration cannot be backfilled:** if matchday snapshots and per-match predictions aren't persisted from the first report, the two flagship differentiators are lost. Persist forecasts *before* matches are played (timestamped) — also proves no hindsight editing.
- **Market benchmark gates the headline claim:** without de-margined odds per match, "vs market" calibration tracking is impossible; ingest odds in the data phase, not later.
- **Ensemble conflicts with timeline if sequenced wrong:** baseline (Elo + D-C + simulator) must publish before ML/ensemble work begins — matches the design doc's F2-before-F3 plan.

## MVP Definition

### Launch With (v1 — baseline, must publish before group stage ends 2026-06-27)

- [ ] Clean historical DB + canonical team table — everything depends on it
- [ ] Dynamic Elo — baseline strength + ML feature later
- [ ] Dixon-Coles λ model with temporal validation — feeds simulation
- [ ] Full-rules 2026 Monte Carlo simulator (10k+ sims, tested tiebreakers, best thirds) — the product
- [ ] Conditional simulation on real state — tournament already running
- [ ] Per-matchday update pipeline + static report (advancement table, P(champion) chart)
- [ ] Per-matchday forecast snapshot persistence (timestamped, pre-match) — enables evolution charts and honest evaluation
- [ ] Odds ingestion + de-margin + cumulative log-loss tracking vs market and naive baselines
- [ ] Didactic notebook structure (MD→code→MD) — hard requirement from day 1, not retrofittable cheaply

### Add After Validation (v1.x — during group stage / Round of 32)

- [ ] XGBoost 3-class classifier + features — trigger: baseline publishing reliably
- [ ] Ensemble + isotonic calibration — trigger: ML beats or ties baseline on temporal validation
- [ ] Reliability diagrams on accumulated real matches — trigger: ~30+ matches played
- [ ] Match leverage analysis — trigger: conditional simulation stable; highest value at end of group stage and knockouts
- [ ] Squad market value feature (Transfermarkt scalar) — trigger: spare capacity, scraping feasible

### Future Consideration (v2+ / post-tournament)

- [ ] Post-mortem report — fixed scope, after final (July 19)
- [ ] Interactive dashboard — explicit future milestone, out of v1 scope
- [ ] Shin's method de-margin / multi-bookmaker benchmark — only if odds-margin handling proves noisy

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Canonical team table + clean DB | HIGH | MEDIUM | P1 |
| Elo dynamic ratings | HIGH | MEDIUM | P1 |
| Dixon-Coles λ | HIGH | HIGH | P1 |
| 2026-rules Monte Carlo simulator | HIGH | HIGH | P1 |
| Conditional simulation + matchday pipeline | HIGH | MEDIUM | P1 |
| Forecast snapshot persistence | HIGH | LOW | P1 |
| Market benchmark + log-loss tracking | HIGH | MEDIUM | P1 |
| Static matchday reports | HIGH | MEDIUM | P1 |
| Didactic notebook structure | HIGH | MEDIUM | P1 (constraint) |
| XGBoost classifier + features | MEDIUM | MEDIUM | P2 |
| Ensemble + isotonic calibration | MEDIUM | MEDIUM | P2 |
| Reliability diagrams | MEDIUM | LOW | P2 |
| Match leverage analysis | MEDIUM | MEDIUM | P2 |
| Feature importance / SHAP | MEDIUM | LOW | P2 |
| Squad market value (Transfermarkt) | LOW | MEDIUM | P3 |
| Post-mortem | HIGH | LOW | P1 (but time-fixed at end) |

## Competitor Feature Analysis

| Feature | FiveThirtyEight | Groll et al. (academic) | Bookmaker consensus (Zeileis) | Our Approach |
|---------|-----------------|-------------------------|-------------------------------|--------------|
| Strength rating | SPI (off/def, Elo-family) | Covariate set incl. Elo, market value | Implied from de-margined odds | Dynamic Elo + D-C attack/defense |
| Goals model | Poisson from SPI ratings | RF-predicted expected goals → Poisson | Derived from implied abilities | Dixon-Coles bivariate Poisson |
| Tournament sim | ~20k runs, updated per match | 100k runs, pre-tournament | Simulation from odds-implied strengths | ≥10k runs, conditional, per matchday |
| ML layer | No (structural only) | Random forest hybrid | No | XGBoost ensemble over structural baseline |
| Live updating | Yes (flagship) | No (static pre-tournament) | No | Yes — per matchday, conditional |
| Calibration evaluation | Internal, partially published | RPS/log-loss in papers | Log-loss in papers | Live cumulative log-loss/RPS vs market, published per matchday |
| Presentation | Interactive web tables | Paper tables/figures | Paper | Static matplotlib/seaborn reports + didactic notebooks |
| Leverage analysis | Yes ("matches that matter") | No | No | P2 once conditional sim exists |

## Sources

- FiveThirtyEight SPI / World Cup forecast methodology (2018, 2022) — training data; site archived since 2023, methodology stable. Confidence: MEDIUM
- Groll, Ley, Schauberger, Van Eetvelde et al. — hybrid random forest World Cup prediction papers (2018 WC, Euro 2020/2021 versions) — training data. Confidence: MEDIUM
- Leitner, Zeileis, Hornik — bookmaker consensus tournament forecasting — training data. Confidence: MEDIUM
- Dixon & Coles (1997), "Modelling Association Football Scores and Inefficiencies in the Football Betting Market" — canonical, stable. Confidence: HIGH
- Kaggle football prediction competition norms (log-loss scoring, GBM + Elo feature consensus) — training data. Confidence: MEDIUM
- 2026 FIFA format (48 teams, 12 groups, best 8 thirds, 104 matches) — confirmed by project design doc `PROYECTO_MUNDIAL_2026.md`. Confidence: HIGH

**Verification flags (web tools unavailable this session):**
- FIFA's official best-thirds bracket-allocation table for the Round of 32 (exact seeding paths) — verify against FIFA regulations document before implementing `rules_fifa.py`. LOW confidence on exact allocation mechanics.
- Current availability/format of football-data.co.uk or The Odds API for 2026 World Cup odds — verify during data phase. LOW confidence.
- 2026 fair-play tiebreaker point values — verify against official regulations. LOW confidence on exact values.

---
*Feature research for: World Cup 2026 forecasting (CDD-MUNDIAL)*
*Researched: 2026-06-11*
