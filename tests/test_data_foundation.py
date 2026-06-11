from pathlib import Path

import pandas as pd
import pandera.errors
import pytest

from cdd_mundial.data.contracts import HistoricalMatchesSchema
from cdd_mundial.data.identities import (
    AmbiguousTeamError,
    TeamResolver,
    UnknownTeamError,
    build_coverage_report,
)
from cdd_mundial.data.ingest_martj42 import build_historical_matches
from cdd_mundial.data.provenance import file_sha256


FIXTURE_ROOT = Path("tests/fixtures/martj42")
SOURCES = ["martj42", "eloratings", "fifa", "fixture", "odds"]


def test_authored_identity_registry_is_complete_and_consistent() -> None:
    resolver = TeamResolver.from_csv()
    participants = resolver.teams.loc[
        resolver.teams["is_world_cup_2026"],
        "team_id",
    ]

    assert len(participants) == 48
    assert participants.is_unique
    assert set(resolver.aliases["team_id"]) <= set(resolver.teams["team_id"])
    assert not resolver.aliases.duplicated(["source", "source_name", "valid_from"]).any()

    report = build_coverage_report(participants, SOURCES, resolver)
    assert len(report) == 48 * len(SOURCES)
    assert report["resolved"].notna().all()
    assert report["reason"].notna().all()
    assert report.loc[report["source"] == "martj42", "resolved"].all()


def test_registry_rejects_orphans_duplicates_unknowns_and_ambiguity() -> None:
    resolver = TeamResolver.from_csv()

    orphaned = resolver.aliases.copy()
    orphaned.loc[0, "team_id"] = "missing-team"
    with pytest.raises(ValueError, match="unknown team IDs"):
        TeamResolver(resolver.teams, orphaned)

    duplicated = pd.concat([resolver.aliases, resolver.aliases.iloc[[0]]], ignore_index=True)
    with pytest.raises(pandera.errors.SchemaError):
        TeamResolver(resolver.teams, duplicated)

    with pytest.raises(UnknownTeamError):
        resolver.resolve("martj42", "Atlantis", "2022-12-18")

    ambiguous = pd.concat(
        [
            resolver.aliases,
            pd.DataFrame(
                [
                    {
                        "source": "martj42",
                        "source_name": "Argentina",
                        "team_id": "brazil",
                        "valid_from": "2000-01-01",
                        "valid_to": None,
                        "mapping_note": "Deliberately ambiguous integration fixture",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    ambiguous_resolver = TeamResolver(resolver.teams, ambiguous)
    with pytest.raises(AmbiguousTeamError):
        ambiguous_resolver.resolve("martj42", "Argentina", "2022-12-18")


def test_martj42_fixture_round_trip_preserves_raw_files(test_workspace: Path) -> None:
    fixture_paths = [
        FIXTURE_ROOT / "results.csv",
        FIXTURE_ROOT / "shootouts.csv",
    ]
    checksums_before = {path: file_sha256(path) for path in fixture_paths}
    output_path = test_workspace / "data" / "processed" / "historical_matches.parquet"

    build_historical_matches(
        fixture_paths[0],
        fixture_paths[1],
        output_path=output_path,
        source_version="fixture-v1",
    )
    reloaded = HistoricalMatchesSchema.validate(pd.read_parquet(output_path))

    assert reloaded["home_team_id"].notna().all()
    assert reloaded["away_team_id"].notna().all()
    assert (reloaded["home_team_id"] != reloaded["away_team_id"]).all()
    assert reloaded["home_score"].ge(0).all()
    assert reloaded["away_score"].ge(0).all()
    assert {path: file_sha256(path) for path in fixture_paths} == checksums_before
