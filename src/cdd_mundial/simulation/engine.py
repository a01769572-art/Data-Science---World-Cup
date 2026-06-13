"""Vectorized Monte Carlo tournament engine (SIM-02, SIM-03, D-05).

The engine is NumPy-first: it integer-codes the 48 canonical teams once,
overlays the played results from a :class:`TournamentState`, samples every
unresolved match's score with a seeded :class:`numpy.random.Generator`, and
advances the official bracket entirely on integer index arrays of shape
``(n_sims, ...)``. It never stores derived standings between calls (D-01).

Determinism and common random numbers
-------------------------------------
All randomness derives from a single :class:`numpy.random.SeedSequence`
``base = SeedSequence([seed, _VERSION])``. Every match owns an independent
child stream keyed by its stable ``match_id`` via
``base.spawn`` indexed by a deterministic ``match_id -> ordinal`` table built
once from the canonicalized fixture. Because the ordinal of an unresolved match
does not change when an *earlier* match becomes fixed, fixing matches in a daily
state update never perturbs the still-unplayed match streams (Open Question 3,
T-03-14). Played matches simply skip sampling and overlay their fixed score, so
their stream is consumed by nobody and the rest stay bit-identical.

Group ranking
-------------
Group standings are ranked by the official global criteria
(points -> goal difference -> goals for). Residual exact ties are broken
deterministically by canonical team order so the batch path stays vectorized
and reproducible; the full branchy Article 13 cascade
(head-to-head, conduct score, FIFA-ranking editions) lives in
:mod:`cdd_mundial.simulation.rules_fifa` for the pure-rules contract and exact
unit tests. Simulated matches carry no head-to-head conduct or ranking inputs,
so the global-criteria path is the correct batch behavior.

Third-place assignment
----------------------
The eight best third-placed teams are selected by the same global criteria and
assigned to their Round-of-32 slots through the reviewed official Annexe C
mapping (:mod:`cdd_mundial.simulation.slots`), never re-derived from tokens.
Simulations are grouped by their qualifying-group combination so each unique
combination resolves its assignment once.

Knockouts
---------
Each knockout round resolves both participants from the frozen fixture slot
tokens (D-06), predicts ``(lambda_a, lambda_b)`` per ordered pairing through the
injected ``predict_lambdas`` contract, converts that to a 90-minute win/draw/loss
triple, folds the draw mass with the compact post-draw resolver
(:mod:`cdd_mundial.simulation.knockout`), and samples one advancing team per
simulation from the match-keyed stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from cdd_mundial.models.dixon_coles import score_matrix
from cdd_mundial.simulation.slots import resolve_third_place_assignments

_VERSION = 20260613  # bump only on an intentional stream-breaking change.

_GROUP_LETTERS = "ABCDEFGHIJKL"
_KO_STAGES = (
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "third_place",
    "final",
)
_ADV_COLUMNS = ("p_r32", "p_r16", "p_qf", "p_sf", "p_final", "p_champion")
_MAX_GOALS = 10


@dataclass(frozen=True)
class SimulationResult:
    """Integer advancement and group-position counts plus retained match scores."""

    teams: list[str]
    n_sims: int
    advancement_counts: np.ndarray  # (48, 6): R32, R16, QF, SF, Final, Champion
    group_position_counts: np.ndarray  # (48, 4): 1st, 2nd, 3rd, 4th
    group_match_scores: dict[str, np.ndarray]  # match_id -> (n_sims, 2) goals_a/goals_b
    team_index: dict[str, int]
    group_of_team: dict[str, str]


def _canonical_fixture(fixture: pd.DataFrame) -> pd.DataFrame:
    return fixture.sort_values("match_id").reset_index(drop=True)


def _match_ordinals(fixture: pd.DataFrame) -> dict[str, int]:
    """Stable match_id -> ordinal table; an earlier match's ordinal is fixed."""
    return {match_id: ordinal for ordinal, match_id in enumerate(sorted(fixture["match_id"]))}


def _stream(base: np.random.SeedSequence, ordinal: int) -> np.random.Generator:
    """Independent generator for one match, keyed by its stable ordinal.

    Deriving the child via a fixed ``spawn_key`` (rather than sequential
    ``base.spawn``) makes each match's stream depend only on its own stable
    ordinal, so fixing an earlier match never shifts a later match's stream.
    """
    child = np.random.SeedSequence(entropy=base.entropy, spawn_key=(ordinal,))
    return np.random.default_rng(child)


def _wdl_from_lambdas(lam_a: float, lam_b: float) -> tuple[float, float, float]:
    """90-minute (p_win_a, p_draw, p_win_b) with no low-score correction (rho=0)."""
    matrix = score_matrix(lam_a, lam_b, 0.0, _MAX_GOALS)
    p_a = float(np.tril(matrix, -1).sum())
    p_draw = float(np.trace(matrix))
    p_b = float(np.triu(matrix, 1).sum())
    return p_a, p_draw, p_b


def _advance_prob(lam_a: float, lam_b: float) -> float:
    """P(team_a advances) from a knockout match, draw mass split by strength."""
    p_a, p_draw, p_b = _wdl_from_lambdas(lam_a, lam_b)
    denom = p_a + p_b
    q = 0.5 if denom == 0.0 else p_a / denom
    return p_a + p_draw * q


def simulate_tournaments(
    *,
    fixture: pd.DataFrame,
    state,
    predict_lambdas,
    n_sims: int,
    seed: int,
    neutral: bool = True,
) -> SimulationResult:
    """Run ``n_sims`` complete tournaments conditioned on ``state``.

    ``predict_lambdas`` must honour the frozen
    ``predict_lambdas(team_a, team_b, ctx)`` contract; ``ctx['neutral']`` carries
    host advantage and is not renamed. ``state`` is a
    :class:`~cdd_mundial.simulation.state.TournamentState` of played results.
    """
    if n_sims <= 0:
        raise ValueError(f"n_sims must be positive, got {n_sims}")

    fixture = _canonical_fixture(fixture)
    ordinals = _match_ordinals(fixture)
    base = np.random.SeedSequence([int(seed), _VERSION])
    played = dict(state.played)
    ctx = {"neutral": neutral}

    group_rows = fixture[fixture["stage"] == "group"]
    teams = sorted(set(group_rows["home_team_id"]) | set(group_rows["away_team_id"]))
    team_index = {team: idx for idx, team in enumerate(teams)}
    n_teams = len(teams)

    group_of_team: dict[str, str] = {}
    teams_by_group: dict[str, list[str]] = {letter: [] for letter in _GROUP_LETTERS}
    for row in group_rows.itertuples(index=False):
        for team in (row.home_team_id, row.away_team_id):
            if team not in group_of_team:
                group_of_team[team] = row.group
                teams_by_group[row.group].append(team)

    # --- Group stage: sample every match once, accumulate standings. -------
    points = np.zeros((n_sims, n_teams), dtype=np.int32)
    gd = np.zeros((n_sims, n_teams), dtype=np.int32)
    gf = np.zeros((n_sims, n_teams), dtype=np.int32)
    group_match_scores: dict[str, np.ndarray] = {}

    lambda_cache: dict[tuple[str, str], tuple[float, float]] = {}

    def _lambdas(a: str, b: str) -> tuple[float, float]:
        key = (a, b)
        if key not in lambda_cache:
            lambda_cache[key] = predict_lambdas(a, b, ctx)
        return lambda_cache[key]

    for row in group_rows.itertuples(index=False):
        a, b = row.home_team_id, row.away_team_id
        ia, ib = team_index[a], team_index[b]
        rec = played.get(row.match_id)
        if rec is not None:
            ga = np.full(n_sims, rec.goals_a, dtype=np.int32)
            gb = np.full(n_sims, rec.goals_b, dtype=np.int32)
        else:
            lam_a, lam_b = _lambdas(a, b)
            rng = _stream(base, ordinals[row.match_id])
            ga = rng.poisson(lam_a, size=n_sims).astype(np.int32)
            gb = rng.poisson(lam_b, size=n_sims).astype(np.int32)

        group_match_scores[row.match_id] = np.stack([ga, gb], axis=1)
        gf[:, ia] += ga
        gf[:, ib] += gb
        gd[:, ia] += ga - gb
        gd[:, ib] += gb - ga
        a_win = ga > gb
        b_win = gb > ga
        draw = ~(a_win | b_win)
        points[:, ia] += np.where(a_win, 3, 0) + np.where(draw, 1, 0)
        points[:, ib] += np.where(b_win, 3, 0) + np.where(draw, 1, 0)

    # --- Rank each group: positions[sim, group, pos] = team index. ---------
    group_letters = list(_GROUP_LETTERS)
    group_member_idx = {
        letter: np.array([team_index[t] for t in teams_by_group[letter]], dtype=np.int64)
        for letter in group_letters
    }
    # positions sorted 1st..4th per group, plus a global standings record.
    group_positions = np.empty((n_sims, 12, 4), dtype=np.int64)
    group_position_counts = np.zeros((n_teams, 4), dtype=np.int64)

    # Third-place records for best-third selection.
    third_team = np.empty((n_sims, 12), dtype=np.int64)
    third_key = np.empty((n_sims, 12, 3), dtype=np.int64)  # points, gd, gf

    for g_idx, letter in enumerate(group_letters):
        members = group_member_idx[letter]
        sub_points = points[:, members]
        sub_gd = gd[:, members]
        sub_gf = gf[:, members]
        # Sort key: descending points, gd, gf; deterministic tiebreak by member order.
        # lexsort sorts ascending by last key; we negate to get descending.
        member_order = np.arange(members.size)
        # Build composite sort per sim via lexsort on stacked keys.
        order = np.lexsort(
            (
                np.broadcast_to(member_order, sub_points.shape),
                -sub_gf,
                -sub_gd,
                -sub_points,
            ),
            axis=1,
        )
        ranked_members = members[order]  # (n_sims, 4) team indices, 1st..4th
        group_positions[:, g_idx, :] = ranked_members
        for pos in range(4):
            np.add.at(group_position_counts[:, pos], ranked_members[:, pos], 1)
        third = ranked_members[:, 2]
        third_team[:, g_idx] = third
        sim_rows = np.arange(n_sims)
        third_key[:, g_idx, 0] = points[sim_rows, third]
        third_key[:, g_idx, 1] = gd[sim_rows, third]
        third_key[:, g_idx, 2] = gf[sim_rows, third]

    # --- Best 8 of 12 third-placed teams. ----------------------------------
    # Rank the 12 thirds per sim by (points, gd, gf), tiebreak by group order.
    g_order = np.broadcast_to(np.arange(12), (n_sims, 12))
    thirds_rank = np.lexsort(
        (g_order, -third_key[:, :, 2], -third_key[:, :, 1], -third_key[:, :, 0]),
        axis=1,
    )  # (n_sims, 12) group-slot indices best..worst
    qualifying_group_slots = np.sort(thirds_rank[:, :8], axis=1)  # group indices, sorted

    # --- Resolve R32 participants per simulation. --------------------------
    # Group-position participant lookup: pos_participant[sim, group, pos]
    advancement_counts = np.zeros((n_teams, 6), dtype=np.int64)

    # R32 reached: all 32 group-stage qualifiers (positions 1 and 2 of every
    # group, plus the eight best thirds).
    for g_idx in range(12):
        advancement_counts[:, 0] += group_position_counts_at(group_positions, g_idx, 0, n_teams)
        advancement_counts[:, 0] += group_position_counts_at(group_positions, g_idx, 1, n_teams)
    # eight best thirds reach R32:
    sim_rows = np.arange(n_sims)
    for slot in range(8):
        g_sel = qualifying_group_slots[:, slot]
        teams_sel = third_team[sim_rows, g_sel]
        np.add.at(advancement_counts[:, 0], teams_sel, 1)

    # Build the R32 participant matrix from fixture slot tokens, vectorized.
    third_assign_cache: dict[str, dict[str, str]] = {}

    def _assignment_for(combo_letters: str) -> dict[str, str]:
        if combo_letters not in third_assign_cache:
            third_assign_cache[combo_letters] = resolve_third_place_assignments(combo_letters)
        return third_assign_cache[combo_letters]

    ko_rows = {
        stage: fixture[fixture["stage"] == stage].sort_values("match_id")
        for stage in _KO_STAGES
    }

    # participants[match_id] = (n_sims,) team index for home_slot/away_slot
    participants: dict[str, np.ndarray] = {}
    winner_of: dict[str, np.ndarray] = {}
    loser_of: dict[str, np.ndarray] = {}

    # Precompute combo strings per sim (sorted qualifying group letters).
    combo_letters_per_sim = np.array(
        ["".join(_GROUP_LETTERS[g] for g in row) for row in qualifying_group_slots]
    )
    unique_combos, combo_inverse = np.unique(combo_letters_per_sim, return_inverse=True)
    # For each R32 match needing a third place, map sim -> assigned group letter.

    def _group_position_team(group_letter: str, position: int) -> np.ndarray:
        g_idx = group_letters.index(group_letter)
        return group_positions[:, g_idx, position - 1]

    def _third_team_for_match(match_id: str) -> np.ndarray:
        out = np.empty(n_sims, dtype=np.int64)
        for c_idx, combo in enumerate(unique_combos):
            assignment = _assignment_for(combo)
            group_letter = assignment[match_id]
            mask = combo_inverse == c_idx
            g_idx = group_letters.index(group_letter)
            out[mask] = group_positions[mask, g_idx, 2]
        return out

    def _resolve_slot_vector(slot: str, match_id: str) -> np.ndarray:
        prefix = slot[0]
        if prefix in {"1", "2", "4"}:
            return _group_position_team(slot[1], int(slot[0]))
        if prefix == "3":
            return _third_team_for_match(match_id)
        if prefix == "W":
            return winner_of[f"WC26-{int(slot[1:]):03d}"]
        if prefix == "L":
            return loser_of[f"WC26-{int(slot[1:]):03d}"]
        raise ValueError(f"unsupported slot token {slot!r}")

    adv_col_by_winner_stage = {
        "round_of_32": 1,  # winning R32 reaches R16
        "round_of_16": 2,  # winning R16 reaches QF
        "quarterfinal": 3,  # winning QF reaches SF
        "semifinal": 4,  # winning SF reaches Final
        "final": 5,  # winning the final is champion
    }

    for stage in _KO_STAGES:
        for row in ko_rows[stage].itertuples(index=False):
            a_idx = _resolve_slot_vector(row.home_slot, row.match_id)
            b_idx = _resolve_slot_vector(row.away_slot, row.match_id)
            participants[row.match_id] = a_idx

            rec = played.get(row.match_id)
            if rec is not None:
                # A played knockout match fixes its real participants and the
                # recorded advancing side across every simulation, regardless of
                # the simulated slot resolution.
                advanced = team_index[rec.advanced_team]
                other = team_index[rec.team_b if rec.advanced_team == rec.team_a else rec.team_a]
                winners = np.full(n_sims, advanced, dtype=np.int64)
                losers = np.full(n_sims, other, dtype=np.int64)
            else:
                # Predict per unique ordered pairing; vectorize advance probability.
                q = _ko_advance_probabilities(
                    a_idx, b_idx, teams, _lambdas, n_sims
                )
                rng = _stream(base, ordinals[row.match_id])
                advancer_is_a = rng.random(n_sims) < q
                winners = np.where(advancer_is_a, a_idx, b_idx)
                losers = np.where(advancer_is_a, b_idx, a_idx)
            winner_of[row.match_id] = winners
            loser_of[row.match_id] = losers

            if stage in adv_col_by_winner_stage:
                col = adv_col_by_winner_stage[stage]
                np.add.at(advancement_counts[:, col], winners, 1)

    return SimulationResult(
        teams=teams,
        n_sims=n_sims,
        advancement_counts=advancement_counts,
        group_position_counts=group_position_counts,
        group_match_scores=group_match_scores,
        team_index=team_index,
        group_of_team=group_of_team,
    )


def group_position_counts_at(
    group_positions: np.ndarray, g_idx: int, position: int, n_teams: int
) -> np.ndarray:
    """Count, per team, how often it finished ``position`` in group ``g_idx``."""
    out = np.zeros(n_teams, dtype=np.int64)
    np.add.at(out, group_positions[:, g_idx, position], 1)
    return out


def _ko_advance_probabilities(
    a_idx: np.ndarray,
    b_idx: np.ndarray,
    teams: list[str],
    lambdas_fn,
    n_sims: int,
) -> np.ndarray:
    """P(team_a advances) for each simulation, cached per ordered (a, b) pairing."""
    q = np.empty(n_sims, dtype=float)
    pairs = np.stack([a_idx, b_idx], axis=1)
    unique_pairs, inverse = np.unique(pairs, axis=0, return_inverse=True)
    for p_idx, (ai, bi) in enumerate(unique_pairs):
        lam_a, lam_b = lambdas_fn(teams[ai], teams[bi])
        q_val = _advance_prob(lam_a, lam_b)
        q[inverse == p_idx] = q_val
    return q
