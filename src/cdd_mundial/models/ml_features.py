"""Deterministic point-in-time ML v1 feature builder (Phase 5, ML-01).

This module freezes the *data contract* for the supervised ML upgrade BEFORE any
modeling, calibration, or CLI code exists. It emits exactly one row per match
with:

* join keys (``match_id``, ``date``, ``home_team_id``, ``away_team_id``,
  ``tournament``),
* the canonical 3-way target ``target_outcome_idx`` reused verbatim from
  :func:`cdd_mundial.models.loading.load_matches` (90-minute semantics, D-01),
* explicit coverage metadata (``has_min_history_home``, ``has_min_history_away``,
  ``ml_eligible``) that proves whether a row is usable under D-04 instead of
  silently dropping it (T-05-02), and
* the fixed 12-feature matrix from D-02 in natural units, with no normalization
  (D-05).

Two anti-leakage invariants are load-bearing (T-05-01):

1. Every rolling feature for a match is computed **strictly** from matches with
   ``date < kickoff`` for that match. A match never sees its own result, and
   ties on ``date`` are resolved by ``match_id`` so same-day fixtures do not
   leak across each other.
2. The structural Dixon-Coles features come from an injected ``dc_predict``
   callable (defaulting to the production :func:`predict_lambdas`). Backtests and
   tests supply a cutoff-correct predictor; nothing here peeks past the cutoff.

The builder accepts either the canonical historical parquet (loaded internally)
or a pre-loaded / live-training frame, mirroring the
``load_matches(path=..., frame=...)`` and ``materialize_live_training`` design so
later plans reuse one deterministic feature path for both holdouts and live
publication.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from cdd_mundial.models.dixon_coles import predict_lambdas, wdl_from_lambdas
from cdd_mundial.models.loading import load_matches

# Minimum prior matches per team for a row to be ML-eligible (D-04). Below this,
# the row is retained for auditability but excluded from ML training/inference;
# production falls back to the baseline for such matches.
MIN_PRIOR_MATCHES = 5

# Fixed last-N window for all recent-form rollings (D-03). v1 never mixes
# last_3 and last_5.
ROLLING_WINDOW = 5

# Frozen 12-feature contract (D-02). Order is authoritative and asserted by tests
# so a silent rename/add/drop fails loudly downstream.
ML_FEATURE_COLUMNS: tuple[str, ...] = (
    "elo_diff",
    "is_host_home",
    "days_rest_diff",
    "form_points_diff_last_5",
    "goal_diff_per_match_diff_last_5",
    "goals_for_per_match_diff_last_5",
    "goals_against_per_match_diff_last_5",
    "lambda_home_dc",
    "lambda_away_dc",
    "p_home_win_dc",
    "p_draw_dc",
    "p_away_win_dc",
)

# Predictor signature: (team_a, team_b, ctx) -> (lambda_a, lambda_b).
DCPredict = Callable[[str, str, dict], tuple[float, float]]

# Default Dixon-Coles rho used to turn lambdas into a 3-way WDL vector when the
# injected predictor returns only lambdas. The production path passes a model
# whose own rho is used by later plans; for the canonical builder a small, stable
# value matches the low-score correction magnitude of the fitted models.
_DEFAULT_RHO = 0.0


def _result_points(scored_for: int, scored_against: int) -> int:
    """3/1/0 points for a single team's match (90-minute result, D-06)."""
    if scored_for > scored_against:
        return 3
    if scored_for == scored_against:
        return 1
    return 0


class _TeamState:
    """Rolling, strictly-prior accumulator for one team.

    Holds only information available *before* the current match; the caller
    updates it with each match's result *after* that match's features are read,
    guaranteeing no look-ahead.
    """

    __slots__ = ("count", "last_date", "_points", "_gf", "_ga", "_gd")

    def __init__(self) -> None:
        self.count = 0
        self.last_date: pd.Timestamp | None = None
        self._points: deque[int] = deque(maxlen=ROLLING_WINDOW)
        self._gf: deque[int] = deque(maxlen=ROLLING_WINDOW)
        self._ga: deque[int] = deque(maxlen=ROLLING_WINDOW)
        self._gd: deque[int] = deque(maxlen=ROLLING_WINDOW)

    def form_points_per_match(self) -> float:
        return float(np.mean(self._points)) if self._points else 0.0

    def goals_for_per_match(self) -> float:
        return float(np.mean(self._gf)) if self._gf else 0.0

    def goals_against_per_match(self) -> float:
        return float(np.mean(self._ga)) if self._ga else 0.0

    def goal_diff_per_match(self) -> float:
        return float(np.mean(self._gd)) if self._gd else 0.0

    def update(self, date: pd.Timestamp, gf: int, ga: int) -> None:
        self.count += 1
        self.last_date = date
        self._points.append(_result_points(gf, ga))
        self._gf.append(gf)
        self._ga.append(ga)
        self._gd.append(gf - ga)


def _days_rest(state: _TeamState, kickoff: pd.Timestamp) -> float:
    """Days since the team's previous match; NaN when it has no prior match."""
    if state.last_date is None:
        return float("nan")
    return float((kickoff - state.last_date).days)


def _elo_lookup(elo_history: pd.DataFrame | None) -> dict[tuple[str, str], float]:
    """Map (match_id, team_id) -> pre-match Elo rating, or empty if unavailable."""
    if elo_history is None:
        return {}
    needed = {"match_id", "team_id", "rating_pre"}
    if not needed.issubset(elo_history.columns):
        raise ValueError(
            f"elo_history is missing required columns; need {sorted(needed)}"
        )
    return {
        (str(row.match_id), str(row.team_id)): float(row.rating_pre)
        for row in elo_history.itertuples(index=False)
    }


def build_ml_dataset(
    *,
    path: Path = Path("data/processed/historical_matches.parquet"),
    frame: pd.DataFrame | None = None,
    elo_history: pd.DataFrame | None = None,
    dc_predict: DCPredict | None = None,
    dc_rho: float = _DEFAULT_RHO,
) -> pd.DataFrame:
    """Build the canonical point-in-time ML v1 dataset (one row per match).

    Parameters
    ----------
    path
        Canonical historical parquet; ignored when ``frame`` is provided.
    frame
        Pre-loaded canonical frame (e.g. the ``_frame`` from
        :func:`materialize_live_training`). Lets the live path reuse the exact
        same feature logic as backtests without re-reading disk.
    elo_history
        Optional pre-match Elo table (``match_id``, ``team_id``, ``rating_pre``).
        When absent, ``elo_diff`` is emitted as NaN and rows still build (the
        feature contract is preserved; later plans inject the real ratings).
    dc_predict
        Injected Dixon-Coles predictor ``(team_a, team_b, ctx) -> (lam, mu)``.
        Defaults to the production :func:`predict_lambdas`. Backtests pass a
        cutoff-correct predictor so structural features never peek past kickoff.
    dc_rho
        Rho used to convert lambdas into the 3-way WDL probabilities.

    Returns
    -------
    pandas.DataFrame
        One row per input match: join keys, ``target_outcome_idx``, coverage
        metadata, and the 12 frozen feature columns. Every input row is retained
        (D-04 is encoded as ``ml_eligible``, never as a silent drop).
    """
    matches = load_matches(path=path, frame=frame)
    predictor: DCPredict = dc_predict if dc_predict is not None else predict_lambdas
    elo_by_key = _elo_lookup(elo_history)

    # load_matches already sorts by (date, match_id); keep that stable order so
    # the strictly-prior accumulation is deterministic and ties never leak.
    states: dict[str, _TeamState] = {}
    records: list[dict[str, object]] = []

    for row in matches.itertuples(index=False):
        match_id = str(row.match_id)
        home = str(row.home_team_id)
        away = str(row.away_team_id)
        kickoff: pd.Timestamp = row.date
        neutral = bool(row.neutral)

        home_state = states.setdefault(home, _TeamState())
        away_state = states.setdefault(away, _TeamState())

        # --- coverage metadata (D-04), read BEFORE updating state ---
        has_home = home_state.count >= MIN_PRIOR_MATCHES
        has_away = away_state.count >= MIN_PRIOR_MATCHES
        ml_eligible = bool(has_home and has_away)

        # --- raw point-in-time rollings (strictly prior matches only) ---
        form_diff = (
            home_state.form_points_per_match() - away_state.form_points_per_match()
        )
        gd_diff = home_state.goal_diff_per_match() - away_state.goal_diff_per_match()
        gf_diff = (
            home_state.goals_for_per_match() - away_state.goals_for_per_match()
        )
        ga_diff = (
            home_state.goals_against_per_match() - away_state.goals_against_per_match()
        )
        days_rest_home = _days_rest(home_state, kickoff)
        days_rest_away = _days_rest(away_state, kickoff)
        days_rest_diff = days_rest_home - days_rest_away

        # --- elo_diff with the project +100 home bonus on non-neutral venues ---
        rating_home = elo_by_key.get((match_id, home), float("nan"))
        rating_away = elo_by_key.get((match_id, away), float("nan"))
        home_bonus = 0.0 if neutral else 100.0
        elo_diff = rating_home + home_bonus - rating_away

        # --- is_host_home: the listed home side enjoys real home advantage ---
        is_host_home = 0 if neutral else 1

        # --- structural Dixon-Coles features (injected, cutoff-correct) ---
        lam_home, lam_away = predictor(
            home,
            away,
            {
                "neutral": neutral,
                "date": kickoff,
                "tournament_type": str(row.tournament),
            },
        )
        p_home, p_draw, p_away = wdl_from_lambdas(lam_home, lam_away, dc_rho)

        records.append(
            {
                "match_id": match_id,
                "date": kickoff,
                "home_team_id": home,
                "away_team_id": away,
                "tournament": str(row.tournament),
                "target_outcome_idx": int(row.outcome_idx),
                "has_min_history_home": has_home,
                "has_min_history_away": has_away,
                "n_prior_home": int(home_state.count),
                "n_prior_away": int(away_state.count),
                "ml_eligible": ml_eligible,
                "elo_diff": float(elo_diff),
                "is_host_home": int(is_host_home),
                "days_rest_diff": float(days_rest_diff),
                "form_points_diff_last_5": float(form_diff),
                "goal_diff_per_match_diff_last_5": float(gd_diff),
                "goals_for_per_match_diff_last_5": float(gf_diff),
                "goals_against_per_match_diff_last_5": float(ga_diff),
                "lambda_home_dc": float(lam_home),
                "lambda_away_dc": float(lam_away),
                "p_home_win_dc": float(p_home),
                "p_draw_dc": float(p_draw),
                "p_away_win_dc": float(p_away),
            }
        )

        # --- update state AFTER reading features (guarantees no look-ahead) ---
        home_state.update(kickoff, int(row.home_score), int(row.away_score))
        away_state.update(kickoff, int(row.away_score), int(row.home_score))

    return pd.DataFrame.from_records(records)
