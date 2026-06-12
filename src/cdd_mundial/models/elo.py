"""Custom World Football Elo recomputed sequentially over the full match history."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from cdd_mundial.models.tournaments import TournamentKTable

INITIAL_RATING = 1000.0
HOME_BONUS = 100.0

_HISTORY_COLUMNS = [
    "match_id",
    "date",
    "team_id",
    "opponent_id",
    "rating_pre",
    "rating_post",
    "k_factor",
]


def expected_score(elo_a: float, elo_b: float, home_bonus_a: float) -> float:
    """Return We for team A under the WFE logistic curve, with A's home bonus inside dr."""
    dr = (elo_a + home_bonus_a) - elo_b
    return 1.0 / (10 ** (-dr / 400.0) + 1.0)


def margin_factor(goal_diff: int, elo_winner: float, elo_loser: float) -> float:
    """Margin-of-victory multiplier: FiveThirtyEight NFL Elo variant, adapted with a draw branch.

    Attribution: ``log(|gd|+1) * 2.2 / ((elo_winner - elo_loser) * 0.001 + 2.2)`` is the
    FiveThirtyEight MOV multiplier (NOT the eloratings.net discrete G table). Draws return
    1.0 explicitly: the raw formula would give log(1)=0 and freeze ratings on ~23% of
    historical matches (pitfall 1).
    """
    if goal_diff == 0:  # empate: factor 1.0 — la formula 538 daria 0 y congelaria 23% de partidos
        return 1.0
    autocorr = 2.2 / ((elo_winner - elo_loser) * 0.001 + 2.2)
    return np.log(abs(goal_diff) + 1.0) * autocorr


def elo_update(
    elo_a: float,
    elo_b: float,
    score_a: int,
    score_b: int,
    k: float,
    home_bonus_a: float,
    drew_after_et: bool = False,
) -> tuple[float, float]:
    """Return post-match ratings for (A, B); shootout/extra-time decisions count as draws.

    ``drew_after_et=True`` (shootout or extra time, D-05 + WFE) forces ``w_a=0.5`` with
    goal difference 0 and margin factor 1.0, regardless of the recorded FT+ET score.
    """
    if drew_after_et:
        w_a, gd = 0.5, 0
    else:
        w_a = 1.0 if score_a > score_b else (0.5 if score_a == score_b else 0.0)
        gd = abs(score_a - score_b)
    we_a = expected_score(elo_a, elo_b, home_bonus_a)
    if gd == 0:
        g = 1.0
    elif w_a == 1.0:
        g = margin_factor(gd, elo_a, elo_b)
    else:
        g = margin_factor(gd, elo_b, elo_a)
    delta = k * g * (w_a - we_a)
    return elo_a + delta, elo_b - delta


def recompute_elo(matches: pd.DataFrame, k_table: TournamentKTable) -> pd.DataFrame:
    """Sequentially recompute Elo from INITIAL_RATING over ``load_matches`` output.

    The +100 home bonus applies to ``home_team_id`` whenever ``neutral`` is False across
    the WHOLE history (Director decision on OQ1, WFE reconciliation); the MEX/USA/CAN
    restriction from D-02 applies only to 2026 prediction, not to this recomputation.
    Returns a long-format frame with two rows per match (home and away perspectives).
    """
    ratings: dict[str, float] = {}
    rows: list[tuple[str, str, str, str, float, float, int]] = []
    for row in matches.itertuples(index=False):
        home = str(row.home_team_id)
        away = str(row.away_team_id)
        elo_home = ratings.get(home, INITIAL_RATING)
        elo_away = ratings.get(away, INITIAL_RATING)
        home_bonus_a = HOME_BONUS if not row.neutral else 0.0
        drew_after_et = bool(row.result_after_extra_time) or pd.notna(
            row.shootout_winner_team_id
        )
        k = k_table.k_factor(str(row.tournament))
        new_home, new_away = elo_update(
            elo_home,
            elo_away,
            int(row.home_score),
            int(row.away_score),
            float(k),
            home_bonus_a,
            drew_after_et=drew_after_et,
        )
        date_str = row.date.strftime("%Y-%m-%d")
        rows.append((str(row.match_id), date_str, home, away, elo_home, new_home, k))
        rows.append((str(row.match_id), date_str, away, home, elo_away, new_away, k))
        ratings[home] = new_home
        ratings[away] = new_away
    return pd.DataFrame(rows, columns=_HISTORY_COLUMNS)


def ratings_asof(history: pd.DataFrame, date: pd.Timestamp) -> dict[str, float]:
    """Return the latest rating_post strictly BEFORE ``date`` per team; default 1000.0."""
    match_dates = pd.to_datetime(history["date"], errors="raise")
    prior = history.loc[match_dates < date]
    latest = prior.sort_values("date", kind="stable").groupby("team_id")["rating_post"].last()
    return defaultdict(lambda: INITIAL_RATING, latest.to_dict())
