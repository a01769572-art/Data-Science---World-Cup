"""Naive comparator baselines for the D-13 gate: uniform W/D/L and solo-Elo ordered logit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

_PROB_FLOOR = 1e-12


@dataclass(frozen=True)
class OrderedLogit:
    """Ordered logit over the Elo difference dr, ordered [home_win, draw, away_win].

    With dr the Elo difference from team A's perspective (including +100 when A is the
    non-neutral host) and sigma the logistic CDF:

    - P(home_win)         = sigma((dr - c2) / scale)
    - P(home_win or draw) = sigma((dr - c1) / scale)
    - P(draw)             = sigma((dr - c1)/scale) - sigma((dr - c2)/scale)  [>= 0: c1 < c2]
    - P(away_win)         = 1 - sigma((dr - c1) / scale)
    """

    c1: float  # cutpoint inferior (loss|draw)
    c2: float  # cutpoint superior (draw|win); invariante c1 < c2
    scale: float  # > 0

    def __post_init__(self) -> None:
        if not self.c1 < self.c2:
            raise ValueError(f"ordered logit requires c1 < c2, got c1={self.c1!r} c2={self.c2!r}")
        if not self.scale > 0.0:
            raise ValueError(f"ordered logit requires scale > 0, got scale={self.scale!r}")


def uniform_wdl() -> np.ndarray:
    """Return the naive uniform forecast [1/3, 1/3, 1/3]."""
    return np.full(3, 1.0 / 3.0)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def solo_elo_probs(dr: np.ndarray, model: OrderedLogit) -> np.ndarray:
    """Return (n, 3) probabilities [home_win, draw, away_win] for Elo differences dr."""
    dr = np.asarray(dr, dtype=float)
    upper = _sigmoid((dr - model.c2) / model.scale)
    lower = _sigmoid((dr - model.c1) / model.scale)
    probs = np.column_stack([upper, lower - upper, 1.0 - lower])
    probs = np.clip(probs, _PROB_FLOOR, None)  # estabilidad de log-loss
    return probs / probs.sum(axis=1, keepdims=True)


def fit_solo_elo(dr: np.ndarray, outcome_idx: np.ndarray) -> OrderedLogit:
    """MLE of the ordered logit via L-BFGS-B over free params (c1, d, log_s).

    Reparametrization c2 = c1 + exp(d) and scale = exp(log_s) guarantees c1 < c2 and
    scale > 0 without bounds. NLL = -sum(log(prob of the observed class)).
    """
    dr = np.asarray(dr, dtype=float)
    outcome_idx = np.asarray(outcome_idx, dtype=int)
    row_index = np.arange(len(outcome_idx))

    def negative_log_likelihood(params: np.ndarray) -> float:
        c1, d, log_s = params
        model = OrderedLogit(c1=float(c1), c2=float(c1 + np.exp(d)), scale=float(np.exp(log_s)))
        probs = solo_elo_probs(dr, model)
        return float(-np.log(probs[row_index, outcome_idx]).sum())

    initial = np.array([-100.0, np.log(200.0), np.log(200.0)])
    result = minimize(negative_log_likelihood, initial, method="L-BFGS-B")
    if not result.success:
        raise ValueError(f"solo-Elo ordered logit fit failed to converge: {result.message}")
    c1, d, log_s = result.x
    return OrderedLogit(c1=float(c1), c2=float(c1 + np.exp(d)), scale=float(np.exp(log_s)))
