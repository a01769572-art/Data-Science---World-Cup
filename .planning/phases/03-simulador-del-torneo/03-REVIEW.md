---
phase: 03-simulador-del-torneo
reviewed: 2026-06-12T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - src/cdd_mundial/simulation/__init__.py
  - src/cdd_mundial/simulation/engine.py
  - src/cdd_mundial/simulation/knockout.py
  - src/cdd_mundial/simulation/outputs.py
  - src/cdd_mundial/simulation/rules_fifa.py
  - src/cdd_mundial/simulation/slots.py
  - src/cdd_mundial/simulation/state.py
  - notebooks/03_simulador_torneo.ipynb
  - pyproject.toml
  - tests/test_knockout.py
  - tests/test_notebooks.py
  - tests/test_rules_fifa.py
  - tests/test_simulation_engine.py
  - tests/test_simulation_outputs.py
  - tests/test_simulation_performance.py
  - tests/test_slot_resolution.py
  - tests/test_tournament_state.py
  - tests/validators/assert_phase03_red.py
  - tests/validators/validate_third_place_mapping.py
findings:
  critical: 1
  warning: 6
  info: 5
  total: 12
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

The Phase 3 tournament simulator is well-architected and the documented invariants
(deterministic SeedSequence keyed by stable match ordinal, played-match conditioning
that skips sampling, FIFA Article 13 cascade isolated to the pure-rules module,
Annexe C third-place mapping consumed rather than re-derived) are largely honored.
The supplied test suite is genuinely strong: 18 engine/output tests pass against the
real fixture, and CRN stability across daily state updates is exercised directly.

That said, this review found one blocker and several quality defects. The blocker is a
latent NumPy-version incompatibility in the knockout advancement vectorization that
will crash the engine under the lower half of the project's own declared dependency
range. The remaining findings are dead code paths, a misleading docstring claim about
group ranking that does not match the implemented behavior, missing-key crash surfaces
in the rules module, and a fragility in third-place resolution if it is ever called for
a non-R32 match. None of the warnings change current passing-test behavior, but several
are real correctness traps for the next phase.

## Critical Issues

### CR-01: `_ko_advance_probabilities` crashes on numpy 2.0/2.1, which `pyproject.toml` permits

**File:** `src/cdd_mundial/simulation/engine.py:399-405`
**Issue:**
The function relies on the 1-D shape of the `inverse` array returned by
`np.unique(pairs, axis=0, return_inverse=True)`:

```python
unique_pairs, inverse = np.unique(pairs, axis=0, return_inverse=True)
for p_idx, (ai, bi) in enumerate(unique_pairs):
    ...
    q[inverse == p_idx] = q_val   # q is 1-D (n_sims,)
```

In NumPy **2.0 and 2.1** a regression made `return_inverse` with `axis=0` return a
*2-D* array of shape `(n_sims, 1)` instead of `(n_sims,)`. `pyproject.toml` declares
`numpy>=2,<2.5` (line 12), so installing on 2.0.x or 2.1.x is allowed by the project's
own pin. Under those versions `q[inverse == p_idx]` raises
`IndexError: too many indices for array: array is 1-dimensional, but 2 were indexed`
(reproduced locally), so **every knockout round crashes** and no tournament can be
simulated. The CI/dev box happens to run 2.4.6 (where the bug was fixed in 2.2), which
is why the tests pass today — this is a classic "works on my machine" version trap.

**Fix:** Flatten the inverse defensively so the code is correct across the entire
declared range (and bump the pin floor):

```python
unique_pairs, inverse = np.unique(pairs, axis=0, return_inverse=True)
inverse = np.asarray(inverse).reshape(-1)   # 1-D on every numpy in [2.0, 2.4]
for p_idx, (ai, bi) in enumerate(unique_pairs):
    lam_a, lam_b = lambdas_fn(teams[int(ai)], teams[int(bi)])
    q[inverse == p_idx] = _advance_prob(lam_a, lam_b)
```

Optionally tighten `pyproject.toml` to `numpy>=2.2,<2.5` to exclude the broken minors,
but the `.reshape(-1)` fix is the robust one.

## Warnings

### WR-01: Engine group-ranking docstring claims a tiebreak that the code does not implement

**File:** `src/cdd_mundial/simulation/engine.py:21-30` (docstring) vs `:226-247` (code)
**Issue:**
The module docstring states group standings are ranked by
"points -> goal difference -> goals for. Residual exact ties are broken
deterministically by canonical team order." The lexsort at lines 235-243 actually breaks
residual ties by **intra-group member position** (`member_order = np.arange(members.size)`),
which is the order teams were appended to `teams_by_group` while iterating group rows —
*not* canonical (alphabetical) team order. Because `teams` is sorted (line 162) but
`teams_by_group` is populated in fixture-row encounter order (lines 168-172), the
residual-tie order is fixture-driven, not canonical. The result is still deterministic
(so `test_row_order_is_invariant_to_fixture_ordering` passes on aggregate counts), but a
documented guarantee ("canonical team order") is false and could mislead Phase 4 work
that relies on it.

**Fix:** Either build `member_order` from the global canonical index so the tiebreak is
truly canonical, e.g.

```python
member_order = members  # already global team indices, ascending == canonical
order = np.lexsort((np.broadcast_to(member_order, sub_points.shape),
                    -sub_gf, -sub_gd, -sub_points), axis=1)
```

or correct the docstring to say "residual ties broken by ascending global team index."
(`members` is already sorted ascending in `group_member_idx`, so using it directly makes
the docstring true.)

### WR-02: Dead `participants` dict — both KO participants are never retained despite the docstring

**File:** `src/cdd_mundial/simulation/engine.py:293-294, 343`
**Issue:**
`participants: dict[str, np.ndarray]` is created and written
(`participants[row.match_id] = a_idx`) but never read anywhere in the module
(confirmed by grep). Worse, only `a_idx` is stored — `b_idx` is dropped — so even if a
consumer existed, the "both participants" the module docstring (line 42) advertises are
not actually retained. This is dead state that implies a feature (recoverable per-match
participants) that does not exist.

**Fix:** Remove the dict and the assignment, or, if Phase 4 needs per-match participants,
store the ordered pair and expose it on `SimulationResult`:
```python
participants[row.match_id] = np.stack([a_idx, b_idx], axis=1)
```

### WR-03: `rank_group` raises `KeyError` instead of a clear error on incomplete `conduct_scores`/`fifa_ranking_editions`

**File:** `src/cdd_mundial/simulation/rules_fifa.py:151, 173`
**Issue:**
`_resolve_tail` does `conduct_scores[team]` and `_resolve_by_fifa_ranking` does
`edition[team]`. If a caller passes a `conduct_scores` map or a ranking edition missing
any tied team, Python raises a bare `KeyError(team)` with no context, deep inside
recursion. Given the module's stated fail-loud philosophy and that these inputs are
hand-assembled regulatory data, a missing key is a plausible operator error that
currently surfaces as an opaque stack trace.

**Fix:** Validate presence up front in `rank_group`/`rank_best_thirds` (or use a guarded
lookup) and raise a descriptive `ValueError`:
```python
missing = [t for t in teams if t not in conduct_scores]
if missing:
    raise ValueError(f"conduct_scores missing teams required to break a tie: {missing}")
```

### WR-04: `_third_team_for_match` assumes every passed `match_id` is a third-place R32 slot

**File:** `src/cdd_mundial/simulation/engine.py:309-317`
**Issue:**
`_third_team_for_match` does `assignment[match_id]` for every unique combo. The
`assignment` only contains the 8 R32 third-place match_ids. It is safe today because
`_resolve_slot_vector` only routes here when a slot token starts with `"3"` and such
tokens appear exclusively on R32 away slots. But the coupling is implicit: if a future
fixture revision (or a test) ever feeds a `"3.."` token on a non-R32 match, this raises a
bare `KeyError(match_id)` rather than a meaningful diagnostic. The pure-rules
`slots.resolve_slot` already guards this case explicitly (`slots.py:157-160`); the engine
path does not.

**Fix:** Guard the lookup and fail loudly with context:
```python
if match_id not in assignment:
    raise ValueError(f"no third-place assignment for knockout match {match_id!r}")
```

### WR-05: Played knockout result trusts `goals`/`advanced_team` but silently ignores the simulated bracket participants

**File:** `src/cdd_mundial/simulation/engine.py:345-353`
**Issue:**
When a knockout match is played, the engine overwrites winners/losers with the recorded
real teams across **all** `n_sims`, regardless of who the simulated bracket sent to that
slot (documented as intended conditioning). However, it never checks that the recorded
`team_a`/`team_b` are consistent with `a_idx`/`b_idx` in the simulations where the bracket
is deterministic (e.g. when upstream matches are also fixed). A typo in conditioned data
(recording a team that cannot reach that slot) is accepted silently and corrupts every
downstream count with no signal. `TournamentState.from_results` validates teams against
*fixture* participants, but KO fixture rows have null participants, so that guard does not
fire for knockout conditioning.

**Fix:** When the upstream matches feeding this slot are themselves fully fixed (so
`a_idx`/`b_idx` are constant across sims), assert the recorded participants match the
deterministically-resolved ones, or at minimum log/raise when the recorded teams never
appear among the resolved `{a_idx, b_idx}` in any simulation.

### WR-06: `advance_probability` shrink default of 1.0 silently disables the documented shrinkage and is wired nowhere

**File:** `src/cdd_mundial/simulation/knockout.py:49-75` vs `engine.py:118-123`
**Issue:**
`knockout.advance_probability`/`post_draw_advance_probability` expose a `shrink`
parameter (default 1.0 = no shrinkage). The engine does **not** use these public
functions at all — it reimplements the draw split inline in `_advance_prob`
(engine.py:118-123) with no `shrink` knob. So the reviewed, unit-tested `shrink` feature
is dead with respect to the actual simulation path, and the engine carries a second,
parallel implementation of the same math. Two implementations of one rule is a drift
hazard (e.g. CR-01-style fixes would have to be applied twice).

**Fix:** Have the engine call `knockout.advance_probability(p_a, p_draw, p_b, shrink=...)`
so there is a single source of truth, and thread a `shrink` argument through
`simulate_tournaments` if it is meant to be configurable (or delete `shrink` if Phase 3
deliberately fixes it at 1.0).

## Info

### IN-01: Unused import `combinations`

**File:** `src/cdd_mundial/simulation/engine.py:53`
**Issue:** `from itertools import combinations` is never used in the module.
**Fix:** Remove the import (ruff would flag this as F401).

### IN-02: Unused module constant `_ADV_COLUMNS`

**File:** `src/cdd_mundial/simulation/engine.py:72`
**Issue:** `_ADV_COLUMNS` is defined in `engine.py` but never referenced; the canonical
copy lives in `outputs.py` (`_ADVANCEMENT_COLUMNS`).
**Fix:** Delete the dead constant from `engine.py`.

### IN-03: Unreachable branch in `_resolve_head_to_head`

**File:** `src/cdd_mundial/simulation/rules_fifa.py:129-132`
**Issue:** Inside the `for block in blocks:` loop, `if len(block) == len(teams):` can only
be true when `len(blocks) == 1`, but that case already returned at lines 123-125. So in
the `len(blocks) > 1` path this branch never executes — dead code.
**Fix:** Remove the `len(block) == len(teams)` check inside the loop (the loop body can
unconditionally recurse via `_resolve_head_to_head`), or add a comment explaining the
defensive intent.

### IN-04: Magic number `_MAX_GOALS = 10` duplicated across modules

**File:** `src/cdd_mundial/simulation/engine.py:73` and `models/dixon_coles.py:209,221`
**Issue:** The 10-goal scoreline cap is hardcoded independently in the engine and in
`dixon_coles.score_matrix`. If one is changed without the other, the engine's knockout
WDL and the model's WDL silently diverge.
**Fix:** Import/share a single `MAX_GOALS` constant from `dixon_coles`.

### IN-05: `score_matrix` is recomputed per unique knockout pairing with no memoization across rounds

**File:** `src/cdd_mundial/simulation/engine.py:401-404` (and `_advance_prob`)
**Issue:** (Quality, not performance-in-scope.) `_advance_prob` rebuilds an 11x11 PMF
matrix for every unique pairing in every KO round; the same `(team_a, team_b)` ordered
pair recomputed in different rounds is not cached, unlike the group-stage `lambda_cache`.
Cosmetic now, but the asymmetry (lambdas cached, WDL not) is easy to misread.
**Fix:** If desired, add a small `dict[(ai,bi)] -> q` cache mirroring `lambda_cache`.

---

_Reviewed: 2026-06-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
