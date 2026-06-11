from datetime import date

import pandas as pd
import pytest

from cdd_mundial.data.identities import (
    AmbiguousTeamError,
    TeamResolver,
    UnknownTeamError,
    build_coverage_report,
)


def test_authored_registry_has_48_world_cup_teams() -> None:
    resolver = TeamResolver.from_csv()

    participants = resolver.teams[resolver.teams["is_world_cup_2026"]]
    assert len(participants) == 48
    assert participants["team_id"].is_unique
    assert participants["fifa_code"].notna().all()
    assert participants["fifa_code"].is_unique


def test_all_five_sources_cover_every_participant() -> None:
    resolver = TeamResolver.from_csv()
    team_ids = resolver.teams.loc[resolver.teams["is_world_cup_2026"], "team_id"]

    report = build_coverage_report(
        team_ids,
        ["martj42", "eloratings", "fifa", "fixture", "odds"],
        resolver,
    )

    assert len(report) == 48 * 5
    assert report["resolved"].all()
    assert report["source_name"].notna().all()
    assert report["reason"].eq("reviewed alias").all()


def test_resolution_is_exact_and_source_keyed() -> None:
    resolver = TeamResolver.from_csv()

    assert resolver.resolve("martj42", "South Korea", "2022-12-02") == "south-korea"
    assert resolver.resolve("fifa", "Korea Republic", date(2026, 6, 11)) == "south-korea"
    with pytest.raises(UnknownTeamError):
        resolver.resolve("martj42", "south korea", "2022-12-02")


def test_unknown_alias_fails_loudly() -> None:
    resolver = TeamResolver.from_csv()

    with pytest.raises(UnknownTeamError, match="unknown team alias"):
        resolver.resolve("martj42", "Atlantis", "2026-06-11")


def test_ambiguous_alias_fails_loudly() -> None:
    teams = pd.DataFrame(
        [
            {
                "team_id": "alpha",
                "canonical_name": "Alpha",
                "fifa_code": "ALP",
                "elo_code": "ALP",
                "confederation": "TEST",
                "is_world_cup_2026": False,
                "active_from": "2000-01-01",
                "active_to": None,
            },
            {
                "team_id": "beta",
                "canonical_name": "Beta",
                "fifa_code": "BET",
                "elo_code": "BET",
                "confederation": "TEST",
                "is_world_cup_2026": False,
                "active_from": "2000-01-01",
                "active_to": None,
            },
        ]
    )
    aliases = pd.DataFrame(
        [
            {
                "source": "test",
                "source_name": "Shared",
                "team_id": "alpha",
                "valid_from": "2000-01-01",
                "valid_to": None,
                "mapping_note": None,
            },
            {
                "source": "test",
                "source_name": "Shared",
                "team_id": "beta",
                "valid_from": "2010-01-01",
                "valid_to": None,
                "mapping_note": None,
            },
        ]
    )
    resolver = TeamResolver(teams, aliases)

    with pytest.raises(AmbiguousTeamError, match="matched 2 rows"):
        resolver.resolve("test", "Shared", "2020-01-01")


def test_alias_foreign_keys_are_enforced() -> None:
    resolver = TeamResolver.from_csv()
    aliases = resolver.aliases.copy()
    aliases.loc[0, "team_id"] = "missing-team"

    with pytest.raises(ValueError, match="unknown team IDs"):
        TeamResolver(resolver.teams, aliases)
