"""Strict dataframe contracts for canonical Phase 1 data products."""

import pandas as pd
import pandera.pandas as pa
from pandera.typing.pandas import Series


class CanonicalSchema(pa.DataFrameModel):
    """Base configuration shared by canonical, post-resolution outputs."""

    class Config:
        strict = True
        coerce = True


class TeamsSchema(CanonicalSchema):
    team_id: Series[str] = pa.Field(unique=True, str_matches=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    canonical_name: Series[str]
    fifa_code: Series[str] = pa.Field(nullable=True, unique=True)
    elo_code: Series[str] = pa.Field(nullable=True, unique=True)
    confederation: Series[str]
    is_world_cup_2026: Series[bool]
    active_from: Series[str]
    active_to: Series[str] = pa.Field(nullable=True)


class TeamAliasesSchema(CanonicalSchema):
    source: Series[str]
    source_name: Series[str]
    team_id: Series[str]
    valid_from: Series[str]
    valid_to: Series[str] = pa.Field(nullable=True)
    mapping_note: Series[str] = pa.Field(nullable=True)

    @pa.dataframe_check
    def aliases_are_unique(cls, frame: pd.DataFrame) -> Series[bool]:
        return ~frame.duplicated(subset=["source", "source_name", "valid_from"])


class HistoricalMatchesSchema(CanonicalSchema):
    match_id: Series[str] = pa.Field(unique=True)
    date: Series[str]
    home_team_id: Series[str]
    away_team_id: Series[str]
    home_team_source_name: Series[str]
    away_team_source_name: Series[str]
    home_score: Series[int] = pa.Field(ge=0)
    away_score: Series[int] = pa.Field(ge=0)
    tournament: Series[str]
    city: Series[str]
    country: Series[str]
    neutral: Series[bool]
    shootout_winner_team_id: Series[str] = pa.Field(nullable=True)
    result_after_extra_time: Series[bool]
    source: Series[str]
    source_version: Series[str]

    @pa.dataframe_check
    def teams_are_distinct(cls, frame: pd.DataFrame) -> Series[bool]:
        return frame["home_team_id"] != frame["away_team_id"]


class EloRatingsSchema(CanonicalSchema):
    team_id: Series[str] = pa.Field(unique=True)
    elo_rating: Series[float] = pa.Field(gt=0)
    rank: Series[int] = pa.Field(ge=1)
    rating_date_utc: Series[str] = pa.Field(str_matches=r".*Z$")
    source: Series[str]
    source_version: Series[str]


class FixtureSchema(CanonicalSchema):
    match_id: Series[str] = pa.Field(unique=True)
    stage: Series[str]
    group: Series[str] = pa.Field(nullable=True, isin=list("ABCDEFGHIJKL"))
    home_slot: Series[str]
    away_slot: Series[str]
    home_team_id: Series[str] = pa.Field(nullable=True)
    away_team_id: Series[str] = pa.Field(nullable=True)
    kickoff_utc: Series[str] = pa.Field(str_matches=r".*Z$")
    venue: Series[str]
    host_city: Series[str]
    host_country: Series[str]
    status: Series[str]
    source_url: Series[str]
    verified_at_utc: Series[str] = pa.Field(str_matches=r".*Z$")

    @pa.dataframe_check
    def assigned_teams_are_distinct(cls, frame: pd.DataFrame) -> Series[bool]:
        unresolved = frame["home_team_id"].isna() | frame["away_team_id"].isna()
        return unresolved | (frame["home_team_id"] != frame["away_team_id"])


class OddsSchema(CanonicalSchema):
    provider: Series[str]
    bookmaker: Series[str]
    event_id: Series[str]
    match_id: Series[str]
    captured_at_utc: Series[str] = pa.Field(str_matches=r".*Z$")
    commence_time_utc: Series[str] = pa.Field(str_matches=r".*Z$")
    home_team_id: Series[str]
    away_team_id: Series[str]
    market: Series[str] = pa.Field(isin=["h2h"])
    price_home: Series[float] = pa.Field(gt=0)
    price_draw: Series[float] = pa.Field(gt=0)
    price_away: Series[float] = pa.Field(gt=0)
    prob_home_raw: Series[float] = pa.Field(ge=0)
    prob_draw_raw: Series[float] = pa.Field(ge=0)
    prob_away_raw: Series[float] = pa.Field(ge=0)
    overround: Series[float] = pa.Field(ge=0)
    prob_home: Series[float] = pa.Field(ge=0, le=1)
    prob_draw: Series[float] = pa.Field(ge=0, le=1)
    prob_away: Series[float] = pa.Field(ge=0, le=1)

    @pa.dataframe_check
    def teams_are_distinct(cls, frame: pd.DataFrame) -> Series[bool]:
        return frame["home_team_id"] != frame["away_team_id"]

    @pa.dataframe_check
    def probabilities_are_normalized(cls, frame: pd.DataFrame) -> Series[bool]:
        probability_sum = frame["prob_home"] + frame["prob_draw"] + frame["prob_away"]
        return (probability_sum - 1.0).abs() <= 1e-9

