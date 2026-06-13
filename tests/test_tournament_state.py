"""Wave 0 invariants for the thin conditional tournament state (SIM-03, D-01, D-02)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd
import pytest

from cdd_mundial.data.identities import UnknownTeamError
from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.simulation.state import (
    PlayedMatchResult,
    TournamentState,
    played_results_from_json,
)

CONDITIONED_RESULTS_PATH = Path("tests/fixtures/tournament/conditioned_results.json")


def mini_fixture() -> pd.DataFrame:
    """Minimal frame factory: two resolved group matches plus two open knockout slots."""
    return pd.DataFrame(
        [
            {
                "match_id": "WC26-001",
                "stage": "group",
                "home_team_id": "mexico",
                "away_team_id": "south-africa",
            },
            {
                "match_id": "WC26-002",
                "stage": "group",
                "home_team_id": "south-korea",
                "away_team_id": "czechia",
            },
            {
                "match_id": "WC26-073",
                "stage": "round_of_32",
                "home_team_id": None,
                "away_team_id": None,
            },
            {
                "match_id": "WC26-074",
                "stage": "round_of_32",
                "home_team_id": None,
                "away_team_id": None,
            },
        ]
    )


def group_result(**overrides) -> PlayedMatchResult:
    payload = {
        "match_id": "WC26-001",
        "team_a": "mexico",
        "team_b": "south-africa",
        "goals_a": 2,
        "goals_b": 1,
    }
    payload.update(overrides)
    return PlayedMatchResult(**payload)


# --- Behavior 1: thin state stores only played results keyed by match_id ---


def test_state_stores_only_played_results_keyed_by_match_id() -> None:
    results = [
        group_result(),
        group_result(match_id="WC26-002", team_a="south-korea", team_b="czechia", goals_a=0, goals_b=0),
    ]

    state = TournamentState.from_results(results, fixture=mini_fixture())

    assert set(state.played) == {"WC26-001", "WC26-002"}
    assert state.played["WC26-001"] == results[0]
    assert state.played["WC26-002"] == results[1]


def test_state_has_no_derived_standings_or_bracket_fields() -> None:
    field_names = [field.name for field in dataclasses.fields(TournamentState)]

    assert field_names == ["played"]
    for forbidden in ("standings", "table", "bracket", "qualified", "participants"):
        assert not hasattr(TournamentState, forbidden)


def test_state_normalization_is_deterministic_across_input_order() -> None:
    first = group_result()
    second = group_result(
        match_id="WC26-002", team_a="south-korea", team_b="czechia", goals_a=0, goals_b=0
    )

    forward = TournamentState.from_results([first, second], fixture=mini_fixture())
    reversed_order = TournamentState.from_results([second, first], fixture=mini_fixture())

    assert forward == reversed_order
    assert list(forward.played) == sorted(forward.played)


def test_state_construction_is_seed_free_and_repeatable() -> None:
    # T-03-05: conditioning must be deterministic; rebuilding from the same
    # inputs yields a value-identical state with the fixed scores untouched.
    results = [group_result()]

    one = TournamentState.from_results(results, fixture=mini_fixture())
    two = TournamentState.from_results(results, fixture=mini_fixture())

    assert one == two
    assert one.played["WC26-001"].goals_a == 2
    assert one.played["WC26-001"].goals_b == 1


# --- Behavior 2: invalid inputs fail loudly ---


def test_duplicate_match_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        TournamentState.from_results(
            [group_result(), group_result(goals_a=3)], fixture=mini_fixture()
        )


def test_unknown_team_is_rejected() -> None:
    record = PlayedMatchResult(
        match_id="WC26-073", team_a="atlantis", team_b="canada", goals_a=2, goals_b=0
    )

    with pytest.raises(UnknownTeamError, match="atlantis"):
        TournamentState.from_results([record], fixture=mini_fixture())


def test_unknown_match_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="WC26-999"):
        TournamentState.from_results(
            [group_result(match_id="WC26-999")], fixture=mini_fixture()
        )


def test_negative_goals_are_rejected() -> None:
    with pytest.raises(ValueError, match="goals"):
        group_result(goals_b=-1)


def test_non_integer_goals_are_rejected() -> None:
    with pytest.raises(ValueError, match="goals"):
        group_result(goals_a=1.5)


def test_identical_teams_are_rejected() -> None:
    with pytest.raises(ValueError, match="distinct"):
        group_result(team_b="mexico")


def test_fixture_participant_conflict_is_rejected() -> None:
    conflicting = group_result(team_b="czechia")  # known team, wrong match

    with pytest.raises(ValueError, match="participant"):
        TournamentState.from_results([conflicting], fixture=mini_fixture())


# --- Behavior 3: fair play is explicit observed input, never simulated ---


def test_fair_play_inputs_are_optional_observed_data() -> None:
    with_conduct = group_result(fair_play_a=-1, fair_play_b=-4)
    without_conduct = group_result(match_id="WC26-002", team_a="south-korea", team_b="czechia")

    assert with_conduct.fair_play_a == -1
    assert with_conduct.fair_play_b == -4
    assert without_conduct.fair_play_a is None
    assert without_conduct.fair_play_b is None


def test_positive_fair_play_scores_are_rejected() -> None:
    # Art. 13 conduct scores are deductions (yellow -1 ... yellow + direct red -5).
    with pytest.raises(ValueError, match="fair_play"):
        group_result(fair_play_a=2)


# --- Knockout advancement is recorded state, not resolved bracket logic ---


def test_group_match_cannot_carry_advanced_team() -> None:
    record = group_result(advanced_team="mexico")

    with pytest.raises(ValueError, match="group"):
        TournamentState.from_results([record], fixture=mini_fixture())


def test_drawn_knockout_match_requires_advanced_team() -> None:
    drawn = PlayedMatchResult(
        match_id="WC26-073", team_a="mexico", team_b="south-korea", goals_a=1, goals_b=1
    )

    with pytest.raises(ValueError, match="advanced_team"):
        TournamentState.from_results([drawn], fixture=mini_fixture())


def test_advanced_team_must_be_a_participant() -> None:
    with pytest.raises(ValueError, match="advanced_team"):
        PlayedMatchResult(
            match_id="WC26-073",
            team_a="mexico",
            team_b="canada",
            goals_a=1,
            goals_b=1,
            advanced_team="brazil",
        )


def test_advanced_team_must_match_a_decided_score() -> None:
    with pytest.raises(ValueError, match="advanced_team"):
        PlayedMatchResult(
            match_id="WC26-073",
            team_a="mexico",
            team_b="canada",
            goals_a=2,
            goals_b=0,
            advanced_team="canada",
        )


# --- Fixture-backed construction against the frozen official fixture ---


def test_conditioned_results_fixture_backs_state_construction() -> None:
    results = played_results_from_json(CONDITIONED_RESULTS_PATH)
    fixture = load_fixture_2026()

    state = TournamentState.from_results(results, fixture=fixture)

    assert set(state.played) == {"WC26-001", "WC26-002", "WC26-073"}
    assert state.played["WC26-001"].goals_a == 2
    assert state.played["WC26-001"].fair_play_b == -3
    assert state.played["WC26-002"].goals_a == 0
    assert state.played["WC26-073"].advanced_team == "mexico"


def test_results_json_rejects_unknown_keys(test_workspace: Path) -> None:
    path = test_workspace / "bad_results.json"
    path.write_text(
        '{"results": [{"match_id": "WC26-001", "team_a": "mexico", "team_b": "south-africa", '
        '"goals_a": 1, "goals_b": 0, "winner": "mexico"}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="winner"):
        played_results_from_json(path)
