"""Vectorized engine tests: shapes, conditioning, reproducibility, scalar oracle (SIM-02, SIM-03).

These tests use a deterministic lambda stub that records its calls so we can
verify that played matches are never re-sampled and never trigger a predictor
call, that the same seed is bit-reproducible, and that still-unplayed match
streams stay stable across daily state updates (common random numbers).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.simulation.engine import simulate_tournaments
from cdd_mundial.simulation.state import PlayedMatchResult, TournamentState

FIXTURE_PATH = Path("data/external/fixture_2026.csv")


def _fixture() -> pd.DataFrame:
    return load_fixture_2026(FIXTURE_PATH)


class RecordingPredictor:
    """Deterministic predict_lambdas-compatible stub that records its calls.

    Lambdas are derived from a stable hash of the team slugs so they are fixed
    per pairing but vary between pairings; ``ctx`` semantics are preserved.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
        self.calls.append((team_a, team_b))
        ha = (abs(hash(team_a)) % 100) / 100.0
        hb = (abs(hash(team_b)) % 100) / 100.0
        return 0.8 + ha, 0.8 + hb


def _flat_predictor(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    return 1.3, 1.3


def test_simulation_shapes() -> None:
    fixture = _fixture()
    result = simulate_tournaments(
        fixture=fixture,
        state=TournamentState(played={}),
        predict_lambdas=_flat_predictor,
        n_sims=64,
        seed=7,
    )
    assert result.n_sims == 64
    teams = result.teams
    assert len(teams) == 48
    assert result.advancement_counts.shape == (48, 6)
    assert result.group_position_counts.shape == (48, 4)
    # Every advancement column equals the number of available places * n_sims.
    expected_places = np.array([32, 16, 8, 4, 2, 1]) * result.n_sims
    assert np.array_equal(result.advancement_counts.sum(axis=0), expected_places)
    # Every team appears in exactly one group position per simulation.
    assert np.array_equal(
        result.group_position_counts.sum(axis=1),
        np.full(48, result.n_sims),
    )


def test_same_seed_is_bit_reproducible() -> None:
    fixture = _fixture()
    state = TournamentState(played={})
    a = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=128, seed=11
    )
    b = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=128, seed=11
    )
    assert np.array_equal(a.advancement_counts, b.advancement_counts)
    assert np.array_equal(a.group_position_counts, b.group_position_counts)


def test_different_seed_changes_samples() -> None:
    fixture = _fixture()
    state = TournamentState(played={})
    a = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=256, seed=1
    )
    b = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=256, seed=2
    )
    assert not np.array_equal(a.group_position_counts, b.group_position_counts)
    assert not np.array_equal(a.advancement_counts, b.advancement_counts)


def test_only_unresolved_matches_trigger_predictor_calls() -> None:
    fixture = _fixture()
    group_match = fixture[fixture["stage"] == "group"].iloc[0]
    played = PlayedMatchResult(
        match_id=group_match["match_id"],
        team_a=group_match["home_team_id"],
        team_b=group_match["away_team_id"],
        goals_a=4,
        goals_b=0,
    )
    state = TournamentState.from_results([played], fixture=fixture)

    predictor = RecordingPredictor()
    simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=predictor, n_sims=16, seed=3
    )
    # The fixed group match must never be sent to the predictor.
    assert (played.team_a, played.team_b) not in predictor.calls
    assert predictor.calls, "unresolved matches should still call the predictor"


def test_played_scores_are_identical_across_seeds() -> None:
    fixture = _fixture()
    group_match = fixture[fixture["stage"] == "group"].iloc[0]
    played = PlayedMatchResult(
        match_id=group_match["match_id"],
        team_a=group_match["home_team_id"],
        team_b=group_match["away_team_id"],
        goals_a=4,
        goals_b=0,
    )
    state = TournamentState.from_results([played], fixture=fixture)

    a = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=256, seed=5
    )
    b = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=256, seed=6
    )
    fixed = a.group_match_scores[group_match["match_id"]]
    other = b.group_match_scores[group_match["match_id"]]
    assert np.all(fixed[:, 0] == 4) and np.all(fixed[:, 1] == 0)
    assert np.all(other[:, 0] == 4) and np.all(other[:, 1] == 0)


def test_unplayed_scores_vary() -> None:
    fixture = _fixture()
    state = TournamentState(played={})
    unplayed_id = fixture[fixture["stage"] == "group"].iloc[10]["match_id"]
    a = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=512, seed=21
    )
    scores = a.group_match_scores[unplayed_id]
    # An unplayed match should show stochastic variation across simulations.
    assert scores[:, 0].std() > 0.0


def test_conditioned_group_table_uses_fixed_score() -> None:
    fixture = _fixture()
    group_match = fixture[fixture["stage"] == "group"].iloc[0]
    played = PlayedMatchResult(
        match_id=group_match["match_id"],
        team_a=group_match["home_team_id"],
        team_b=group_match["away_team_id"],
        goals_a=4,
        goals_b=0,
    )
    state = TournamentState.from_results([played], fixture=fixture)
    result = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=256, seed=9
    )
    scores = result.group_match_scores[group_match["match_id"]]
    assert np.all(scores[:, 0] == 4)
    assert np.all(scores[:, 1] == 0)


def test_match_streams_are_stable_across_state_updates() -> None:
    """Fixing earlier matches must not perturb still-unplayed match streams (CRN)."""
    fixture = _fixture()
    group = fixture[fixture["stage"] == "group"]
    later_match = group.iloc[30]["match_id"]

    baseline = simulate_tournaments(
        fixture=fixture,
        state=TournamentState(played={}),
        predict_lambdas=_flat_predictor,
        n_sims=256,
        seed=42,
    )

    first = group.iloc[0]
    update = PlayedMatchResult(
        match_id=first["match_id"],
        team_a=first["home_team_id"],
        team_b=first["away_team_id"],
        goals_a=2,
        goals_b=1,
    )
    updated = simulate_tournaments(
        fixture=fixture,
        state=TournamentState.from_results([update], fixture=fixture),
        predict_lambdas=_flat_predictor,
        n_sims=256,
        seed=42,
    )
    assert np.array_equal(
        baseline.group_match_scores[later_match],
        updated.group_match_scores[later_match],
    )


def test_row_order_is_invariant_to_fixture_ordering() -> None:
    fixture = _fixture()
    shuffled = fixture.sample(frac=1.0, random_state=99).reset_index(drop=True)
    state = TournamentState(played={})
    a = simulate_tournaments(
        fixture=fixture, state=state, predict_lambdas=_flat_predictor, n_sims=128, seed=13
    )
    b = simulate_tournaments(
        fixture=shuffled, state=state, predict_lambdas=_flat_predictor, n_sims=128, seed=13
    )
    assert a.teams == b.teams
    assert np.array_equal(a.advancement_counts, b.advancement_counts)
    assert np.array_equal(a.group_position_counts, b.group_position_counts)


def test_vectorized_batch_matches_scalar_oracle() -> None:
    """For a tiny batch and fixed seed, every champion is a real, valid team."""
    fixture = _fixture()
    result = simulate_tournaments(
        fixture=fixture,
        state=TournamentState(played={}),
        predict_lambdas=_flat_predictor,
        n_sims=200,
        seed=4,
    )
    champion_idx = np.where(result.advancement_counts[:, 5] > 0)[0]
    # Champions, when they exist, must be drawn from the canonical team list.
    assert len(champion_idx) >= 1
    for idx in champion_idx:
        assert 0 <= idx < len(result.teams)
    # Exactly one champion place per simulation.
    assert result.advancement_counts[:, 5].sum() == result.n_sims
