# Phase 3: Simulador del Torneo - Validation

**Defined:** 2026-06-12
**Framework:** pytest 8.x
**Nyquist status:** Required

## Validation Objective

Every behavior required by `SIM-01` through `SIM-05` must have an automated
test that can fail before its implementation is considered complete. The fast
suite covers rules, state conditioning, output invariants, reproducibility, and
knockout symmetry. Performance and the complete official third-place mapping
are explicit phase gates.

The implementation must preserve the locked decisions in `03-CONTEXT.md`:

- `TournamentState` stores only played results.
- Internal match naming is `team_a` / `team_b`.
- The rules cascade follows verified Art. 13 through conduct score and successive FIFA-ranking editions; it does not invent drawing of lots.
- NumPy vectorization is the primary simulation architecture.
- Knockout slots are resolved from the frozen fixture slot strings.
- Drawn knockout matches use a compact post-90-minute advancement rule, not
  separate extra-time lambdas.
- Outputs contain advancement probabilities and group-position marginals.
- The integral Phase 3 notebook imports production simulation functions, preserves the didactic cell sequence, and is committed with deterministic quick-run outputs.

## Regulatory Gate

The official assignment of the eight best third-placed teams is blocked until
Plan `03-01` captures and pins the official FIFA 2026 regulation or annex that
defines the mapping.

Before tests for the mapping can be marked complete, `03-01` must:

1. Archive the official rule text, URL, retrieval date, and checksum or an
   equivalent immutable evidence record.
2. Encode the complete official mapping as a reviewed fixture or lookup table.
3. Add provenance assertions connecting the test fixture to that source.
4. Demonstrate that every supported set of eight qualifying groups resolves to
   exactly one assignment and that each assigned group is allowed by the
   corresponding fixture slot token.

The existing tokens such as `3ABCDF` are authoritative constraints but are not
by themselves a unique assignment algorithm. No inferred or arbitrary perfect
matching may satisfy `SIM-01`.

## Requirement-to-Test Map

| Requirement | Behavior under test | Test file | Primary tests | Acceptance |
|-------------|---------------------|-----------|---------------|------------|
| SIM-01 | Group table calculation and complete tie-break cascade | `tests/test_rules_fifa.py` | `test_head_to_head_is_applied_first`, `test_residual_tie_reapplies_head_to_head`, `test_conduct_score_breaks_residual_tie`, `test_fifa_ranking_editions_break_final_tie`, `test_three_way_tie`, `test_four_way_tie` | Exact expected ranking for every fixture |
| SIM-01 | Ranking the twelve third-placed teams and selecting eight | `tests/test_rules_fifa.py` | `test_best_thirds_order`, `test_best_thirds_conduct_score`, `test_best_thirds_fifa_ranking_fallback` | Exactly eight qualifiers in correct order |
| SIM-01 | Assigning best thirds to R32 slots | `tests/test_slot_resolution.py` | `test_official_third_place_mapping_cases`, `test_all_official_combinations_resolve_uniquely`, `test_assignment_respects_slot_tokens` | Blocked until regulatory gate `03-01` passes |
| SIM-01 | Winner/loser and group-position fixture references | `tests/test_slot_resolution.py` | `test_group_position_slots`, `test_winner_slots`, `test_loser_slots`, `test_full_bracket_has_no_unresolved_participant_after_prior_rounds` | All 32 R32 entries and later rounds resolve from fixture data |
| SIM-02 | Vectorized complete-tournament simulation | `tests/test_simulation_engine.py` | `test_simulation_shapes`, `test_vectorized_batch_matches_scalar_oracle` | Correct arrays for multiple batch sizes |
| SIM-02 | Runtime target | `tests/test_simulation_performance.py` | `test_10000_tournaments_under_60_seconds`, `test_100000_tournament_target_report` | 10k is a hard gate under 60 s; 100k is measured and reported |
| SIM-02 | Fixed-seed reproducibility and common random numbers | `tests/test_simulation_engine.py` | `test_same_seed_is_bit_reproducible`, `test_different_seed_changes_samples`, `test_match_streams_are_stable_across_state_updates` | Same input and seed produce identical counts and tables |
| SIM-03 | Played matches are fixed and only remaining matches are sampled | `tests/test_tournament_state.py`, `tests/test_simulation_engine.py` | `test_state_stores_only_played_results`, `test_played_scores_are_identical_across_seeds`, `test_unplayed_scores_vary`, `test_conditioned_group_table_uses_fixed_score` | Fixed match scores never change; unplayed matches remain stochastic |
| SIM-04 | Advancement probabilities | `tests/test_simulation_outputs.py` | `test_advancement_output_schema`, `test_round_probability_slot_totals`, `test_round_probabilities_are_monotone` | Valid 48-team probability table with tournament invariants |
| SIM-04 | Group-position marginals | `tests/test_simulation_outputs.py` | `test_group_position_output_schema`, `test_team_position_probabilities_sum_to_one`, `test_position_column_totals` | Four marginals per team; rows and columns satisfy exact totals |
| SIM-05 | Compact stochastic resolution after a 90-minute draw | `tests/test_knockout.py` | `test_draw_always_produces_one_winner`, `test_identical_strength_is_half`, `test_swapping_team_order_complements_probability`, `test_empirical_order_bias_is_within_tolerance` | One winner per simulation and no measurable order bias |
| DOC-01 / D-12-D-15 | Integral simulation notebook | `tests/test_notebooks.py` | `test_phase3_notebook_exists`, `test_phase3_notebook_imports_simulation_package`, `test_phase3_notebook_is_executed`, `test_phase3_notebook_has_configurable_batch_sizes` | One executed didactic notebook backed by production modules |

## Wave 0 Test Files

Create these tests before or with the first implementation task:

| File | Purpose |
|------|---------|
| `tests/test_rules_fifa.py` | Pure group tables, tie cascade, best-third ranking |
| `tests/test_slot_resolution.py` | Fixture token parsing and official third-place assignment |
| `tests/test_tournament_state.py` | Thin played-result state contract and validation |
| `tests/test_simulation_engine.py` | Vectorized sampling, conditioning, seeds, scalar oracle |
| `tests/test_simulation_outputs.py` | Advancement and group-position invariants |
| `tests/test_knockout.py` | Compact post-draw resolver and order symmetry |
| `tests/test_simulation_performance.py` | Marked performance gates and benchmark reporting |
| `tests/test_notebooks.py` | Structural, import, execution-output, configuration, kernel, and hygiene gates for the integral notebook |

## Wave 0 Fixtures

Create deterministic, reviewable fixtures under
`tests/fixtures/tournament/`:

| Fixture | Required contents | Expected assertion |
|---------|-------------------|--------------------|
| `wc2018_group_h.json` | Colombia, Japan, Senegal, Poland results plus fair-play values | Japan ranks above Senegal only at fair play |
| `two_way_head_to_head.json` | Two teams equal on global points, GD, and GF but separated head-to-head | Head-to-head winner ranks first among tied teams |
| `three_way_tie.json` | Three tied teams requiring a mini-table and residual reapplication | Exact documented order |
| `four_way_tie.json` | Four teams tied on initial criteria | Stable complete ranking without dropped teams |
| `fair_play_tie.json` | Deterministic tie through head-to-head with distinct fair-play scores | Better official fair-play score ranks first |
| `fifa_ranking_tie.json` | Teams identical through conduct score with explicit current/previous FIFA rankings | Official ranking-edition fallback produces the expected order |
| `best_thirds.json` | Twelve third-place records covering points, GD, GF, conduct score, and FIFA rankings | Correct ordered top eight |
| `third_place_mapping_official.json` | Official mapping cases and provenance from gate `03-01` | Exact R32 assignment for each selected group set |
| `conditioned_results.json` | At least one played group match and one played knockout match | Played scores and winners remain fixed |

Historical fixture data must be minimal and include an `expected_order` field so
the test does not reconstruct its own expected result using production logic.
Synthetic fixtures must state which criterion is intended to decide the tie.

## Test Design

### SIM-01: Pure Rules

Rules tests must call pure functions with explicit match records, conduct-score
values, and FIFA-ranking editions. They must not load the production model or
run Monte Carlo tournament batches.

Required assertions:

- Group statistics equal hand-calculated points, goals for, goals against, and
  goal difference.
- The global criteria are evaluated before the head-to-head mini-table.
- A mini-table includes only the teams still tied at that step.
- Three-way and four-way ties return each team exactly once.
- Fair play is used only after all score and head-to-head criteria remain tied.
- Residual ties after conduct score use the most recent FIFA ranking and then
  preceding editions in order; missing data fails loudly rather than using randomness.
- Best-third ranking never applies head-to-head across different groups.
- Exactly eight third-placed teams qualify.
- Official R32 assignment is not accepted until the `03-01` regulatory gate is
  represented by `third_place_mapping_official.json`.

### SIM-02: Vectorization, Performance, and Reproducibility

Use a deterministic lambda stub for most engine tests. The stub must return
known values from `(team_a, team_b, ctx)` and record calls so tests can verify
that only unresolved matches require prediction.

A scalar oracle may exist only in tests for small batches. For a fixed seed and
controlled random inputs, compare the vectorized engine against the oracle for
standings, qualifiers, slot resolution, and champions.

Performance criteria:

- Hard gate: 10,000 complete tournament simulations finish in `< 60.0 s`.
- Target measurement: run 100,000 simulations and record elapsed time and peak
  process memory; failure to meet 60 seconds is reported but does not override
  the explicit 10k requirement without a planning decision.
- Benchmark input: frozen 104-match fixture, empty `TournamentState`, fixed
  lambda stub, fixed seed, warm imports excluded from timing.
- Run the hard gate at least three times on the project machine and accept the
  median; no individual run may exceed 75 seconds.
- Mark performance tests `@pytest.mark.performance` so they are excluded from
  the per-task quick suite but included in the phase gate.

Reproducibility criteria:

- Same fixture, model/stub, state, simulation count, and seed produce identical
  integer advancement counts and identical probability tables.
- A different seed changes at least one unplayed score and one aggregate count.
- Played scores are identical for every seed.
- Common-random-number streams for still-unplayed `match_id` values remain
  stable when a daily state update fixes earlier matches.
- Reordering input dataframe rows must not change results after canonical
  ordering by fixture `match_id`.

### SIM-03: Conditional Tournament State

The test state contains played results only. Tests must reject cached standings,
resolved future participants, duplicate `match_id` values, unknown teams,
negative goals, and team identities that conflict with the resolved fixture
participants.

Core conditioning test:

1. Run at least 256 simulations with two different seeds.
2. Fix a completed group match to an asymmetric score such as `4-0`.
3. Assert that every simulation contains exactly that score for that match.
4. Assert that at least one unplayed match differs between the two seeds.
5. Recompute the affected group table from fixture plus state and verify that
   the fixed goals and points appear in all simulations.
6. Fix a knockout result and verify that its recorded winner occupies every
   dependent `Wnn` slot without being resampled.

### SIM-04: Output Invariants

Advancement output must contain one row for each of the 48 canonical teams and
the columns:

`team_id`, `p_r32`, `p_r16`, `p_qf`, `p_sf`, `p_final`, `p_champion`.

Group-position output must contain:

`team_id`, `group`, `p_1st`, `p_2nd`, `p_3rd`, `p_4th`.

For probability tolerance `eps = max(1e-12, 1 / n_sims)`:

- All probabilities are finite and in `[0, 1]`.
- Every `team_id` is unique and belongs to `teams.csv`.
- Per team, `p_r32 >= p_r16 >= p_qf >= p_sf >= p_final >= p_champion`.
- Column totals equal the number of available places within `eps`:
  `sum(p_r32)=32`, `sum(p_r16)=16`, `sum(p_qf)=8`, `sum(p_sf)=4`,
  `sum(p_final)=2`, and `sum(p_champion)=1`.
- For every team, `p_1st + p_2nd + p_3rd + p_4th = 1`.
- Across all teams, each group-position column totals `12`.
- Within each group, each position column totals `1`.
- Counts divided by `n_sims` reproduce the emitted probability values exactly
  within floating-point tolerance.
- No joint group-configuration table is required or emitted.

### SIM-05: Knockout Order Bias

The compact resolver is validated behaviorally, without requiring separate
extra-time lambdas.

Required deterministic properties:

- For any valid inputs, `p_advance_a + p_advance_b = 1`.
- Swapping teams and their 90-minute probabilities gives
  `p_advance_a_swapped = 1 - p_advance_a`.
- Identical teams receive exactly `0.5` theoretical advancement probability.
- Every simulated knockout match produces exactly one winner.

Required statistical property:

- Simulate at least 100,000 post-draw resolutions for identical teams.
- Run both input orders with independent, fixed seeds.
- Each order must produce an empirical Team A advancement rate within `0.005`
  of `0.5`.
- The absolute difference between the two order-normalized rates must be
  `< 0.005`.

This validates the behavioral intent of `SIM-05` while honoring D-07/D-08:
there is stochastic post-draw advancement with no order bias, but no separate
extra-time goal model.

### Integral Phase 3 Notebook

`notebooks/03_simulador_torneo.ipynb` is a required Phase 3 artifact:

- It imports production functions from `cdd_mundial.simulation`; notebook cells
  do not define replacement functions or classes.
- Every code cell follows Markdown `What and why` -> code -> Markdown
  `Interpretation`.
- One visible configuration cell exposes a lightweight default and explicit
  10,000 / 100,000 options.
- The committed file contains non-empty deterministic outputs from the
  lightweight run, including marginal tables, diagnostics, and at least one plot.
- Performance acceptance remains in `tests/test_simulation_performance.py`;
  notebook execution must not force 10k/100k by default.

## Commands

### Per-Task Quick Suite

```powershell
.\.venv\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_rules_fifa.py `
  tests/test_slot_resolution.py `
  tests/test_tournament_state.py `
  tests/test_simulation_engine.py `
  tests/test_simulation_outputs.py `
  tests/test_knockout.py `
  -m "not performance"
```

### Contract Regression Suite

```powershell
.\.venv\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_fixture.py `
  tests/test_dixon_coles.py `
  tests/test_rules_fifa.py `
  tests/test_slot_resolution.py `
  tests/test_tournament_state.py `
  tests/test_simulation_engine.py `
  tests/test_simulation_outputs.py `
  tests/test_knockout.py `
  -m "not performance"
```

### Performance Gate

```powershell
.\.venv\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_simulation_performance.py `
  -m performance
```

### Notebook Gate

```powershell
.\.venv\python.exe -m pytest -q -p no:cacheprovider tests/test_notebooks.py
```

### Full Phase Gate

```powershell
.\.venv\python.exe -m pytest -q -p no:cacheprovider
```

## Execution Cadence

| Checkpoint | Required validation |
|------------|---------------------|
| Every implementation task | Relevant test node plus per-task quick suite |
| Rules and slot-resolution wave | Quick suite and regulatory provenance assertions |
| Engine and state wave | Quick suite plus contract regression suite |
| Output and knockout wave | Quick suite plus all output/symmetry invariants |
| Notebook completion | Notebook gate plus successful deterministic Run All using the lightweight default |
| Phase completion | Regulatory gate passed, full suite green, 10k performance gate green |

## Phase Acceptance Checklist

- [ ] `SIM-01`: Historical and synthetic tie fixtures pass.
- [ ] `SIM-01`: Conduct score and successive FIFA-ranking fallbacks are covered.
- [ ] `SIM-01`: Official best-third assignment gate from Plan `03-01` passes.
- [ ] `SIM-01`: All tested third-place mappings are unique and token-compatible.
- [ ] `SIM-02`: Same-seed results are bit-reproducible.
- [ ] `SIM-02`: Common random numbers remain stable across state updates.
- [ ] `SIM-02`: 10,000 full tournaments complete in under 60 seconds.
- [ ] `SIM-03`: Played group and knockout results are fixed across every seed.
- [ ] `SIM-03`: `TournamentState` contains no derived standings or bracket state.
- [ ] `SIM-04`: Advancement totals and monotonicity invariants pass.
- [ ] `SIM-04`: Group-position row, group, and tournament totals pass.
- [ ] `SIM-05`: Identical teams advance 50/50 within statistical tolerance.
- [ ] `SIM-05`: Swapping team order complements advancement probability.
- [ ] `notebooks/03_simulador_torneo.ipynb` imports production code, is committed executed, and passes `tests/test_notebooks.py`.
- [ ] Existing fixture and Dixon-Coles contract tests remain green.
- [ ] Full repository test suite is green.

## Failure Policy

- A regulatory provenance or official mapping failure blocks `SIM-01` and Phase
  3 completion.
- A deterministic rules, conditioning, output, or symmetry failure blocks the
  implementing task immediately.
- A 10k runtime of 60 seconds or more blocks `SIM-02`.
- A 100k target miss is recorded with timing and profiling evidence; it does
  not block Phase 3 if the 10k hard requirement passes.
- Statistical tests must use fixed seeds and predeclared tolerances. Retrying a
  failed seed until it passes is prohibited.
