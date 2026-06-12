"""Custom ranked probability score and multiclass Brier score for 1X2 forecasts."""

from __future__ import annotations

import numpy as np


def rps(probs: np.ndarray, outcome_idx: np.ndarray) -> float:
    """probs: (n, 3) en orden [home_win, draw, away_win]; outcome_idx: (n,) en {0,1,2}."""
    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(np.eye(3)[outcome_idx], axis=1)
    return float(((cum_p - cum_o) ** 2).sum(axis=1).mean() / 2)


def brier_multiclass(probs: np.ndarray, outcome_idx: np.ndarray) -> float:
    return float(((probs - np.eye(3)[outcome_idx]) ** 2).sum(axis=1).mean())
