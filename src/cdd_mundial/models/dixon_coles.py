"""Dixon-Coles bivariate Poisson model: weighted MLE, analytic gradient, and fit-at-cutoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from cdd_mundial.data.identities import UnknownTeamError

_REQUIRED_CTX_KEYS = ("neutral", "date", "tournament_type")


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

    def __post_init__(self) -> None:
        if not (len(self.att) == len(self.dfn) == len(self.teams)):
            raise ValueError(
                "teams/att/dfn lengths must match: "
                f"{len(self.teams)}/{len(self.att)}/{len(self.dfn)}"
            )
        if not -0.2 <= self.rho <= 0.2:
            raise ValueError(f"rho must lie in [-0.2, 0.2], got {self.rho!r}")

    def predict_lambdas(self, team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
        """Return (lambda_a, lambda_b): expected goals for team_a and team_b.

        ctx keys: neutral (bool), date (datetime), tournament_type (str).
        team IDs are canonical slugs from teams.csv.
        Convention: when ctx["neutral"] is False, team_a IS the home/host side and
        receives gamma (en 2026 solo MEX/USA/CAN tendran neutral=False).
        """
        missing = [key for key in _REQUIRED_CTX_KEYS if key not in ctx]
        if missing:
            raise ValueError(f"ctx is missing required key(s): {missing!r}")
        unknown = [slug for slug in (team_a, team_b) if slug not in self.teams]
        if unknown:
            raise UnknownTeamError(f"unknown team slug(s) for Dixon-Coles model: {unknown!r}")

        index = {team: position for position, team in enumerate(self.teams)}
        a, b = index[team_a], index[team_b]
        is_home = 0.0 if ctx["neutral"] else 1.0
        log_lam = self.c + self.att[a] - self.dfn[b] + self.gamma * is_home
        log_mu = self.c + self.att[b] - self.dfn[a]
        return (float(np.exp(log_lam)), float(np.exp(log_mu)))

    def to_dict(self) -> dict[str, Any]:
        """Convert the model to deterministic JSON-compatible values."""
        return {
            "att": list(self.att),
            "c": self.c,
            "cutoff": self.cutoff,
            "dfn": list(self.dfn),
            "fitted_at_utc": self.fitted_at_utc,
            "gamma": self.gamma,
            "rho": self.rho,
            "teams": list(self.teams),
            "xi": self.xi,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> DixonColesModel:
        """Rebuild a model, revalidating invariants via ``__post_init__``."""
        return cls(
            teams=tuple(str(team) for team in payload["teams"]),
            att=tuple(float(value) for value in payload["att"]),
            dfn=tuple(float(value) for value in payload["dfn"]),
            c=float(payload["c"]),
            gamma=float(payload["gamma"]),
            rho=float(payload["rho"]),
            xi=float(payload["xi"]),
            cutoff=str(payload["cutoff"]),
            fitted_at_utc=str(payload["fitted_at_utc"]),
        )

    def save(self, path: Path) -> None:
        """Write deterministic UTF-8 JSON (plain JSON, never pickle, for dc_params)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        path.write_text(payload, encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path: Path) -> DixonColesModel:
        """Load and revalidate a persisted model."""
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def score_matrix(lam: float, mu: float, rho: float, max_goals: int = 10) -> np.ndarray:
    """Return the (max_goals+1)^2 scoreline matrix with tau applied; rows = team_a goals."""
    goals = np.arange(max_goals + 1)
    matrix = np.outer(poisson.pmf(goals, lam), poisson.pmf(goals, mu))
    matrix[0, 0] *= 1.0 - lam * mu * rho
    matrix[0, 1] *= 1.0 + lam * rho
    matrix[1, 0] *= 1.0 + mu * rho
    matrix[1, 1] *= 1.0 - rho
    return matrix / matrix.sum()


def wdl_from_lambdas(
    lam: float, mu: float, rho: float, max_goals: int = 10
) -> tuple[float, float, float]:
    """Return (p_win, p_draw, p_loss) for team_a from the scoreline matrix.

    Cuando team_a es el home, el mapeo es [home_win, draw, away_win].
    """
    matrix = score_matrix(lam, mu, rho, max_goals)
    p_win = float(np.tril(matrix, -1).sum())
    p_draw = float(np.trace(matrix))
    p_loss = float(np.triu(matrix, 1).sum())
    return p_win, p_draw, p_loss


def _latest_params_path(models_dir: Path) -> Path:
    candidates = sorted(models_dir.glob("dc_params_*.json"))
    if not candidates:
        raise FileNotFoundError(
            f"no dc_params_*.json found in {models_dir} — "
            "run cdd_mundial.models.validation first"
        )
    return candidates[-1]


def load_production_model(models_dir: Path = Path("data/processed/models")) -> DixonColesModel:
    """Load the newest persisted dc_params_*.json (ISO dates sort lexicographically)."""
    return DixonColesModel.load(_latest_params_path(models_dir))


_PRODUCTION_MODEL: tuple[Path, float, DixonColesModel] | None = None


def predict_lambdas(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    """
    Returns (lambda_a, lambda_b): expected goals for team_a and team_b.
    ctx keys: neutral (bool), date (datetime), tournament_type (str)
    team IDs are canonical slugs from teams.csv.
    Convention: when ctx["neutral"] is False, team_a IS the home/host side and receives gamma.
    """
    global _PRODUCTION_MODEL
    latest = _latest_params_path(Path("data/processed/models"))
    mtime = latest.stat().st_mtime
    if _PRODUCTION_MODEL is None or _PRODUCTION_MODEL[:2] != (latest, mtime):
        _PRODUCTION_MODEL = (latest, mtime, DixonColesModel.load(latest))
    return _PRODUCTION_MODEL[2].predict_lambdas(team_a, team_b, ctx)


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
    # A neutral gamma start avoids a degenerate high-c/negative-gamma basin seen
    # in sparse recent windows while leaving the fitted home effect unconstrained.
    x0 = np.concatenate([np.zeros(2 * n_teams), [np.log(goal_mean), 0.0, 0.0]])
    bounds = [(None, None)] * (2 * n_teams + 2) + [(-0.2, 0.2)]

    with np.errstate(divide="ignore", invalid="ignore"):
        result = minimize(
            neg_log_lik,
            x0,
            args=(x, y, home_idx, away_idx, is_home, w, n_teams),
            jac=grad_neg_log_lik,
            method="L-BFGS-B",
            bounds=bounds,
            options={"ftol": 1e-8, "maxiter": 3000, "maxls": 50},
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
