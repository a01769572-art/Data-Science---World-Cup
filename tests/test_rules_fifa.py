import json
from pathlib import Path

import pandas as pd
import pytest

from cdd_mundial.simulation.rules_fifa import (
    calculate_group_table,
    rank_best_thirds,
    rank_group,
)


FIXTURE_DIR = Path("tests/fixtures/tournament")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _rank_group_fixture(name: str) -> tuple[list[str], dict]:
    payload = _load_fixture(name)
    order = rank_group(
        pd.DataFrame(payload["matches"]),
        conduct_scores=payload["conduct_scores"],
        fifa_ranking_editions=payload["fifa_ranking_editions"],
    )
    return order, payload


def test_points_gd_gf_order() -> None:
    payload = _load_fixture("wc2018_group_h.json")
    table = calculate_group_table(pd.DataFrame(payload["matches"])).set_index("team_id")

    for team_id, expected in payload["expected_stats"].items():
        assert table.loc[team_id, list(expected)].to_dict() == expected

    order, payload = _rank_group_fixture("wc2018_group_h.json")
    assert order == payload["expected_order"]


def test_head_to_head_is_applied_first() -> None:
    order, payload = _rank_group_fixture("two_way_head_to_head.json")
    assert order == payload["expected_order"]
    assert order.index("alpha") < order.index("beta")


def test_head_to_head_subtable() -> None:
    payload = _load_fixture("two_way_head_to_head.json")
    table = calculate_group_table(pd.DataFrame(payload["matches"])).set_index("team_id")

    assert table.loc["alpha", ["points", "goal_difference", "goals_for"]].tolist() == [
        6,
        1,
        2,
    ]
    assert table.loc["beta", ["points", "goal_difference", "goals_for"]].tolist() == [
        6,
        1,
        2,
    ]
    order, _ = _rank_group_fixture("two_way_head_to_head.json")
    assert order[:2] == ["alpha", "beta"]


def test_residual_tie_reapplies_head_to_head() -> None:
    order, payload = _rank_group_fixture("three_way_tie.json")
    assert order == payload["expected_order"]
    assert order[:3] == ["alpha", "beta", "gamma"]


@pytest.mark.parametrize(
    "fixture_name",
    ["three_way_tie.json", "four_way_tie.json"],
)
def test_multi_team_ties_return_each_team_once(fixture_name: str) -> None:
    order, payload = _rank_group_fixture(fixture_name)
    assert order == payload["expected_order"]
    assert len(order) == len(set(order)) == 4


def test_conduct_score_breaks_residual_tie() -> None:
    order, payload = _rank_group_fixture("fair_play_tie.json")
    assert order == payload["expected_order"]
    assert payload["conduct_scores"]["alpha"] > payload["conduct_scores"]["beta"]
    assert order.index("alpha") < order.index("beta")


def test_fifa_ranking_editions_break_final_tie() -> None:
    order, payload = _rank_group_fixture("fifa_ranking_tie.json")
    current, previous = payload["fifa_ranking_editions"]

    assert current["alpha"] == current["beta"]
    assert previous["alpha"] < previous["beta"]
    assert order == payload["expected_order"]
    assert "drawing" not in payload["criterion_note"].lower().replace("no drawing", "")


def test_best_thirds_order() -> None:
    payload = _load_fixture("best_thirds.json")
    order = rank_best_thirds(
        pd.DataFrame(payload["records"]),
        fifa_ranking_editions=payload["fifa_ranking_editions"],
    )

    assert order == payload["expected_order"]
    assert order[:8] == payload["expected_qualifiers"]
    assert len(order[:8]) == len(set(order[:8])) == 8


def test_best_thirds_conduct_score() -> None:
    payload = _load_fixture("best_thirds.json")
    order = rank_best_thirds(
        pd.DataFrame(payload["records"]),
        fifa_ranking_editions=payload["fifa_ranking_editions"],
    )

    assert order.index("third-g") < order.index("third-h")


def test_best_thirds_fifa_ranking_fallback() -> None:
    payload = _load_fixture("best_thirds.json")
    order = rank_best_thirds(
        pd.DataFrame(payload["records"]),
        fifa_ranking_editions=payload["fifa_ranking_editions"],
    )
    current, previous = payload["fifa_ranking_editions"]

    assert current["third-h"] == current["third-i"]
    assert previous["third-h"] < previous["third-i"]
    assert order.index("third-h") < order.index("third-i")


def test_best_thirds_never_uses_cross_group_head_to_head() -> None:
    payload = _load_fixture("best_thirds.json")
    records = pd.DataFrame(payload["records"])
    reversed_noise = records.assign(
        cross_group_head_to_head_points=3 - records["cross_group_head_to_head_points"]
    )

    original = rank_best_thirds(
        records,
        fifa_ranking_editions=payload["fifa_ranking_editions"],
    )
    changed = rank_best_thirds(
        reversed_noise,
        fifa_ranking_editions=payload["fifa_ranking_editions"],
    )
    assert original == changed == payload["expected_order"]
