"""Output-table invariants for advancement and group-position marginals (SIM-04).

These tests assert structural invariants (totals, monotonicity, bounds,
uniqueness) rather than exact Monte Carlo values, exactly as the validation
plan requires. They run a small deterministic simulation and then check the
emitted tables.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.simulation.engine import simulate_tournaments
from cdd_mundial.simulation.outputs import (
    advancement_table,
    group_position_table,
)
from cdd_mundial.simulation.state import TournamentState

FIXTURE_PATH = Path("data/external/fixture_2026.csv")
TEAMS_PATH = Path("data/external/teams.csv")

_ADV_COLUMNS = ["team_id", "p_r32", "p_r16", "p_qf", "p_sf", "p_final", "p_champion"]
_GROUP_COLUMNS = ["team_id", "group", "p_1st", "p_2nd", "p_3rd", "p_4th"]


def _flat_predictor(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    return 1.3, 1.3


def _result(n_sims: int = 512, seed: int = 7):
    fixture = load_fixture_2026(FIXTURE_PATH)
    return simulate_tournaments(
        fixture=fixture,
        state=TournamentState(played={}),
        predict_lambdas=_flat_predictor,
        n_sims=n_sims,
        seed=seed,
    )


def _known_teams() -> set[str]:
    teams = pd.read_csv(TEAMS_PATH)
    return set(teams["team_id"])


def test_advancement_output_schema() -> None:
    table = advancement_table(_result())
    assert list(table.columns) == _ADV_COLUMNS
    assert len(table) == 48
    assert table["team_id"].is_unique
    known = _known_teams()
    assert set(table["team_id"]) <= known
    values = table[_ADV_COLUMNS[1:]].to_numpy()
    assert np.all(np.isfinite(values))
    assert np.all((values >= 0.0) & (values <= 1.0))


def test_round_probability_slot_totals() -> None:
    result = _result()
    table = advancement_table(result)
    eps = max(1e-12, 1.0 / result.n_sims)
    expected = {"p_r32": 32, "p_r16": 16, "p_qf": 8, "p_sf": 4, "p_final": 2, "p_champion": 1}
    for col, total in expected.items():
        assert abs(table[col].sum() - total) <= eps, col


def test_round_probabilities_are_monotone() -> None:
    table = advancement_table(_result())
    cols = ["p_r32", "p_r16", "p_qf", "p_sf", "p_final", "p_champion"]
    values = table[cols].to_numpy()
    diffs = values[:, :-1] - values[:, 1:]
    assert np.all(diffs >= -1e-12), "round probabilities must be non-increasing per team"


def test_group_position_output_schema() -> None:
    table = group_position_table(_result())
    assert list(table.columns) == _GROUP_COLUMNS
    assert len(table) == 48
    assert table["team_id"].is_unique
    assert set(table["group"]) == set("ABCDEFGHIJKL")
    values = table[["p_1st", "p_2nd", "p_3rd", "p_4th"]].to_numpy()
    assert np.all(np.isfinite(values))
    assert np.all((values >= 0.0) & (values <= 1.0))


def test_team_position_probabilities_sum_to_one() -> None:
    result = _result()
    table = group_position_table(result)
    eps = max(1e-12, 1.0 / result.n_sims)
    row_sums = table[["p_1st", "p_2nd", "p_3rd", "p_4th"]].sum(axis=1).to_numpy()
    assert np.all(np.abs(row_sums - 1.0) <= eps)


def test_position_column_totals() -> None:
    result = _result()
    table = group_position_table(result)
    eps = max(1e-12, 1.0 / result.n_sims)
    # Each position column totals 12 across all teams.
    for col in ("p_1st", "p_2nd", "p_3rd", "p_4th"):
        assert abs(table[col].sum() - 12) <= eps, col
    # Within each group each position column totals 1.
    for _, sub in table.groupby("group"):
        for col in ("p_1st", "p_2nd", "p_3rd", "p_4th"):
            assert abs(sub[col].sum() - 1.0) <= eps, col


def test_counts_divided_by_n_sims_reproduce_probabilities() -> None:
    result = _result()
    table = advancement_table(result)
    expected = result.advancement_counts / result.n_sims
    # team order in the table matches result.teams
    assert table["team_id"].tolist() == result.teams
    got = table[["p_r32", "p_r16", "p_qf", "p_sf", "p_final", "p_champion"]].to_numpy()
    assert np.allclose(got, expected, atol=1e-12)


def test_no_joint_group_configuration_table_is_emitted() -> None:
    import cdd_mundial.simulation.outputs as outputs

    public = {name for name in dir(outputs) if not name.startswith("_")}
    forbidden = {"joint_group_table", "group_configuration_table", "joint_table"}
    assert not (public & forbidden)
