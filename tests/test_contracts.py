from collections.abc import Callable

import pandas as pd
import pandera.pandas as pa
import pytest

from cdd_mundial.data.contracts import (
    EloRatingsSchema,
    FixtureSchema,
    HistoricalMatchesSchema,
    OddsSchema,
    TeamAliasesSchema,
    TeamsSchema,
)

PANDERA_ERRORS = (pa.errors.SchemaError, pa.errors.SchemaErrors)


def teams_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "team_id": "mexico",
                "canonical_name": "Mexico",
                "fifa_code": "MEX",
                "elo_code": "MEX",
                "confederation": "CONCACAF",
                "is_world_cup_2026": True,
                "active_from": "1923-01-01",
                "active_to": None,
            }
        ]
    )


def aliases_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source": "martj42",
                "source_name": "Mexico",
                "team_id": "mexico",
                "valid_from": "1923-01-01",
                "valid_to": None,
                "mapping_note": None,
            }
        ]
    )


def historical_matches_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": "martj42-2022-001",
                "date": "2022-11-22",
                "home_team_id": "mexico",
                "away_team_id": "poland",
                "home_team_source_name": "Mexico",
                "away_team_source_name": "Poland",
                "home_score": 0,
                "away_score": 0,
                "tournament": "FIFA World Cup",
                "city": "Doha",
                "country": "Qatar",
                "neutral": True,
                "shootout_winner_team_id": None,
                "result_after_extra_time": False,
                "source": "martj42",
                "source_version": "2026-06-11",
            }
        ]
    )


def elo_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "team_id": "mexico",
                "elo_rating": 1810.5,
                "rank": 20,
                "rating_date_utc": "2026-06-11T00:00:00Z",
                "source": "eloratings.net",
                "source_version": "2026-06-11",
            }
        ]
    )


def fixture_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": "WC26-001",
                "stage": "group",
                "group": "A",
                "home_slot": "A1",
                "away_slot": "A2",
                "home_team_id": "mexico",
                "away_team_id": "south-africa",
                "kickoff_utc": "2026-06-11T19:00:00Z",
                "venue": "Estadio Azteca",
                "host_city": "Mexico City",
                "host_country": "Mexico",
                "status": "scheduled",
                "source_url": "https://www.fifa.com/",
                "verified_at_utc": "2026-06-11T12:00:00Z",
            }
        ]
    )


def odds_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "provider": "example",
                "bookmaker": "example-book",
                "event_id": "event-001",
                "match_id": "WC26-001",
                "captured_at_utc": "2026-06-11T12:00:00Z",
                "commence_time_utc": "2026-06-11T19:00:00Z",
                "home_team_id": "mexico",
                "away_team_id": "south-africa",
                "market": "h2h",
                "price_home": 1.8,
                "price_draw": 3.5,
                "price_away": 4.5,
                "prob_home_raw": 1 / 1.8,
                "prob_draw_raw": 1 / 3.5,
                "prob_away_raw": 1 / 4.5,
                "overround": (1 / 1.8) + (1 / 3.5) + (1 / 4.5) - 1,
                "prob_home": 0.522875816993464,
                "prob_draw": 0.26890756302521,
                "prob_away": 0.208216619981326,
            }
        ]
    )


@pytest.mark.parametrize(
    ("schema", "frame_factory"),
    [
        (TeamsSchema, teams_frame),
        (TeamAliasesSchema, aliases_frame),
        (HistoricalMatchesSchema, historical_matches_frame),
        (EloRatingsSchema, elo_frame),
        (FixtureSchema, fixture_frame),
        (OddsSchema, odds_frame),
    ],
)
def test_valid_minimal_canonical_frames_pass(
    schema: type[pa.DataFrameModel],
    frame_factory: Callable[[], pd.DataFrame],
) -> None:
    validated = schema.validate(frame_factory())
    assert len(validated) == 1


def test_unexpected_columns_fail() -> None:
    frame = teams_frame().assign(raw_provider_column="not canonical")
    with pytest.raises(PANDERA_ERRORS):
        TeamsSchema.validate(frame)


def test_negative_scores_fail() -> None:
    frame = historical_matches_frame()
    frame.loc[0, "home_score"] = -1
    with pytest.raises(pa.errors.SchemaError):
        HistoricalMatchesSchema.validate(frame)


@pytest.mark.parametrize("schema,frame_factory", [(HistoricalMatchesSchema, historical_matches_frame), (FixtureSchema, fixture_frame), (OddsSchema, odds_frame)])
def test_self_matches_fail(
    schema: type[pa.DataFrameModel],
    frame_factory: Callable[[], pd.DataFrame],
) -> None:
    frame = frame_factory()
    frame.loc[0, "away_team_id"] = frame.loc[0, "home_team_id"]
    with pytest.raises(pa.errors.SchemaError):
        schema.validate(frame)


def test_invalid_fixture_group_fails() -> None:
    frame = fixture_frame()
    frame.loc[0, "group"] = "M"
    with pytest.raises(pa.errors.SchemaError):
        FixtureSchema.validate(frame)


@pytest.mark.parametrize("column", ["kickoff_utc", "verified_at_utc"])
def test_non_utc_fixture_timestamps_fail(column: str) -> None:
    frame = fixture_frame()
    frame.loc[0, column] = "2026-06-11T14:00:00-05:00"
    with pytest.raises(pa.errors.SchemaError):
        FixtureSchema.validate(frame)


@pytest.mark.parametrize("column", ["price_home", "price_draw", "price_away"])
def test_nonpositive_decimal_prices_fail(column: str) -> None:
    frame = odds_frame()
    frame.loc[0, column] = 0
    with pytest.raises(pa.errors.SchemaError):
        OddsSchema.validate(frame)


def test_negative_overround_fails() -> None:
    frame = odds_frame()
    frame.loc[0, "overround"] = -0.01
    with pytest.raises(pa.errors.SchemaError):
        OddsSchema.validate(frame)


def test_non_normalized_probabilities_fail() -> None:
    frame = odds_frame()
    frame.loc[0, "prob_home"] += 1e-6
    with pytest.raises(pa.errors.SchemaError):
        OddsSchema.validate(frame)
