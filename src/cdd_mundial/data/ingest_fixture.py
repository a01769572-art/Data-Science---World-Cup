"""Load and structurally validate the frozen FIFA World Cup 2026 fixture."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cdd_mundial.data.contracts import FixtureSchema
from cdd_mundial.data.identities import TeamResolver


ALLOWED_STAGES = {
    "group",
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "third_place",
    "final",
}
HOST_COUNTRIES = {"CAN", "MEX", "USA"}
FIXTURE_COLUMNS = [
    "match_id",
    "stage",
    "group",
    "home_slot",
    "away_slot",
    "home_team_id",
    "away_team_id",
    "kickoff_utc",
    "venue",
    "host_city",
    "host_country",
    "status",
    "source_url",
    "verified_at_utc",
]


def validate_fixture_structure(
    fixture: pd.DataFrame,
    *,
    resolver: TeamResolver | None = None,
) -> pd.DataFrame:
    """Validate schema, canonical identities, tournament counts, and slot integrity."""
    validated = FixtureSchema.validate(fixture[FIXTURE_COLUMNS].copy())
    active_resolver = resolver or TeamResolver.from_csv()

    if len(validated) != 104:
        raise ValueError(f"fixture must contain exactly 104 matches, found {len(validated)}")
    if not validated["match_id"].is_unique:
        raise ValueError("fixture match IDs must be unique")

    unknown_stages = sorted(set(validated["stage"]) - ALLOWED_STAGES)
    if unknown_stages:
        raise ValueError(f"fixture contains unsupported stages: {unknown_stages}")
    unknown_countries = sorted(set(validated["host_country"]) - HOST_COUNTRIES)
    if unknown_countries:
        raise ValueError(f"fixture contains unsupported host countries: {unknown_countries}")
    if not validated["kickoff_utc"].str.endswith("Z").all():
        raise ValueError("all fixture kickoff timestamps must be UTC values ending in Z")

    pairings = validated[["home_slot", "away_slot"]].apply(
        lambda row: "::".join(sorted((str(row.iloc[0]), str(row.iloc[1])))),
        axis=1,
    )
    if pairings.duplicated().any():
        duplicates = sorted(pairings[pairings.duplicated(keep=False)].unique())
        raise ValueError(f"fixture contains duplicate scheduled slot pairings: {duplicates}")

    group_matches = validated[validated["stage"] == "group"]
    if len(group_matches) != 72:
        raise ValueError(f"fixture must contain exactly 72 group matches, found {len(group_matches)}")
    group_counts = group_matches.groupby("group", observed=True).size().to_dict()
    expected_counts = {group: 6 for group in "ABCDEFGHIJKL"}
    if group_counts != expected_counts:
        raise ValueError(f"each group A-L must contain six matches, found {group_counts}")
    if group_matches[["home_team_id", "away_team_id"]].isna().any().any():
        raise ValueError("all group-stage participants must have canonical team IDs")

    known_team_ids = set(active_resolver.teams["team_id"])
    assigned_ids = set(
        pd.concat(
            [validated["home_team_id"], validated["away_team_id"]],
            ignore_index=True,
        ).dropna()
    )
    unknown_team_ids = sorted(assigned_ids - known_team_ids)
    if unknown_team_ids:
        raise ValueError(f"fixture references unknown canonical team IDs: {unknown_team_ids}")

    participant_ids = set(
        active_resolver.teams.loc[
            active_resolver.teams["is_world_cup_2026"], "team_id"
        ]
    )
    group_ids = set(
        pd.concat(
            [group_matches["home_team_id"], group_matches["away_team_id"]],
            ignore_index=True,
        )
    )
    if group_ids != participant_ids:
        missing = sorted(participant_ids - group_ids)
        extra = sorted(group_ids - participant_ids)
        raise ValueError(f"group-stage participant mismatch; missing={missing}, extra={extra}")

    appearances = pd.concat(
        [group_matches["home_team_id"], group_matches["away_team_id"]],
        ignore_index=True,
    ).value_counts()
    if not appearances.eq(3).all():
        invalid = appearances[~appearances.eq(3)].to_dict()
        raise ValueError(f"every group-stage team must appear three times: {invalid}")

    knockout = validated[validated["stage"] != "group"]
    if knockout[["home_slot", "away_slot"]].isna().any().any():
        raise ValueError("knockout matches must retain both participant slot references")
    return validated


def load_fixture_2026(
    path: Path = Path("data/external/fixture_2026.csv"),
    *,
    resolver: TeamResolver | None = None,
) -> pd.DataFrame:
    """Load the reviewed fixture CSV and enforce the complete tournament contract."""
    fixture = pd.read_csv(path, dtype=str, keep_default_na=True)
    missing_columns = set(FIXTURE_COLUMNS) - set(fixture.columns)
    if missing_columns:
        raise ValueError(f"fixture is missing columns: {sorted(missing_columns)}")
    return validate_fixture_structure(fixture, resolver=resolver)
