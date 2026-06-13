"""Stable marginal probability tables from a simulation run (SIM-04, D-09..D-11).

The engine returns integer count arrays; this module turns them into the two
user-facing marginal tables the roadmap requires, with explicit column ordering
and deterministic per-team rows:

* :func:`advancement_table` -- per-team ``P(R32)``..``P(Campeon)`` (D-09).
* :func:`group_position_table` -- per-team group-position marginals
  ``P(1st)``..``P(4th)`` (D-10).

No joint group-configuration table is produced (D-11): only per-team marginals.
The output layer is intentionally separate from the engine loop and performs
counts-to-probabilities conversion deterministically, so the same counts always
yield byte-identical tables.
"""

from __future__ import annotations

import pandas as pd

from cdd_mundial.simulation.engine import SimulationResult

_ADVANCEMENT_COLUMNS = ["team_id", "p_r32", "p_r16", "p_qf", "p_sf", "p_final", "p_champion"]
_GROUP_POSITION_COLUMNS = ["team_id", "group", "p_1st", "p_2nd", "p_3rd", "p_4th"]


def advancement_table(result: SimulationResult) -> pd.DataFrame:
    """Per-team round-advancement probabilities, one row per canonical team.

    Rows follow ``result.teams`` order. Columns are ``team_id`` plus
    ``p_r32``, ``p_r16``, ``p_qf``, ``p_sf``, ``p_final``, ``p_champion``.
    Probabilities are counts divided by ``n_sims`` and are non-increasing across
    rounds for every team by construction (reaching a later round implies
    reaching every earlier one).
    """
    probs = result.advancement_counts / result.n_sims
    frame = pd.DataFrame(
        {
            "team_id": result.teams,
            "p_r32": probs[:, 0],
            "p_r16": probs[:, 1],
            "p_qf": probs[:, 2],
            "p_sf": probs[:, 3],
            "p_final": probs[:, 4],
            "p_champion": probs[:, 5],
        }
    )
    return frame[_ADVANCEMENT_COLUMNS]


def group_position_table(result: SimulationResult) -> pd.DataFrame:
    """Per-team group-position marginals, one row per canonical team.

    Columns are ``team_id``, ``group`` plus ``p_1st``..``p_4th``. Each team's
    four position probabilities sum to one, every group's position columns each
    sum to one, and each position column totals twelve across the field.
    """
    probs = result.group_position_counts / result.n_sims
    frame = pd.DataFrame(
        {
            "team_id": result.teams,
            "group": [result.group_of_team[team] for team in result.teams],
            "p_1st": probs[:, 0],
            "p_2nd": probs[:, 1],
            "p_3rd": probs[:, 2],
            "p_4th": probs[:, 3],
        }
    )
    return frame[_GROUP_POSITION_COLUMNS]


__all__ = ["advancement_table", "group_position_table"]
