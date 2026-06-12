"""Tests for the naive comparator baselines: uniform W/D/L and solo-Elo ordered logit."""

from __future__ import annotations

import numpy as np

from cdd_mundial.models.baselines import OrderedLogit, fit_solo_elo, solo_elo_probs, uniform_wdl


def test_uniform_wdl_is_one_third_each() -> None:
    probs = uniform_wdl()

    assert probs.shape == (3,)
    np.testing.assert_allclose(probs, np.full(3, 1.0 / 3.0))
    assert probs.sum() == 1.0


def test_solo_elo_probs_rows_are_valid_distributions() -> None:
    model = OrderedLogit(c1=-120.0, c2=80.0, scale=200.0)
    dr = np.linspace(-800.0, 800.0, 33)

    probs = solo_elo_probs(dr, model)

    assert probs.shape == (33, 3)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-9)
    assert (probs >= 0.0).all()
    assert (probs <= 1.0).all()


def test_home_win_probability_is_monotone_in_dr() -> None:
    model = OrderedLogit(c1=-120.0, c2=80.0, scale=200.0)
    dr = np.array([-400.0, 0.0, 400.0])

    probs = solo_elo_probs(dr, model)

    assert probs[0, 0] < probs[1, 0] < probs[2, 0]


def test_fit_recovers_synthetic_parameters() -> None:
    rng = np.random.default_rng(42)
    true_model = OrderedLogit(c1=-120.0, c2=80.0, scale=200.0)
    n = 20_000
    dr = rng.normal(0.0, 250.0, size=n)
    probs = solo_elo_probs(dr, true_model)
    cumulative = probs.cumsum(axis=1)
    outcome_idx = (rng.random(n)[:, None] > cumulative).sum(axis=1)

    fitted = fit_solo_elo(dr, outcome_idx)

    assert abs(fitted.c1 - true_model.c1) < 25.0
    assert abs(fitted.c2 - true_model.c2) < 25.0
    assert abs(fitted.scale - true_model.scale) / true_model.scale < 0.15
    assert fitted.c1 < fitted.c2
    assert fitted.scale > 0.0
