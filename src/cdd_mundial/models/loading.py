"""Canonical historical match loader with 90-minute outcome labels."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cdd_mundial.data.contracts import HistoricalMatchesSchema

OUTCOME_LABELS = ("home_win", "draw", "away_win")

_OUTCOME_INDEX = {label: index for index, label in enumerate(OUTCOME_LABELS)}


def load_matches(
    path: Path = Path("data/processed/historical_matches.parquet"),
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return validated history with datetime dates plus outcome_90/outcome_idx labels.

    Scores in the source are full-time-including-extra-time, so any match decided
    after extra time or penalties drew at 90 minutes regardless of the final score.
    """
    raw = frame.copy() if frame is not None else pd.read_parquet(path)
    matches = HistoricalMatchesSchema.validate(raw)

    matches["date"] = pd.to_datetime(matches["date"], errors="raise")

    drew_90 = matches["result_after_extra_time"] | matches["shootout_winner_team_id"].notna()
    outcome_90 = np.select(
        [
            drew_90,
            matches["home_score"] > matches["away_score"],
            matches["home_score"] < matches["away_score"],
        ],
        ["draw", "home_win", "away_win"],
        default="draw",
    )
    matches["outcome_90"] = outcome_90
    matches["outcome_idx"] = matches["outcome_90"].map(_OUTCOME_INDEX).astype(int)

    return matches.sort_values(["date", "match_id"]).reset_index(drop=True)
