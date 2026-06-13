"""Compact post-90-minute knockout advancement resolver (SIM-05, D-07, D-08).

A knockout match drawn after 90 minutes must still produce exactly one
advancing team. Phase 3 resolves that draw with a compact approximation built
ONLY from the 90-minute model outputs ``(p_win, p_draw, p_loss)``: the draw
probability mass is split by the non-draw strength ratio

    q = p_win / (p_win + p_loss)            (0.5 when there is no signal)
    q = 0.5 + shrink * (q - 0.5)            (optional shrinkage toward even)

so swapping the two teams swaps ``q`` with ``1 - q`` by construction — there
is no order bias and no separate extra-time lambda model (D-07/D-08).

Engine integration note (for later Phase 3 plans): the ``uniforms`` consumed by
:func:`sample_post_draw_advancers` MUST come from deterministic RNG streams
keyed by stable ``match_id`` plus the simulation/version seed (SeedSequence
spawning), so that fixing earlier matches in a daily state update never
perturbs the draw-resolution stream of still-unplayed matches.
"""

from __future__ import annotations

import math

import numpy as np

_TRIPLE_SUM_TOLERANCE = 1e-6


def _validate_triple(p_win: float, p_draw: float, p_loss: float) -> None:
    """Fail loudly on anything that is not a 90-minute probability triple."""
    for name, value in (("p_win", p_win), ("p_draw", p_draw), ("p_loss", p_loss)):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}")
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must lie in [0, 1], got {value!r}")
    total = p_win + p_draw + p_loss
    if abs(total - 1.0) > _TRIPLE_SUM_TOLERANCE:
        raise ValueError(
            f"p_win + p_draw + p_loss must sum to 1 within {_TRIPLE_SUM_TOLERANCE}, got {total!r}"
        )


def _validate_shrink(shrink: float) -> None:
    if not math.isfinite(shrink) or not 0.0 <= shrink <= 1.0:
        raise ValueError(f"shrink must lie in [0, 1], got {shrink!r}")


def post_draw_advance_probability(
    p_win: float, p_draw: float, p_loss: float, shrink: float = 1.0
) -> float:
    """Return q = P(team_a advances | the match is drawn after 90 minutes).

    The split uses only the 90-minute non-draw strengths; identical-strength
    teams (``p_win == p_loss``) receive exactly 0.5, and ``shrink=0.0``
    collapses every split to an even coin.
    """
    _validate_triple(p_win, p_draw, p_loss)
    _validate_shrink(shrink)
    denominator = p_win + p_loss
    q = 0.5 if denominator == 0.0 else p_win / denominator
    return float(0.5 + shrink * (q - 0.5))


def advance_probability(
    p_win: float, p_draw: float, p_loss: float, shrink: float = 1.0
) -> float:
    """Return the total probability that team_a advances from a knockout match.

    ``p_win + p_draw * q`` with ``q`` from
    :func:`post_draw_advance_probability`; swapping the teams complements the
    result exactly because ``q`` swaps with ``1 - q``.
    """
    q = post_draw_advance_probability(p_win, p_draw, p_loss, shrink=shrink)
    return float(p_win + p_draw * q)


def sample_post_draw_advancers(q_a: np.ndarray, uniforms: np.ndarray) -> np.ndarray:
    """Resolve drawn knockout matches: True where team_a advances.

    ``team_b`` advances exactly where team_a does not, so every drawn match
    produces exactly one advancing team by construction. ``uniforms`` must be
    deterministic draws in ``[0, 1)`` from streams keyed by ``match_id`` plus
    the simulation/version seed (see module docstring).
    """
    q_array = np.asarray(q_a, dtype=float)
    u_array = np.asarray(uniforms, dtype=float)
    if q_array.shape != u_array.shape:
        raise ValueError(
            f"q_a and uniforms must share the same shape, got {q_array.shape} and {u_array.shape}"
        )
    if not np.all(np.isfinite(q_array)) or np.any((q_array < 0.0) | (q_array > 1.0)):
        raise ValueError("q_a values must be finite probabilities in [0, 1]")
    if not np.all(np.isfinite(u_array)) or np.any((u_array < 0.0) | (u_array >= 1.0)):
        raise ValueError("uniforms must be finite draws in [0, 1)")
    return u_array < q_array
