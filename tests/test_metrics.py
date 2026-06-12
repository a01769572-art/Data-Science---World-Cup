import numpy as np
import pytest

from cdd_mundial.models.metrics import brier_multiclass, rps


def test_perfect_forecast_scores_zero() -> None:
    probs = np.array([[1.0, 0.0, 0.0]])
    outcome_idx = np.array([0])

    assert rps(probs, outcome_idx) == 0.0
    assert brier_multiclass(probs, outcome_idx) == 0.0


def test_uniform_forecast_matches_hand_computed_values() -> None:
    probs = np.array([[1 / 3, 1 / 3, 1 / 3]])
    outcome_idx = np.array([0])

    # RPS = ((1/3 - 1)^2 + (2/3 - 1)^2) / 2 = 5/18; Brier = (2/3)^2 + 2 * (1/3)^2 = 2/3
    assert rps(probs, outcome_idx) == pytest.approx(5 / 18)
    assert brier_multiclass(probs, outcome_idx) == pytest.approx(2 / 3)


def test_rps_penalizes_distant_errors_more() -> None:
    distant = rps(np.array([[0.8, 0.2, 0.0]]), np.array([2]))
    adjacent = rps(np.array([[0.0, 0.2, 0.8]]), np.array([2]))

    assert distant > adjacent
