import pandas as pd

from cdd_mundial.models.loading import OUTCOME_LABELS, load_matches


def _match_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "match_id": "2022-12-18-argentina-france",
        "date": "2022-12-18",
        "home_team_id": "argentina",
        "away_team_id": "france",
        "home_team_source_name": "Argentina",
        "away_team_source_name": "France",
        "home_score": 2,
        "away_score": 1,
        "tournament": "FIFA World Cup",
        "city": "Lusail",
        "country": "Qatar",
        "neutral": True,
        "shootout_winner_team_id": None,
        "result_after_extra_time": False,
        "source": "martj42",
        "source_version": "fixture-v1",
    }
    row.update(overrides)
    return row


def test_regulation_home_win_is_labelled_home_win() -> None:
    frame = pd.DataFrame([_match_row(home_score=2, away_score=1)])

    loaded = load_matches(frame=frame)

    assert loaded.loc[0, "outcome_90"] == "home_win"
    assert loaded.loc[0, "outcome_idx"] == 0
    assert OUTCOME_LABELS[loaded.loc[0, "outcome_idx"]] == "home_win"


def test_shootout_match_is_labelled_draw() -> None:
    frame = pd.DataFrame(
        [
            _match_row(
                home_score=3,
                away_score=3,
                shootout_winner_team_id="argentina",
                result_after_extra_time=True,
            )
        ]
    )

    loaded = load_matches(frame=frame)

    assert loaded.loc[0, "outcome_90"] == "draw"
    assert loaded.loc[0, "outcome_idx"] == 1


def test_extra_time_result_is_labelled_draw_despite_final_score() -> None:
    frame = pd.DataFrame(
        [_match_row(home_score=2, away_score=1, result_after_extra_time=True)]
    )

    loaded = load_matches(frame=frame)

    assert loaded.loc[0, "outcome_90"] == "draw"
    assert loaded.loc[0, "outcome_idx"] == 1


def test_date_column_is_datetime_after_loading() -> None:
    frame = pd.DataFrame([_match_row()])

    loaded = load_matches(frame=frame)

    assert pd.api.types.is_datetime64_any_dtype(loaded["date"])
