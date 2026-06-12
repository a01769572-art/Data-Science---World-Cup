"""Hand-verified tests for the custom World Football Elo recomputation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from cdd_mundial.models.elo import (
    HOME_BONUS,
    INITIAL_RATING,
    elo_update,
    expected_score,
    margin_factor,
    ratings_asof,
    recompute_elo,
    verify_elo_materialization,
)
from cdd_mundial.models.loading import load_matches
from cdd_mundial.models.tournaments import TournamentKTable, UnknownTournamentError


def _mini_matches() -> pd.DataFrame:
    """Four synthetic matches covering neutral, home bonus, shootout, and K variety."""
    rows = [
        ("2020-01-01", "alpha", "beta", 2, 0, "Test Friendly", True, None, False),
        ("2020-02-01", "alpha", "gamma", 1, 1, "Test Friendly", False, None, False),
        ("2020-03-01", "beta", "gamma", 2, 2, "Test Cup", True, "beta", True),
        ("2020-04-01", "gamma", "alpha", 3, 1, "Test Cup", False, None, False),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "date",
            "home_team_id",
            "away_team_id",
            "home_score",
            "away_score",
            "tournament",
            "neutral",
            "shootout_winner_team_id",
            "result_after_extra_time",
        ],
    )
    frame["match_id"] = [
        f"{date}-{home}-{away}"
        for date, home, away in zip(
            frame["date"], frame["home_team_id"], frame["away_team_id"], strict=True
        )
    ]
    frame["home_team_source_name"] = frame["home_team_id"].str.title()
    frame["away_team_source_name"] = frame["away_team_id"].str.title()
    frame["city"] = "Testville"
    frame["country"] = "Testland"
    frame["source"] = "synthetic"
    frame["source_version"] = "test-v1"
    return frame


def _mini_k_table(include_cup: bool = True) -> TournamentKTable:
    rows = [{"tournament": "Test Friendly", "k_category": "friendly", "k_factor": 20}]
    if include_cup:
        rows.append({"tournament": "Test Cup", "k_category": "wc", "k_factor": 60})
    return TournamentKTable(pd.DataFrame(rows))


def test_hand_computed_update_neutral_one_nil() -> None:
    new_a, new_b = elo_update(1500.0, 1500.0, 1, 0, 60.0, 0.0)

    # We=0.5, margin=log(2)*2.2/2.2=log(2), delta=60*log(2)*0.5
    assert new_a == pytest.approx(1520.7944, abs=1e-3)
    assert new_b == pytest.approx(1479.2056, abs=1e-3)


def test_draw_between_unequal_teams_moves_ratings() -> None:
    new_a, new_b = elo_update(1700.0, 1300.0, 1, 1, 40.0, 0.0)

    # We_a = 1/(10**(-400/400)+1) = 0.909090..., margin=1.0, delta=40*(0.5-0.90909...)
    assert new_a == pytest.approx(1683.6364, abs=1e-3)
    assert new_b == pytest.approx(1316.3636, abs=1e-3)
    assert new_a != 1700.0  # pitfall 1: el empate NUNCA debe dejar el rating congelado


def test_shootout_counts_as_draw() -> None:
    drawn_a, drawn_b = elo_update(1600.0, 1400.0, 1, 1, 60.0, 0.0)
    shootout_a, shootout_b = elo_update(1600.0, 1400.0, 3, 3, 60.0, 0.0, drew_after_et=True)

    # shootout o ET => w_a=0.5, margin factor 1.0: mismo delta que un empate
    assert shootout_a == pytest.approx(drawn_a, abs=1e-12)
    assert shootout_b == pytest.approx(drawn_b, abs=1e-12)


def test_home_bonus_raises_expected_score() -> None:
    assert expected_score(1500.0, 1500.0, 0.0) == pytest.approx(0.5)
    assert expected_score(1500.0, 1500.0, HOME_BONUS) > 0.5


def test_recompute_matches_sequential_hand_application() -> None:
    matches = load_matches(frame=_mini_matches())
    history = recompute_elo(matches, _mini_k_table())

    # Long format: 2 filas por partido (home y away)
    assert len(history) == 2 * len(matches)
    assert list(history.columns) == [
        "match_id",
        "date",
        "team_id",
        "opponent_id",
        "rating_pre",
        "rating_post",
        "k_factor",
    ]

    # Aplicacion secuencial independiente con las funciones puras verificadas arriba
    ratings = {"alpha": INITIAL_RATING, "beta": INITIAL_RATING, "gamma": INITIAL_RATING}
    spec = [
        ("alpha", "beta", 2, 0, 20.0, 0.0, False),
        ("alpha", "gamma", 1, 1, 20.0, HOME_BONUS, False),
        ("beta", "gamma", 2, 2, 60.0, 0.0, True),
        ("gamma", "alpha", 3, 1, 60.0, HOME_BONUS, False),
    ]
    for home, away, hs, aws, k, bonus, drew in spec:
        ratings[home], ratings[away] = elo_update(
            ratings[home], ratings[away], hs, aws, k, bonus, drew_after_et=drew
        )

    # Valor a mano del primer partido: delta = 20*log(3)*0.5 = 10.9861
    first_home = history.iloc[0]
    assert first_home["team_id"] == "alpha"
    assert first_home["rating_pre"] == pytest.approx(INITIAL_RATING)
    assert first_home["rating_post"] == pytest.approx(1010.9861, abs=1e-3)

    final = history.groupby("team_id")["rating_post"].last()
    for team, expected in ratings.items():
        assert final[team] == pytest.approx(expected, abs=1e-9)

    # ratings_asof: estrictamente anterior a la fecha pedida; sin historia => 1000
    asof = ratings_asof(history, pd.Timestamp("2020-03-01"))
    assert asof["alpha"] == pytest.approx(1007.8962, abs=1e-3)
    assert asof["unseen-team"] == pytest.approx(INITIAL_RATING)


def test_unknown_tournament_fails_loudly() -> None:
    matches = load_matches(frame=_mini_matches())

    with pytest.raises(UnknownTournamentError, match="Test Cup"):
        recompute_elo(matches, _mini_k_table(include_cup=False))


def test_margin_factor_draw_branch_is_one() -> None:
    assert margin_factor(0, 1800.0, 1200.0) == 1.0
    assert margin_factor(2, 1500.0, 1500.0) == pytest.approx(np.log(3.0), abs=1e-12)


@pytest.mark.data_acceptance
def test_model01_real_elo_materialization() -> None:
    summary = verify_elo_materialization(data_root=Path("data"))

    assert summary["matches"] > 49_000
    assert summary["teams"] > 300
    assert summary["top_rating"] > INITIAL_RATING


@pytest.mark.data_acceptance
def test_model01_spearman_vs_eloratings_snapshot() -> None:
    # Comparar RANGOS, nunca niveles absolutos (pitfall 2/9: cold-start centra ~1000
    # mientras eloratings.net centra ~1500 — solo las diferencias/rangos importan).
    recomputed = pd.read_parquet("data/processed/models/elo_ratings.parquet")
    reference = pd.read_parquet("data/processed/elo_current.parquet")
    teams = pd.read_csv("data/external/teams.csv")
    world_cup_ids = teams.loc[teams["is_world_cup_2026"], "team_id"]

    merged = recomputed[recomputed["team_id"].isin(world_cup_ids)].merge(
        reference, on="team_id", suffixes=("_recomputed", "_reference")
    )

    assert len(merged) == 48
    correlation = spearmanr(
        merged["elo_rating_recomputed"], merged["elo_rating_reference"]
    ).statistic
    assert correlation >= 0.9
