"""Synthetic-data tests for the weighted Dixon-Coles MLE and its analytic gradient."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import approx_fprime

from cdd_mundial.models.dixon_coles import (
    fit_dixon_coles,
    grad_neg_log_lik,
    neg_log_lik,
)

TRUE_C = 0.2
TRUE_GAMMA = 0.3


def _gradient_batch() -> tuple[np.ndarray, tuple]:
    """Build a small seeded batch (4 teams, 50 matches) plus a generic params vector."""
    rng = np.random.default_rng(7)
    n_teams, n_matches = 4, 50
    home_idx = rng.integers(0, n_teams, n_matches)
    away_idx = (home_idx + rng.integers(1, n_teams, n_matches)) % n_teams
    x = rng.poisson(1.3, n_matches).astype(float)
    y = rng.poisson(1.1, n_matches).astype(float)
    is_home = rng.integers(0, 2, n_matches).astype(float)
    w = rng.uniform(0.5, 1.0, n_matches)
    att = rng.normal(0.0, 0.2, n_teams)
    dfn = rng.normal(0.0, 0.2, n_teams)
    params = np.concatenate([att, dfn, [0.15, 0.25, 0.05]])
    return params, (x, y, home_idx, away_idx, is_home, w, n_teams)


def test_analytic_gradient_matches_numeric() -> None:
    params, args = _gradient_batch()

    analytic = grad_neg_log_lik(params, *args)
    numeric = approx_fprime(params, neg_log_lik, 1.4901161193847656e-08, *args)

    rel_error = np.linalg.norm(analytic - numeric) / np.linalg.norm(analytic)
    assert rel_error < 1e-5


@pytest.fixture(scope="module")
def synthetic_fit() -> tuple:
    """Fit on 3000 seeded matches sampled from known independent-Poisson parameters."""
    rng = np.random.default_rng(42)
    n_teams, n_matches = 8, 3000
    teams = [f"team-{i}" for i in range(n_teams)]
    att_true = rng.uniform(-0.4, 0.4, n_teams)
    att_true -= att_true.mean()
    dfn_true = rng.uniform(-0.4, 0.4, n_teams)
    dfn_true -= dfn_true.mean()
    home = rng.integers(0, n_teams, n_matches)
    away = (home + rng.integers(1, n_teams, n_matches)) % n_teams
    lam = np.exp(TRUE_C + att_true[home] - dfn_true[away] + TRUE_GAMMA)
    mu = np.exp(TRUE_C + att_true[away] - dfn_true[home])
    matches = pd.DataFrame(
        {
            "date": pd.Timestamp("2025-12-31"),
            "home_team_id": [teams[i] for i in home],
            "away_team_id": [teams[j] for j in away],
            "home_score": rng.poisson(lam),
            "away_score": rng.poisson(mu),
            "neutral": False,
        }
    )

    model = fit_dixon_coles(matches, cutoff=pd.Timestamp("2026-01-01"), xi=0.0018)
    return model, att_true, dfn_true, tuple(teams)


def test_fit_recovers_known_synthetic_parameters(synthetic_fit: tuple) -> None:
    model, att_true, _dfn_true, teams = synthetic_fit

    assert model.teams == teams
    assert abs(model.c - TRUE_C) < 0.1
    assert abs(model.gamma - TRUE_GAMMA) < 0.1
    assert np.max(np.abs(np.array(model.att) - att_true)) < 0.15
    assert abs(model.rho) < 0.05


def test_fitted_rho_respects_lbfgsb_bounds(synthetic_fit: tuple) -> None:
    model = synthetic_fit[0]

    assert -0.2 <= model.rho <= 0.2


def test_low_weight_matches_are_excluded_from_training() -> None:
    rng = np.random.default_rng(11)
    pairs = [("team-a", "team-b"), ("team-b", "team-c"), ("team-c", "team-a")] * 20
    recent = pd.DataFrame(
        {
            "date": pd.Timestamp("2025-12-01"),
            "home_team_id": [home for home, _ in pairs],
            "away_team_id": [away for _, away in pairs],
            "home_score": rng.poisson(1.4, len(pairs)),
            "away_score": rng.poisson(1.1, len(pairs)),
            "neutral": False,
        }
    )
    # 2010-01-01 is ~5844 days before the cutoff: w = exp(-0.0018 * 5844) ~ 2.7e-5 < 1e-4.
    stale = pd.DataFrame(
        {
            "date": pd.Timestamp("2010-01-01"),
            "home_team_id": ["ancient"] * 5,
            "away_team_id": ["team-a"] * 5,
            "home_score": [1, 0, 2, 1, 0],
            "away_score": [0, 1, 1, 2, 0],
            "neutral": False,
        }
    )
    matches = pd.concat([recent, stale], ignore_index=True)

    model = fit_dixon_coles(matches, cutoff=pd.Timestamp("2026-01-01"), xi=0.0018)

    assert "ancient" not in model.teams


def test_identifiability_centering_holds(synthetic_fit: tuple) -> None:
    model = synthetic_fit[0]

    assert abs(sum(model.att)) < 0.01
    assert abs(sum(model.dfn)) < 0.01
