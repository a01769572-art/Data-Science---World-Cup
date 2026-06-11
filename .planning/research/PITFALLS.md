# Pitfalls Research

**Domain:** Football match forecasting (ML + structural models) with Monte Carlo tournament simulation — FIFA World Cup 2026 (48 teams, live-updating)
**Researched:** 2026-06-11
**Confidence:** MEDIUM overall — methodology pitfalls (leakage, Dixon-Coles, calibration, Elo) are HIGH confidence (stable, well-documented literature); exact FIFA 2026 regulation details are flagged LOW and must be verified against the official FIFA regulations PDF during the simulation phase. Web research tools were unavailable this session; findings are from established domain knowledge with explicit verification flags.

## Critical Pitfalls

### Pitfall 1: Temporal data leakage in features, validation, and calibration

**What goes wrong:**
The model looks great in validation (log-loss far below the ~1.0 bookmaker-level benchmark) and then collapses on real tournament matches. Classic leak vectors in this exact project:
- Rolling features (recent form, goals for/against) computed with `pandas.rolling()` **including the current match** (missing `.shift(1)`).
- Elo ratings computed over the **full** history, then "validated" on a subset that contributed to the ratings the model sees.
- FIFA ranking joined as "latest ranking" instead of the ranking **as of the match date** (rankings are monthly point-in-time snapshots).
- Isotonic calibrator fit on the same set used to report metrics — calibration looks perfect because it memorized the test set.
- During the live tournament: re-training/re-calibrating with today's results, then "forecasting" today's matches.

**Why it happens:**
Time-series leakage is invisible in code review of a single line; it only shows as suspiciously good metrics. Random K-fold CV is the sklearn default reflex and silently leaks future matches into training.

**How to avoid:**
- Hard rule: **every feature for match at date t uses only data with date < t**. Implement features via `groupby(team).shift(1)` patterns and audit each feature column with a unit test: recompute one team's feature by hand for a known match.
- Validation = strict temporal splits only (train ≤ cutoff, validate after). Designated holdouts: WC 2018, WC 2022, Euro 2024, Copa América 2024 — never touched during tuning.
- Three-way temporal split: train → calibration set (fit isotonic) → test (report metrics). Never fit the calibrator on the reported set.
- FIFA rankings stored as (date, team, rank) and joined with `merge_asof(direction='backward')`.
- Live mode: forecasts for matchday N are generated and **logged with timestamp before kickoff** using only data through matchday N−1.

**Warning signs:**
- Validation log-loss < ~0.95 on 1/X/2 (bookmakers sit around 0.95–1.00; materially beating them in backtest = almost certainly a leak).
- Accuracy > ~58% on three-class international football.
- A feature with implausibly high XGBoost importance (e.g., "rolling goals" dominating Elo difference).

**Phase to address:**
F1 (Datos/features: shift discipline, point-in-time joins) and F3 (ML: temporal splits, calibration split). Director sign-off on metrics before accepting any model (already a Key Decision in PROJECT.md).

---

### Pitfall 2: Team-name entity mismatch and national-team identity changes across sources

**What goes wrong:**
Silent join failures: "USA" vs "United States" vs "USMNT", "South Korea" vs "Korea Republic" (FIFA official) vs "Korea Rep.", "Iran" vs "IR Iran", "Ivory Coast" vs "Côte d'Ivoire", "Curaçao" with/without diacritics (Curaçao qualified for 2026 — a small team likely to be poorly covered in some sources). A team silently drops out of the Elo merge, gets NaN features, and either crashes the pipeline mid-tournament or — worse — gets imputed default strength and produces absurd forecasts. Deeper version: historical entities — West Germany/Germany, USSR/Russia, Czechoslovakia/Czechia, Yugoslavia/Serbia, Zaire/DR Congo. The Kaggle martj42 dataset, eloratings.net, and FIFA rankings each make **different** continuity decisions, so Elo histories and form features can be built on broken team timelines.

**Why it happens:**
Joins on raw name strings "mostly work" in EDA, so coverage gaps go unnoticed until a specific match fails. Fuzzy matching without human review creates false merges (e.g., "Korea DPR" → "Korea Republic").

**How to avoid:**
- Canonical `teams.csv` master table with one row per current FIFA entity, plus an **alias table** (source, source_name → canonical_id) and a **predecessor map** (West Germany → Germany, etc.) with an explicit, documented continuity decision per lineage.
- **Coverage assertion at ingest:** every source load ends with a test that (a) all 48 World Cup 2026 teams resolve to a canonical id in that source, and (b) the count of unmatched historical names is reported, not silently dropped.
- Fuzzy matching only as a *suggestion* generator (or via Gemini batch as planned); every alias is human-approved and committed to the alias table — never matched on the fly at pipeline runtime.

**Warning signs:**
- Row counts drop after a merge; NaN ratios > 0 in Elo/ranking columns for post-2000 matches; any 2026 participant missing from a per-source coverage report.

**Phase to address:**
F1 (Datos) — the master table and coverage tests must exist before any feature work. This is already flagged in the design doc as "bug source #1"; the addition is the **48-team coverage test as a hard gate**.

---

### Pitfall 3: Mishandling neutral venues and the three-host structure

**What goes wrong:**
Models trained with a generic "home advantage" term applied to World Cup matches, where ~95% of matches are neutral. Result: systematic bias toward the arbitrary "home" team listed first in the fixture. The inverse error also occurs: ignoring home advantage entirely, missing that **Mexico, USA, and Canada play true home matches** in 2026 (host advantage is historically worth roughly +0.4–0.6 goals or ~100 Elo points). Subtle variant: in the martj42 dataset, for `neutral == True` matches the `home_team` column is just the first-listed team; in qualifiers, `country` can equal the home nation even when listed oddly.

**Why it happens:**
Home advantage is the strongest single effect in club football modeling, so tutorials hard-code it. International tournament data breaks the assumption.

**How to avoid:**
- Home advantage as a **conditional** term: full effect when `neutral == False`, zero when neutral, and a separate (smaller or equal) **host** effect for tournament hosts playing in their own country. Encode `is_host_playing_at_home` explicitly from the 2026 fixture (Mexico's matches in Mexico, USA's in USA, Canada's in Canada).
- In Dixon-Coles fitting, estimate the home parameter only from non-neutral matches.
- Verify the neutral flag semantics empirically in EDA: home win rate at neutral vs non-neutral venues (should be ~order 45% non-neutral, ~near-symmetric neutral).

**Warning signs:**
- The first-listed team in neutral fixtures wins more often than the second in your *simulations*; Dixon-Coles home parameter fitted on all matches including neutrals.

**Phase to address:**
F1 (EDA verifies flag semantics), F2 (Elo and Dixon-Coles parameterize home/host correctly).

---

### Pitfall 4: Dixon-Coles misimplementation — independent Poisson in disguise, unstable τ, wrong decay, unidentifiable parameters

**What goes wrong:**
Four distinct failure modes seen in hobbyist DC implementations:
1. **Plain independent Poisson labeled "Dixon-Coles"** — skipping the τ correction for 0-0/1-0/0-1/1-1. Independent Poisson systematically **underestimates draws** (real draw rate ~25–28%; independent Poisson with typical λ gives ~22–24%), which propagates into the group-stage simulation (too few draws → wrong points distributions → wrong third-place dynamics).
2. **Unconstrained ρ** — the τ adjustment is only a valid probability model for ρ within bounds depending on λ; an unconstrained optimizer can produce negative probabilities.
3. **Time decay tuned for club football** — half-lives of ~1 season (ξ ≈ 0.0065/day from the literature) leave a national team with ~5–10 effectively-weighted matches because international teams play ~10 matches/year. International DC needs a much gentler decay (effective half-life of 2–4 years) or the parameters are pure noise.
4. **Identifiability/sparsity:** fitting per-team attack+defense for 200+ national teams with sparse cross-confederation matchups. Teams that fatten stats on weak confederation opponents get inflated attack ratings (the "Oceania qualifier blowout" problem: 10-0 scorelines poison λ estimates). Without a sum constraint on attack/defense the optimization is degenerate.

**Why it happens:**
The 1997 paper and most blog implementations target a closed league (20 clubs, round-robin, dense schedule). International football violates every one of those assumptions.

**How to avoid:**
- Implement τ explicitly; unit-test that the score matrix sums to 1 and that the implied draw probability exceeds the independent-Poisson draw probability for typical λ.
- Constrain ρ in the optimizer (`scipy.optimize` with bounds) and add identifiability constraint (e.g., mean attack = 0).
- Tune ξ by maximizing out-of-sample log-loss on the temporal validation sets — do not copy club-football values. Consider weighting by competition importance (friendlies down-weighted) as in the FIFA-ranking spirit.
- Mitigate sparsity: either (a) shrink attack/defense toward zero (ridge penalty on parameters), or (b) the more robust route for this project — **drive λ from Elo difference** (λ_A = f(Elo_A − Elo_B, host)) fitted on history, and use DC only for the dependence correction. Option (b) sidesteps 400 free parameters and is recommended for the F2 baseline.
- Cap or winsorize training margins (e.g., treat 7-0 as 5-0) so qualifiers' blowouts don't dominate.

**Warning signs:**
- Simulated group stages with <22% draws; any negative cell in the score probability matrix; a non-major nation in the top 10 of fitted attack ratings; λ > 4 for any 2026 group match.

**Phase to address:**
F2 (Baseline). Add a dedicated test module for the score matrix (sums to 1, draw share, τ effect direction).

---

### Pitfall 5: Elo expected score treated as P(win) — the missing draw model

**What goes wrong:**
The Elo formula gives **expected score** E = P(win) + 0.5·P(draw), not P(win). Using E directly as win probability overstates favorites and produces a 2-class view of a 3-class problem. Downstream, the ensemble blends incompatible quantities (Elo "probability" vs true 1/X/2 from DC). A second version: mixing eloratings.net's published ratings (which use their own K, goal-difference multipliers, and home adjustment) with a self-computed Elo on a different scale — the difference-to-probability mapping is then wrong for one of them.

**Why it happens:**
The Elo logistic formula looks like a probability and tutorials present it as one; draws don't exist in chess where Elo conventions originate (with a different meaning).

**How to avoid:**
- Convert Elo difference → (P_win, P_draw, P_loss) via an explicit draw model fitted on history: e.g., ordered logistic on Elo diff, or Davidson/Rao-Kupper extension, or simply binning historical outcomes by Elo-diff and smoothing. Validate that predicted draw share ≈ 26% overall.
- Pick ONE Elo: either scrape eloratings.net as a *feature* (treating it as an external rating, with its scale calibrated empirically) or compute your own from match history (full control, reproducible, no scraping fragility). Recommended: compute your own for the model; use eloratings.net only as a sanity cross-check. Don't average the two.
- Optimize K, home bonus, and competition weights on log-loss of the derived 3-class probabilities, not on rating "accuracy".

**Warning signs:**
- Elo-based P(draw) hard-coded or absent; favorites' implied probabilities consistently above market odds; two Elo columns in the feature table with different scales.

**Phase to address:**
F2 (Baseline Elo) — the draw model is part of the deliverable, not an afterthought.

---

### Pitfall 6: Isotonic calibration overfitting and multiclass normalization breakage

**What goes wrong:**
Isotonic regression is powerful but needs ~1,000+ samples per fit to be stable. Fit on a few hundred international matches it produces a staircase that memorizes the calibration set — calibration plots look perfect in-sample and get **worse** out-of-sample than the uncalibrated model. Multiclass twist: sklearn-style one-vs-rest isotonic per class breaks the sum-to-1 constraint; if you renormalize naively you can *uncalibrate* the classes again. Also: calibrating each ensemble member and then averaging produces an uncalibrated blend (averaging calibrated probabilities ≠ calibrated average).

**Why it happens:**
"Isotonic > Platt" is repeated as a blanket rule; the small-sample caveat (documented in sklearn's own calibration guide) gets dropped.

**How to avoid:**
- With the realistic calibration-set size here (a few hundred competitive matches), **prefer Platt/logistic scaling or temperature scaling**; use isotonic only if the calibration set exceeds ~1,000 matches (possible if calibrating on all internationals 2015+, not just tournaments).
- Calibrate the **final ensemble output once** (not each member), on a temporally held-out calibration window, then renormalize and *re-check* reliability on a further untouched window.
- Track live calibration during the tournament (reliability + cumulative log-loss vs market) — but do NOT re-fit the calibrator on 10 World Cup matches mid-tournament; that's re-introducing the small-sample problem with n=10.

**Warning signs:**
- Calibration curve with long flat steps; calibrated log-loss better than uncalibrated on the calibration set but worse on the test set; ensemble probabilities not summing to 1 before renormalization (silent renorm hides the bug).

**Phase to address:**
F3 (Ensemble + calibración). Decision point: isotonic vs Platt should be an empirical comparison on the temporal validation sets, with isotonic NOT assumed.

---

### Pitfall 7: Tournament rules bugs — FIFA tiebreakers, best-thirds ranking, and the Round-of-32 bracket allocation

**What goes wrong:**
The Monte Carlo engine implements plausible-but-wrong rules, and every downstream probability (advance, champion) is corrupted. Three distinct sub-bugs:
1. **Wrong tiebreaker order.** FIFA World Cup group tiebreakers are NOT the UEFA Euro rules. FIFA order (2018/2022 regulations, expected to carry to 2026 — VERIFY): (1) points; (2) goal difference in **all** group matches; (3) goals scored in all group matches; then, only among still-tied teams: (4) head-to-head points, (5) head-to-head GD, (6) head-to-head goals scored; (7) fair-play points (yellow −1, double-yellow red −3, direct red −4, yellow+direct −5); (8) drawing of lots. Copying Euro logic (head-to-head FIRST) flips qualification in a meaningful fraction of simulated groups. Since cards aren't being modeled, fair-play must be approximated as a random tiebreak — document that simplification.
2. **Best-thirds ranking.** The 8 best thirds across 12 groups are ranked by: points, GD, goals scored, then (per FIFA precedent) fair play and drawing of lots — no head-to-head possible across groups. Easy to get right, easy to forget the tie case.
3. **Bracket allocation of the 8 thirds — the hardest 2026-specific rule.** Which R32 slot each third-placed team occupies **depends on the combination of groups the 8 thirds come from** (C(12,8) = 495 combinations). FIFA's regulations define the allocation (Euro 2016/2024 used a published lookup table for their 15-combination case; FIFA 26 has an analogous annex/procedure constrained so group winners don't face their own group's third, etc.). A naive "assign thirds in ranked order to fixed slots" implementation produces a **wrong bracket in essentially every simulation**, biasing every team's path. This is the single most error-prone piece of the simulator. LOW confidence on the exact published mechanism — **must be verified against the official "FIFA World Cup 26™ Regulations" PDF (and cross-checked with Wikipedia's format article) before coding `rules_fifa.py`.**

**Why it happens:**
The rules live in a legal PDF nobody reads; Euro and World Cup rules are confused constantly; the 48-team thirds allocation is brand-new with no battle-tested open-source reference implementation.

**How to avoid:**
- `rules_fifa.py` as pure functions with an exhaustive unit-test suite: (a) historical group tables with known tiebreak outcomes (e.g., WC 2018 Group H Japan vs Senegal decided on fair play; WC 1990-style three-way ties), (b) synthetic three- and four-way tie cases, (c) thirds-allocation tests against the official table for several specific 8-of-12 combinations.
- As the tournament progresses, **replay-validate**: feed real 2026 group results into the engine and assert it reproduces FIFA's actual published standings and bracket exactly. Any mismatch = stop-the-line bug. (Group stage ends June 27 — this check is free and decisive.)
- Drawing-of-lots tiebreaks must be sampled randomly **per simulation** (not resolved deterministically by team index — see Pitfall 8).

**Warning signs:**
- No test file for rules; bracket slots hard-coded by ranked-third order; simulated R32 pairings disagreeing with any published projection tool; engine output not matching real standings after matchday 2.

**Phase to address:**
F2 (Simulación) — rule verification (fetch official regulations) is a *research prerequisite* of this phase. Replay-validation continues through F4.

---

### Pitfall 8: Monte Carlo noise, systematic tie-bias, and stale-conditioning bugs

**What goes wrong:**
1. **Reporting MC noise as signal.** With N=10,000 sims, a 5% champion probability has standard error ≈ 0.22 pp, but "P(reach semifinal)" day-over-day deltas of ±1 pp are routinely within noise — the matchday report then narrates random fluctuation as "Brazil's chances rose". With independent seeds per day, even *unchanged* inputs produce different headline numbers.
2. **Deterministic tie-breaking bias in vectorized code.** `np.argsort`/`lexsort` on points (and on equal random keys) is stable → ties always resolve toward lower team index. Over 10k sims this systematically inflates alphabetically/index-early teams' advancement by a measurable margin.
3. **Stale conditioning.** Fixing played matches at their real result but forgetting to also update Elo/form/λ from those results (or double-updating: once in the data pipeline and again in the simulator) — the simulation is conditioned on the bracket state but not on the information state, or vice versa.
4. Minor but real: sampling scores from an unbounded Poisson loop vs a truncated score matrix — truncate at ~10 goals and renormalize, or probabilities silently leak.

**Why it happens:**
MC error analysis feels like overkill for a hobby project; vectorization hides per-simulation logic; the "conditional simulation" feature is bolted on after the unconditional engine works.

**How to avoid:**
- N = 100,000 for published reports (vectorized numpy makes this cheap — seconds, not minutes). Report probabilities rounded to a precision consistent with MC error (whole percentage points for round-reach probabilities) and/or include the MC standard error once in the report footer.
- **Common random numbers** for day-over-day comparisons: same `np.random.default_rng(seed)` stream structure so reported *changes* reflect input changes, not resampling. Fixed seed per report is already a project constraint — extend it to "fixed seed + fixed stream layout".
- Break ties with a per-simulation random key as the last sort column (this also implements "drawing of lots" correctly). Test: simulate two identical teams 100k times; advancement must be 50/50 ± MC error.
- Single source of truth for tournament state: a `state` object (played matches, current ratings) built by the data pipeline, consumed read-only by the simulator. The simulator never recomputes ratings.
- Diagnostic invariants asserted after every simulation batch: each sim advances exactly 32 teams to R32, exactly 8 thirds, exactly one champion; per-team probabilities sum correctly across mutually exclusive exit rounds.

**Warning signs:**
- Reports narrating <1 pp changes; champion probabilities differing run-to-run with identical inputs; an obscure team with anomalously high advancement rate (tie-bias smell); P(advance) for all teams in a group not summing to ~2.67 (2 + 8/12 expected qualifiers per group on average — group-level invariant).

**Phase to address:**
F2 (engine + invariants/tests), F4 (common-random-numbers report discipline).

---

### Pitfall 9: Live-updating pipeline breaks mid-tournament (the forecasting-integrity failure)

**What goes wrong:**
The system works on day 1 and degrades during the tournament:
- **Forecasts not logged before kickoff.** If a forecast file can be regenerated after results are known, the calibration tracking and the entire post-mortem are scientifically worthless ("we would have predicted..."). This is the project-killing version because the live tracking is the portfolio's core differentiator.
- **Result-ingestion fragility.** The Kaggle dataset updates with lag; scraping a results page breaks when the site changes markup mid-tournament; an automated source silently misses a match and Elo/conditioning go stale without error.
- **Timezone date bugs.** Matches in Mexico/USA/Canada span UTC−7 to UTC−4; late kickoffs cross UTC midnight, so "yesterday's matches" filtered by naive local date misses or duplicates matches at exactly the moment the daily pipeline runs.
- **Mid-tournament model changes** (F3 ensemble replacing F2 baseline) silently break the comparability of the cumulative log-loss series, making the post-mortem mush.

**Why it happens:**
Express timeline means the pipeline ships without operational hardening; the team is focused on model quality, not forecast bookkeeping.

**How to avoid:**
- **Append-only forecast log** (`forecasts.csv`/parquet: timestamp_utc, model_version, match_id, p1/px/p2, λs) written and **git-committed before each matchday's first kickoff**. The commit hash is the tamper-evidence. This is a tiny artifact with outsized scientific value.
- Manual-entry fallback as a first-class path: 104 matches over 39 days is ~3 results/day — a `results_manual.csv` that the pipeline prefers over scraped data costs minutes and removes the single point of failure. Cache every scrape into `data/raw/` with timestamp (already a project rule).
- All match timestamps stored in UTC; "matchday complete" determined by match IDs from the fixture, never by date arithmetic.
- Version every forecast with `model_version`; when F3 replaces F2, keep producing F2 baseline forecasts in parallel (it's cheap) so the log-loss comparison series is honest and the post-mortem can compare models on identical matches.
- Pipeline ends with a state assertion: number of matches ingested == matches scheduled before now, per the official fixture.

**Warning signs:**
- No `forecasts/` directory by the end of F2; any forecast file regenerated/overwritten after its matchday; pipeline run that requires manual cleanup more than once; Elo table whose last update lags the real schedule.

**Phase to address:**
F2 (forecast log exists from the FIRST published forecast), F4 (operational discipline). The forecast log must be in the F2 exit criteria, not an F4 nicety.

---

### Pitfall 10: Overfitting XGBoost to small international samples — and the draw-class trap

**What goes wrong:**
International football gives ~1,000–4,000 usable competitive matches (depending on era/competition filters) and only ~64–104 matches per World Cup. XGBoost with default depth and 20+ correlated features memorizes idiosyncrasies (specific eras, confederation quirks) and loses to the Elo+DC baseline out-of-sample — but only if you check honestly. Related trap: **the draw class**. Draws are ~26% of matches but almost never the *most likely* single outcome, so (a) accuracy is a useless metric (a model that never predicts draws looks fine), and (b) the ML classifier learns to under-weight draws, skewing simulated group dynamics. Also: tuning hyperparameters against the same validation tournaments repeatedly is selection leakage — with only 4 holdout tournaments, repeated peeking overfits the validation set itself.

**Why it happens:**
Gradient boosting defaults assume 10×–100× more data; portfolio pressure to show "the ML beats the baseline" invites validation-set shopping.

**How to avoid:**
- Constrain the model: depth ≤ 3–4, strong regularization, ≤ ~10 well-motivated features (Elo diff, form, rest, host, importance), early stopping on a *separate* temporal fold. Prefer fewer features over feature creep — the design doc's P2 features (squad value, travel) should enter only if they improve temporal-validation log-loss.
- Pre-register the comparison: ensemble accepted only if it beats/ties the F2 baseline on log-loss across **all four** holdout tournaments (already an F3 exit criterion — keep it hard).
- Limit hyperparameter search budget and log every evaluation against the holdouts; treat the 4th tournament (Copa América 2024) as a final untouched gate if possible.
- Compare predicted vs empirical draw frequency on validation as a standing diagnostic; the ensemble's draw share must land near 24–28%.
- Accept the documented fallback: if ML doesn't beat the baseline, ship the baseline — the design doc already blesses this; resist the portfolio urge to force it.

**Warning signs:**
- ML validation log-loss varies wildly across the four holdout tournaments; feature importance dominated by a P2 feature; predicted draw share < 20%; more than ~3 rounds of hyperparameter tuning against the same holdouts.

**Phase to address:**
F3 (ML + Ensemble), with the pre-registered acceptance gate.

---

### Pitfall 11: Label and score-convention mismatches — penalties recorded as draws, AET vs 90-minute scores, odds conventions

**What goes wrong:**
In the martj42 dataset, knockout matches decided on penalties appear in `results.csv` with the post-extra-time (drawn) score; the shootout winner lives in a separate `shootouts.csv` (VERIFY at ingest — MEDIUM confidence on exact convention). Three resulting bugs: (1) Elo updates that ignore extra time/shootouts vs ones that don't produce different ratings — pick one convention and document it; (2) the 1/X/2 classifier label for knockout matches must be the **90-minute (or 120-minute) result**, consistently — mixing conventions across matches corrupts training labels; (3) betting odds (the Layer C benchmark) are quoted for **90 minutes only** — comparing model log-loss against odds requires the same outcome definition, or the benchmark comparison is invalid. Additionally, de-margining odds naively (proportional normalization) overstates implied longshot probabilities; the bias matters when treating market probabilities as a calibration target.

**Why it happens:**
The 90'/AET/penalties distinction is a domain detail invisible in a quick EDA; odds margin removal looks like a one-liner.

**How to avoid:**
- Ingest-time validation: cross `results.csv` knockout draws against `shootouts.csv`; create explicit columns `outcome_90` (or `outcome_ft` per dataset convention) and `advanced` (who progressed). Train on `outcome_90/ft`; simulate progression with the extra-time/penalty model.
- Document the Elo update convention (recommended: update on the FT result, shootout treated as a draw with the standard eloratings.net-style adjustment, or simply as a draw — but written down and tested).
- For the market benchmark: proportional de-margin is acceptable for a student project, but note the longshot-bias caveat in the report; ensure odds and model probabilities reference the identical outcome definition and identical match set.

**Warning signs:**
- World Cup finals appearing as "draws" in the training labels without a companion progression column; benchmark log-loss computed on a different match subset than the model's.

**Phase to address:**
F1 (ingest validation, outcome columns), F3/F4 (benchmark comparison hygiene).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-coding the 2026 fixture/groups in Python instead of a data file | Ships F2 faster | Unauditable, error-prone updates if FIFA reschedules | Never — fixture belongs in `data/external/` with a pandera schema |
| Skipping the `rules_fifa.py` test suite "until later" | Days saved | Every simulation result untrustworthy; bugs found only when real standings diverge | Never — tests are cheaper than one wrong published report |
| On-the-fly fuzzy name matching at pipeline runtime | No alias-table maintenance | Non-deterministic joins; silent false merges | Never at runtime; OK as one-time suggestion generator |
| Single Elo implementation without parameter optimization (fixed K=32 etc.) | Faster F2 | Mildly worse baseline | OK for first published forecast; optimize in F2→F3 window |
| Ignoring fair-play tiebreaker (no card model) → random tiebreak | Avoids modeling cards | Tiny probability distortion in rare ties | Acceptable permanently — document the simplification |
| Re-training XGBoost mid-tournament on World Cup matches | "Learning from the tournament" | n≈10–60 matches → noise injection; breaks forecast comparability | Never for model weights; only Elo/form state updates per matchday |
| Skipping pandera schemas on processed outputs | Less boilerplate | Silent schema drift breaks the daily pipeline mid-tournament | Never — already a project constraint |
| Notebook-only logic for simulation/rules | Faster iteration | Untestable, unimportable for daily pipeline | EDA only; rules/sim/features must live in `src/` |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Kaggle martj42 dataset | Assuming it updates same-day during the tournament; assuming penalties are in results.csv | Treat as historical backbone only; live results via manual entry/scrape; join shootouts.csv explicitly |
| eloratings.net | Scraping rendered HTML with requests (site is JS-heavy; data loads from backend TSV endpoints) | Inspect network calls for TSV endpoints, or Playwright fallback; cache every pull in `data/raw/`; prefer self-computed Elo for the model |
| FIFA rankings | Using one "current" snapshot for all historical matches; ignoring the 2018 methodology change (pre/post-2018 ranks are different scales) | Point-in-time table + `merge_asof`; use rank *difference* or post-2018-only, or era-normalize |
| Official 2026 fixture (FIFA/Wikipedia) | Scraping once and never re-validating; missing venue→country mapping for host-advantage feature | Versioned static file in `data/external/` + manual review; re-check after group stage for R32 bracket population |
| Betting odds (football-data.co.uk / The Odds API) | Comparing model vs odds on different outcome definitions or different match subsets; ignoring margin | Same matches, same 90-min outcome, de-margined; benchmark only (per Key Decision) |
| MCP Jupyter daily pipeline | State accumulating in a long-lived kernel (stale globals corrupting daily runs) | Daily report notebook runs top-to-bottom from a fresh kernel; logic imported from `src/` |
| Gemini API (name normalization) | Trusting LLM matches without review | LLM output → human-reviewed alias table commit |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Python-loop Monte Carlo (per-sim, per-match loops) | 10k sims takes 30+ min; temptation to cut N | Vectorize across sims (arrays shaped [n_sims, n_matches]); sample all scores at once | At N=10k+ with 104 matches; numba only if vectorization insufficient |
| Refitting Dixon-Coles from scratch daily over full history | Daily pipeline takes too long; skipped updates | DC parameters change negligibly per matchday — refit weekly or use Elo-driven λ; only ratings/state update daily | During F4 daily ops |
| N=10k sims for headline numbers | Day-over-day noise ±0.5–1 pp read as signal | N=100k for reports + common random numbers (cheap once vectorized) | Immediately, for any small-probability team |
| Truncating score matrix too low (max 5 goals) | Probabilities don't sum to 1; mismatched GD distributions | Truncate at 10+ and renormalize; assert matrix sum ≈ 1 | Edge cases with λ > 2.5 |
| Re-reading/parsing raw CSVs every pipeline run | Slow, fragile daily runs | Parquet intermediates (already planned) with extraction metadata | F4 daily cadence |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Kaggle token / Odds API key / Gemini key committed to the public repo | Key abuse; portfolio embarrassment | `.env` outside version control (already planned); pre-commit secret scan before first push since repo is public |
| Versioning scraped data with restrictive licenses (Transfermarkt, odds feeds) in the public repo | Takedown/licensing trouble on a portfolio repo | Keep raw scraped data gitignored; publish only derived aggregates; document sources in README |
| Aggressive scraping of eloratings.net/FIFA during the tournament | IP block exactly when the live pipeline needs data | Cache-first policy, low frequency (1×/day), Playwright fallback, manual fallback |

## UX Pitfalls

(For this project, "UX" = the matchday reports and the pedagogical repo.)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Reporting probabilities with false precision ("Brazil 13.42%") | Readers infer accuracy the MC/model can't support | Whole percentage points; MC standard-error note in footer |
| Narrating MC noise as news ("X's chances rose 0.8 pp") | Misleading day-over-day story | Common random numbers; only narrate changes > 2× MC SE or driven by actual results |
| Probability tables without a baseline comparison | No way to judge if the model is good | Every report shows cumulative log-loss: model vs Elo-only vs market vs uniform |
| Notebooks that show code without interpretation | Fails the project's core pedagogical value | Enforce the MD→code→MD structure as a review checklist item per notebook |
| Hiding misses in the post-mortem | Destroys the portfolio's credibility (the honest post-mortem IS the product) | Pre-registered forecast log makes honesty automatic; report Brier/log-loss per round |

## "Looks Done But Isn't" Checklist

- [ ] **Feature pipeline:** Often missing `shift(1)` on rolling features — verify by hand-recomputing one team's features for one known match date.
- [ ] **Dixon-Coles:** Often actually independent Poisson — verify τ raises draw probability vs independent baseline; verify score matrix sums to 1.
- [ ] **Elo:** Often missing the draw model — verify Elo layer outputs three probabilities summing to 1 with realistic draw share (~26%).
- [ ] **Group resolver:** Often only handles 2-way ties — verify against synthetic 3-way and 4-way tie fixtures and WC 2018 Group H (fair-play case → random-lots simplification documented).
- [ ] **Thirds allocation:** Often "ranked thirds → fixed slots" — verify against the official FIFA 26 allocation annex for ≥3 specific group combinations. (LOW confidence on mechanism; fetch official regulations PDF first.)
- [ ] **Conditional simulation:** Often fixes results but not ratings — verify simulated ratings entering pending matches reflect all played matches exactly once.
- [ ] **Forecast log:** Often forecasts are regenerable post-hoc — verify append-only file committed before kickoff with model_version and UTC timestamp.
- [ ] **Calibration:** Often fit and evaluated on the same data — verify three distinct temporal windows (train/calibrate/test).
- [ ] **Knockout labels:** Often penalties counted as wins in training labels — verify `outcome_ft` vs `advanced` columns are distinct.
- [ ] **Neutral venues:** Often home advantage applied to neutral matches — verify home parameter is zeroed when `neutral == True` and host flag covers Mexico/USA/Canada home venues only.
- [ ] **Daily pipeline:** Often passes only when run manually with cleanup — verify a clean top-to-bottom run from fresh kernel against the fixture-based completeness assertion.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Leakage discovered after publishing forecasts | MEDIUM | Forecast log preserves honest record; fix feature, re-validate on holdouts, version-bump model, document in DECISIONES.md — past forecasts stay as-is (they were honest at the time) |
| Tiebreaker/thirds-allocation bug found mid-tournament | MEDIUM | Replay real results through fixed engine; re-simulate from current state; publish correction note; tests added for the failing case |
| Name-mismatch crash on a matchday | LOW | Add alias to table, re-run pipeline; coverage test prevents recurrence |
| Scraper breaks during tournament | LOW | Manual results entry (~3 matches/day); fix scraper offline |
| Forecast log missing for early matchdays | HIGH (irreversible for those matches) | Cannot recover scientifically — exclude those matchdays from calibration claims; start logging immediately; disclose in post-mortem |
| ML ensemble fails to beat baseline | LOW | By design: ship F2 baseline; document the negative result as a finding (pedagogically valuable) |
| Isotonic calibration degrades live log-loss | LOW | Fall back to Platt or uncalibrated ensemble; calibration layer is swappable by construction |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Temporal leakage | F1 (features) + F3 (validation/calibration splits) | Hand-recompute features for a known match; log-loss in plausible range (≥ ~0.95); Director review of metrics |
| 2. Team-name mismatch | F1 (Datos) | 48-team coverage test passes per source; zero NaN ratings for 2026 participants |
| 3. Neutral/host mishandling | F1 (EDA) + F2 (models) | Home param ≈ 0 effect on neutral matches; host flag audit vs fixture venues |
| 4. Dixon-Coles misimplementation | F2 (Baseline) | Score-matrix unit tests; draw share 24–28% in simulated groups; ξ tuned on temporal validation |
| 5. Elo draw model | F2 (Baseline) | Elo layer emits 3 calibrated-ish probabilities; binned reliability vs Elo diff |
| 6. Calibration overfitting | F3 (Ensemble) | Platt-vs-isotonic comparison on holdouts; reliability on untouched window |
| 7. FIFA rules bugs | F2 (Simulación) — with official-regulations verification as phase prerequisite | `rules_fifa.py` test suite green incl. historical + synthetic ties + thirds-allocation cases; replay matches real 2026 standings |
| 8. Monte Carlo noise/bias | F2 (engine) + F4 (reporting) | Identical-teams 50/50 test; invariant assertions; CRN day-over-day; N=100k reports |
| 9. Live pipeline integrity | F2 (forecast log exists at first forecast) + F4 (ops) | Pre-kickoff git commits of forecasts; fixture-completeness assertion; manual-entry path tested |
| 10. XGBoost overfitting / draw trap | F3 (ML) | Pre-registered gate: beats baseline log-loss on all 4 holdouts; predicted draw share check |
| 11. Label/score conventions | F1 (ingest) + F4 (benchmark) | `outcome_ft` vs `advanced` columns; odds benchmark on identical matches/definitions |

## Sources

- Dixon & Coles (1997), *Modelling Association Football Scores and Inefficiencies in the Football Betting Market* — τ correction, time decay (training knowledge, HIGH confidence on the math).
- Karlis & Ntzoufras bivariate Poisson literature; standard sports-analytics treatments of draw modeling with Elo (Davidson/ordered-logit extensions) — HIGH confidence.
- sklearn calibration documentation guidance on isotonic small-sample overfitting (~<1,000 samples) — HIGH confidence, stable documentation.
- FIFA World Cup 2018/2022 regulations tiebreaker order; WC 2018 Group H fair-play precedent — MEDIUM confidence from training data; **2026-specific regulations (exact tiebreaker text, thirds R32 allocation annex) NOT verified this session — flagged LOW; verify against the official FIFA World Cup 26 Regulations PDF and Wikipedia's 2026 format article before implementing `rules_fifa.py`.**
- martj42/international_results dataset structure (results.csv / shootouts.csv conventions, neutral flag semantics) — MEDIUM confidence; verify at ingest in F1.
- Community post-mortems of public forecasting models (FiveThirtyEight SPI methodology notes, Kaggle WC prediction competition discussions) — MEDIUM confidence, used for the "draw class trap", market-benchmark log-loss range (~0.95–1.0), and live-tracking integrity practices.
- Web research tools (WebSearch/WebFetch) were unavailable in this session; all LOW/MEDIUM items above carry explicit in-phase verification steps as mitigation.

---
*Pitfalls research for: World Cup 2026 ML forecasting + Monte Carlo simulation (CDD-MUNDIAL)*
*Researched: 2026-06-11*
