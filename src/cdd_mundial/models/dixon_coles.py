"""Dixon-Coles bivariate Poisson model: weighted MLE, analytic gradient, and fit-at-cutoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def tau_log(
    x: np.ndarray,
    y: np.ndarray,
    lam: np.ndarray,
    mu: np.ndarray,
    rho: float,
) -> np.ndarray:
    """log tau vectorizado; solo (0,0),(0,1),(1,0),(1,1) difieren de 0.

    Fuente: Dixon & Coles (1997), ecuaciones 4.2-4.3.
    """
    t = np.ones_like(lam)
    t = np.where((x == 0) & (y == 0), 1.0 - lam * mu * rho, t)
    t = np.where((x == 0) & (y == 1), 1.0 + lam * rho, t)
    t = np.where((x == 1) & (y == 0), 1.0 + mu * rho, t)
    t = np.where((x == 1) & (y == 1), 1.0 - rho, t)
    return np.log(t)


def neg_log_lik(
    params: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    home_idx: np.ndarray,
    away_idx: np.ndarray,
    is_home: np.ndarray,
    w: np.ndarray,
    n_teams: int,
) -> float:
    """Weighted Dixon-Coles negative log-likelihood with an identifiability penalty.

    Layout de params: [att (n), dfn (n), c, gamma, rho]. La penalizacion
    ``1000.0 * (att.sum()**2 + dfn.sum()**2)`` elimina la direccion plana de la
    NLL (att y dfn solo estan identificados hasta una constante aditiva conjunta);
    sin ella L-BFGS-B converge mal y los parametros derivan arbitrariamente.
    """
    att, dfn = params[:n_teams], params[n_teams : 2 * n_teams]
    c, gamma, rho = params[-3], params[-2], params[-1]
    log_lam = c + att[home_idx] - dfn[away_idx] + gamma * is_home
    log_mu = c + att[away_idx] - dfn[home_idx]
    lam, mu = np.exp(log_lam), np.exp(log_mu)
    # log Poisson sin el termino factorial (constante en params).
    ll = w * (tau_log(x, y, lam, mu, rho) + x * log_lam - lam + y * log_mu - mu)
    return float(-ll.sum() + 1000.0 * (att.sum() ** 2 + dfn.sum() ** 2))


def grad_neg_log_lik(
    params: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    home_idx: np.ndarray,
    away_idx: np.ndarray,
    is_home: np.ndarray,
    w: np.ndarray,
    n_teams: int,
) -> np.ndarray:
    """Analytic gradient of :func:`neg_log_lik` (required for fast L-BFGS-B fits)."""
    att, dfn = params[:n_teams], params[n_teams : 2 * n_teams]
    c, gamma, rho = params[-3], params[-2], params[-1]
    log_lam = c + att[home_idx] - dfn[away_idx] + gamma * is_home
    log_mu = c + att[away_idx] - dfn[home_idx]
    lam, mu = np.exp(log_lam), np.exp(log_mu)

    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)

    dtau_dloglam = np.zeros_like(lam)
    dtau_dloglam = np.where(m00, -lam * mu * rho / (1.0 - lam * mu * rho), dtau_dloglam)
    dtau_dloglam = np.where(m01, lam * rho / (1.0 + lam * rho), dtau_dloglam)

    dtau_dlogmu = np.zeros_like(mu)
    dtau_dlogmu = np.where(m00, -lam * mu * rho / (1.0 - lam * mu * rho), dtau_dlogmu)
    dtau_dlogmu = np.where(m10, mu * rho / (1.0 + mu * rho), dtau_dlogmu)

    glam = w * (x - lam + dtau_dloglam)
    gmu = w * (y - mu + dtau_dlogmu)

    dll_drho = np.zeros_like(lam)
    dll_drho = np.where(m00, w * (-lam * mu) / (1.0 - lam * mu * rho), dll_drho)
    dll_drho = np.where(m01, w * lam / (1.0 + lam * rho), dll_drho)
    dll_drho = np.where(m10, w * mu / (1.0 + mu * rho), dll_drho)
    dll_drho = np.where(m11, w * (-1.0) / (1.0 - rho), dll_drho)

    grad_att = np.bincount(home_idx, weights=glam, minlength=n_teams) + np.bincount(
        away_idx, weights=gmu, minlength=n_teams
    )
    grad_dfn = -np.bincount(away_idx, weights=glam, minlength=n_teams) - np.bincount(
        home_idx, weights=gmu, minlength=n_teams
    )
    grad_c = glam.sum() + gmu.sum()
    grad_gamma = (glam * is_home).sum()
    grad_rho = dll_drho.sum()

    # Negar todo: la funcion objetivo es la NEG log-lik; luego sumar la penalizacion.
    grad = -np.concatenate([grad_att, grad_dfn, [grad_c, grad_gamma, grad_rho]])
    grad[:n_teams] += 2000.0 * att.sum()
    grad[n_teams : 2 * n_teams] += 2000.0 * dfn.sum()
    return grad


@dataclass(frozen=True)
class DixonColesModel:
    """Fitted Dixon-Coles parameters keyed by canonical team slugs."""

    teams: tuple[str, ...]
    att: tuple[float, ...]
    dfn: tuple[float, ...]
    c: float
    gamma: float
    rho: float
    xi: float
    cutoff: str
    fitted_at_utc: str


def fit_dixon_coles(matches: pd.DataFrame, cutoff: pd.Timestamp, xi: float) -> DixonColesModel:
    """Fit Dixon-Coles on matches strictly before ``cutoff`` with exponential decay.

    Los pesos w = exp(-xi * dias) con w < 1e-4 se descartan: el truncamiento es
    numericamente neutro (equivalente al "todo el historico" de D-07 porque los
    pesos descartados son < 0.0001). Los 677 partidos con ET/shootout SE INCLUYEN
    en el fit de goles (decision del Director sobre OQ5; ~1.4% de filas).
    """
    train = matches[matches["date"] < cutoff]
    w = np.exp(-xi * (cutoff - train["date"]).dt.days.to_numpy())
    keep = w >= 1e-4
    train = train[keep]
    w = w[keep]
    if train.empty:
        raise ValueError(f"no training matches remain before cutoff {cutoff!r} with xi={xi!r}")

    teams = tuple(sorted(set(train["home_team_id"]) | set(train["away_team_id"])))
    index = {team: position for position, team in enumerate(teams)}
    home_idx = train["home_team_id"].map(index).to_numpy()
    away_idx = train["away_team_id"].map(index).to_numpy()
    x = train["home_score"].to_numpy(dtype=float)
    y = train["away_score"].to_numpy(dtype=float)
    is_home = (~train["neutral"].astype(bool)).to_numpy(dtype=float)
    n_teams = len(teams)

    goal_mean = float(np.concatenate([x, y]).mean())
    x0 = np.concatenate([np.zeros(2 * n_teams), [np.log(goal_mean), 0.1, 0.0]])
    bounds = [(None, None)] * (2 * n_teams + 2) + [(-0.2, 0.2)]

    result = minimize(
        neg_log_lik,
        x0,
        args=(x, y, home_idx, away_idx, is_home, w, n_teams),
        jac=grad_neg_log_lik,
        method="L-BFGS-B",
        bounds=bounds,
    )
    if not result.success:
        raise ValueError(f"Dixon-Coles fit did not converge: {result.message}")

    params = result.x
    return DixonColesModel(
        teams=teams,
        att=tuple(float(value) for value in params[:n_teams]),
        dfn=tuple(float(value) for value in params[n_teams : 2 * n_teams]),
        c=float(params[-3]),
        gamma=float(params[-2]),
        rho=float(params[-1]),
        xi=float(xi),
        cutoff=cutoff.strftime("%Y-%m-%d"),
        fitted_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
