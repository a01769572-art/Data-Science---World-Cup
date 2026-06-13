import json
from pathlib import Path

import pandas as pd

from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.simulation.slots import (
    load_official_third_place_mapping,
    resolve_slot,
    resolve_third_place_assignments,
)


FIXTURE_PATH = Path("data/external/fixture_2026.csv")
MAPPING_PATH = Path("tests/fixtures/tournament/third_place_mapping_official.json")
EXPECTED_COMBINATIONS_PATH = Path(
    "tests/fixtures/tournament/third_place_expected_combinations.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _group_positions() -> dict[str, str]:
    return {
        f"{position}{group}": f"group-{group.lower()}-position-{position}"
        for group in "ABCDEFGHIJKL"
        for position in (1, 2, 3, 4)
    }


def _result_maps() -> tuple[dict[str, str], dict[str, str]]:
    winners = {
        f"WC26-{match_number:03d}": f"winner-{match_number}"
        for match_number in range(73, 105)
    }
    losers = {
        f"WC26-{match_number:03d}": f"loser-{match_number}"
        for match_number in range(73, 105)
    }
    return winners, losers


def test_official_third_place_mapping_cases() -> None:
    payload = _load_json(MAPPING_PATH)

    for index in (0, len(payload["cases"]) // 2, len(payload["cases"]) - 1):
        case = payload["cases"][index]
        resolved = resolve_third_place_assignments(
            case["qualified_groups"],
            mapping_path=MAPPING_PATH,
        )
        assert resolved == case["assignments"]


def test_all_official_combinations_resolve_uniquely() -> None:
    expected_payload = _load_json(EXPECTED_COMBINATIONS_PATH)
    expected_combinations = expected_payload["combinations"]
    mapping = load_official_third_place_mapping(MAPPING_PATH)

    assert len(expected_combinations) == len(set(expected_combinations)) == 495
    assert set(mapping) == set(expected_combinations)
    for qualified_groups in expected_combinations:
        assignment = resolve_third_place_assignments(
            qualified_groups,
            mapping_path=MAPPING_PATH,
        )
        assert assignment == mapping[qualified_groups]
        assert len(assignment) == len(set(assignment.values())) == 8
        assert set(assignment.values()) == set(qualified_groups)


def test_assignment_respects_slot_tokens() -> None:
    payload = _load_json(MAPPING_PATH)
    fixture = load_fixture_2026(FIXTURE_PATH).set_index("match_id")

    for case in payload["cases"]:
        for match_id, group in case["assignments"].items():
            selector = payload["selectors"][fixture.loc[match_id, "home_slot"]]
            assert selector["match_id"] == match_id
            assert selector["side"] == "away"
            assert fixture.loc[match_id, "away_slot"] == selector["slot_token"]
            assert group in selector["slot_token"][1:]


def test_mapping_selectors_match_frozen_fixture_topology() -> None:
    payload = _load_json(MAPPING_PATH)
    fixture = pd.read_csv(FIXTURE_PATH, dtype=str, keep_default_na=True).set_index("match_id")

    for winner_slot, selector in payload["selectors"].items():
        row = fixture.loc[selector["match_id"]]
        assert row["stage"] == "round_of_32"
        assert row["home_slot"] == winner_slot == selector["winner_slot_home"]
        assert row["away_slot"] == selector["slot_token"]
        assert selector["slot_token"].startswith("3")


def test_group_position_slots() -> None:
    positions = _group_positions()
    winners, losers = _result_maps()

    assert (
        resolve_slot(
            "1A",
            match_id="WC26-079",
            group_positions=positions,
            winners=winners,
            losers=losers,
            third_place_assignments={},
        )
        == positions["1A"]
    )
    assert (
        resolve_slot(
            "2L",
            match_id="WC26-083",
            group_positions=positions,
            winners=winners,
            losers=losers,
            third_place_assignments={},
        )
        == positions["2L"]
    )


def test_winner_slots() -> None:
    positions = _group_positions()
    winners, losers = _result_maps()

    assert (
        resolve_slot(
            "W74",
            match_id="WC26-089",
            group_positions=positions,
            winners=winners,
            losers=losers,
            third_place_assignments={},
        )
        == winners["WC26-074"]
    )


def test_loser_slots() -> None:
    positions = _group_positions()
    winners, losers = _result_maps()

    assert (
        resolve_slot(
            "L101",
            match_id="WC26-103",
            group_positions=positions,
            winners=winners,
            losers=losers,
            third_place_assignments={},
        )
        == losers["WC26-101"]
    )


def test_full_bracket_has_no_unresolved_participant_after_prior_rounds() -> None:
    fixture = load_fixture_2026(FIXTURE_PATH)
    knockout = fixture[fixture["stage"] != "group"]
    positions = _group_positions()
    winners, losers = _result_maps()
    qualified_groups = _load_json(MAPPING_PATH)["cases"][0]["qualified_groups"]
    third_place_assignments = resolve_third_place_assignments(
        qualified_groups,
        mapping_path=MAPPING_PATH,
    )

    resolved: dict[str, tuple[str, str]] = {}
    for row in knockout.itertuples(index=False):
        resolved[row.match_id] = (
            resolve_slot(
                row.home_slot,
                match_id=row.match_id,
                group_positions=positions,
                winners=winners,
                losers=losers,
                third_place_assignments=third_place_assignments,
            ),
            resolve_slot(
                row.away_slot,
                match_id=row.match_id,
                group_positions=positions,
                winners=winners,
                losers=losers,
                third_place_assignments=third_place_assignments,
            ),
        )

    assert len(resolved) == 32
    assert all(team_a and team_b for team_a, team_b in resolved.values())
