"""Wave 0 symmetry and unbiased-advance tests for the compact knockout resolver (SIM-05).

D-07/D-08: drawn knockout matches are resolved with a compact post-90-minute
advancement probability derived only from 90-minute (p_win, p_draw, p_loss).
No extra-time lambdas, no ET scorelines, no order-biased tie-breaking.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from cdd_mundial.models.dixon_coles import wdl_from_lambdas
from cdd_mundial.simulation.knockout import (
    advance_probability,
    post_draw_advance_probability,
    sample_post_draw_advancers,
)

TRIPLES = [
    (0.55, 0.25, 0.20),
    (0.10, 0.30, 0.60),
    (0.40, 0.20, 0.40),
    (0.05, 0.90, 0.05),
    (0.70, 0.00, 0.30),
]


# --- Test 1: swapping team order complements advancement probability exactly ---


@pytest.mark.parametrize("p_win, p_draw, p_loss", TRIPLES)
def test_swapping_team_order_complements_probability(
    p_win: float, p_draw: float, p_loss: float
) -> None:
    forward = advance_probability(p_win, p_draw, p_loss)
    swapped = advance_probability(p_loss, p_draw, p_win)

    assert forward + swapped == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("p_win, p_draw, p_loss", TRIPLES)
def test_post_draw_split_is_complementary(p_win: float, p_draw: float, p_loss: float) -> None:
    q_forward = post_draw_advance_probability(p_win, p_draw, p_loss)
    q_swapped = post_draw_advance_probability(p_loss, p_draw, p_win)

    assert q_forward + q_swapped == pytest.approx(1.0, abs=1e-12)


def test_complement_holds_for_real_dixon_coles_probabilities() -> None:
    p_win, p_draw, p_loss = wdl_from_lambdas(1.6, 1.1, -0.05)

    forward = advance_probability(p_win, p_draw, p_loss)
    swapped = advance_probability(p_loss, p_draw, p_win)

    assert forward + swapped == pytest.approx(1.0, abs=1e-9)
    assert forward > 0.5  # the stronger 90-minute side keeps its edge


# --- Test 2: identical-strength teams advance 50/50 ---


def test_identical_strength_is_half_theoretically() -> None:
    p_win, p_draw, p_loss = wdl_from_lambdas(1.25, 1.25, 0.0)

    assert post_draw_advance_probability(p_win, p_draw, p_loss) == pytest.approx(0.5, abs=1e-12)
    assert advance_probability(p_win, p_draw, p_loss) == pytest.approx(0.5, abs=1e-12)


def test_degenerate_certain_draw_splits_evenly() -> None:
    # p_win + p_loss == 0: no strength signal, the split must be exactly even.
    assert post_draw_advance_probability(0.0, 1.0, 0.0) == 0.5


def test_shrink_pulls_post_draw_split_toward_half() -> None:
    q_full = post_draw_advance_probability(0.6, 0.2, 0.2, shrink=1.0)
    q_half = post_draw_advance_probability(0.6, 0.2, 0.2, shrink=0.5)
    q_none = post_draw_advance_probability(0.6, 0.2, 0.2, shrink=0.0)

    assert q_none == 0.5
    assert 0.5 < q_half < q_full


def test_identical_strength_is_half_empirically() -> None:
    # >= 100k post-draw resolutions, both input orders, independent fixed seeds.
    n = 100_000
    q_identical = post_draw_advance_probability(0.3, 0.4, 0.3)

    uniforms_order_one = np.random.default_rng(1234).uniform(size=n)
    uniforms_order_two = np.random.default_rng(5678).uniform(size=n)
    rate_one = sample_post_draw_advancers(np.full(n, q_identical), uniforms_order_one).mean()
    rate_two = sample_post_draw_advancers(np.full(n, q_identical), uniforms_order_two).mean()

    assert abs(rate_one - 0.5) < 0.005
    assert abs(rate_two - 0.5) < 0.005


def test_empirical_order_bias_is_within_tolerance() -> None:
    # Order-normalized advancement rates for the same physical team must agree
    # across input orders within 0.005 (predeclared tolerance, fixed seeds).
    n = 100_000
    p_win, p_draw, p_loss = 0.35, 0.30, 0.35
    q_forward = post_draw_advance_probability(p_win, p_draw, p_loss)
    q_swapped = post_draw_advance_probability(p_loss, p_draw, p_win)

    forward_rate = sample_post_draw_advancers(
        np.full(n, q_forward), np.random.default_rng(20260613).uniform(size=n)
    ).mean()
    swapped_rate = sample_post_draw_advancers(
        np.full(n, q_swapped), np.random.default_rng(31415926).uniform(size=n)
    ).mean()

    team_a_rate_in_swapped_order = 1.0 - swapped_rate
    assert abs(forward_rate - 0.5) < 0.005
    assert abs(team_a_rate_in_swapped_order - 0.5) < 0.005
    assert abs(forward_rate - team_a_rate_in_swapped_order) < 0.005


# --- Test 3: every post-draw resolution produces exactly one winner, no ET lambdas ---


def test_draw_always_produces_one_winner() -> None:
    rng = np.random.default_rng(7)
    q_a = rng.uniform(size=512)
    uniforms = rng.uniform(size=512)

    a_advances = sample_post_draw_advancers(q_a, uniforms)
    b_advances = ~a_advances

    assert a_advances.dtype == np.bool_
    assert np.all(a_advances ^ b_advances)  # exactly one advancing side per draw
    assert a_advances.any() and b_advances.any()


def test_sampler_is_deterministic_for_fixed_uniforms() -> None:
    q_a = np.array([0.2, 0.5, 0.8])
    uniforms = np.array([0.1, 0.6, 0.79])

    first = sample_post_draw_advancers(q_a, uniforms)
    second = sample_post_draw_advancers(q_a, uniforms)

    assert np.array_equal(first, second)
    assert first.tolist() == [True, False, True]


def test_public_contract_uses_only_90_minute_probabilities() -> None:
    # D-07/D-08 gate: the resolver consumes (p_win, p_draw, p_loss) only.
    # Later engine work feeds deterministic uniforms keyed by match_id + seed.
    assert list(inspect.signature(advance_probability).parameters) == [
        "p_win",
        "p_draw",
        "p_loss",
        "shrink",
    ]
    assert list(inspect.signature(post_draw_advance_probability).parameters) == [
        "p_win",
        "p_draw",
        "p_loss",
        "shrink",
    ]
    assert list(inspect.signature(sample_post_draw_advancers).parameters) == [
        "q_a",
        "uniforms",
    ]


# --- Invalid inputs fail loudly ---


@pytest.mark.parametrize(
    "p_win, p_draw, p_loss",
    [
        (-0.1, 0.6, 0.5),
        (0.5, 0.5, 0.5),
        (0.2, 0.2, 0.2),
        (float("nan"), 0.5, 0.5),
    ],
)
def test_invalid_probability_triples_are_rejected(
    p_win: float, p_draw: float, p_loss: float
) -> None:
    with pytest.raises(ValueError):
        advance_probability(p_win, p_draw, p_loss)


@pytest.mark.parametrize("shrink", [-0.1, 1.1])
def test_shrink_outside_unit_interval_is_rejected(shrink: float) -> None:
    with pytest.raises(ValueError, match="shrink"):
        post_draw_advance_probability(0.4, 0.2, 0.4, shrink=shrink)


def test_sampler_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="q_a"):
        sample_post_draw_advancers(np.array([1.5]), np.array([0.5]))
    with pytest.raises(ValueError, match="shape"):
        sample_post_draw_advancers(np.array([0.5, 0.5]), np.array([0.5]))
    with pytest.raises(ValueError, match="uniforms"):
        sample_post_draw_advancers(np.array([0.5]), np.array([1.5]))
