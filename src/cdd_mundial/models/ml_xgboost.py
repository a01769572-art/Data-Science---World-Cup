"""Conservative multiclass XGBoost wrapper for the ML upgrade candidate (Phase 5, ML-02).

This is the *first* ML candidate that competes against the structural baseline. By
design it stays small, deterministic, and auditable rather than chasing leaderboard
scores (research section 4):

* objective ``multi:softprob`` with ``num_class=3`` — the canonical 3-way target
  (``0=home_win``, ``1=draw``, ``2=away_win``) reused verbatim from
  :func:`cdd_mundial.models.loading.load_matches`;
* shallow trees (``max_depth=3``) and a modest number of boosting rounds — the hard
  question is whether ML adds signal beyond the baseline, not whether a deep search
  can overfit four holdouts;
* one pinned seed plus single-threaded, deterministic tree construction so repeated
  fits and predictions are bit-identical (threat T-05-05);
* natural-unit features only — no scaler is baked in (D-05); XGBoost is invariant to
  monotone feature rescaling so the canonical dataset needs none.

The wrapper deliberately exposes only ``fit`` / ``predict_proba`` and an immutable
``params`` view. It does **not** do hyperparameter search, calibration, or
eligibility filtering — those belong to later plans / the harness, keeping this
module a thin, testable model contract.
"""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import xgboost as xgb

# The canonical 3-way target cardinality (loading.OUTCOME_LABELS). Hard-wired: the
# wrapper rejects any training target that is not exactly the three canonical classes.
NUM_CLASSES = 3

# Default seed. Pinned so the wrapper is reproducible out of the box; callers can
# override per fold. XGBoost is seeded via ``seed``; single-thread + ``exact`` tree
# method removes the remaining sources of run-to-run nondeterminism on this data size.
DEFAULT_SEED = 20260616

# Conservative, auditable defaults (research section 4). Kept small on purpose for a
# ~5k-row supervised problem with 12 features; no broad search.
_BASE_PARAMS: dict[str, object] = {
    "objective": "multi:softprob",
    "num_class": NUM_CLASSES,
    "max_depth": 3,
    "eta": 0.05,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "min_child_weight": 5.0,
    "reg_lambda": 1.0,
    "tree_method": "exact",
    "nthread": 1,
}

DEFAULT_NUM_BOOST_ROUND = 200


class MulticlassXGBoost:
    """A small, deterministic 3-class probability model over fixed natural-unit features.

    Parameters
    ----------
    seed
        Random seed pinned into the booster for reproducible fits (T-05-05).
    num_boost_round
        Number of boosting rounds. Modest by default; later plans may tune within
        temporal folds, never as a broad leaderboard search.
    params
        Optional overrides merged onto the conservative defaults. ``objective`` and
        ``num_class`` are always forced to the canonical 3-way contract.
    """

    def __init__(
        self,
        *,
        seed: int = DEFAULT_SEED,
        num_boost_round: int = DEFAULT_NUM_BOOST_ROUND,
        params: dict[str, object] | None = None,
    ) -> None:
        merged = deepcopy(_BASE_PARAMS)
        if params:
            merged.update(params)
        # The canonical contract is non-negotiable regardless of caller overrides.
        merged["objective"] = "multi:softprob"
        merged["num_class"] = NUM_CLASSES
        merged["seed"] = int(seed)
        self._params: dict[str, object] = merged
        self._seed = int(seed)
        self._num_boost_round = int(num_boost_round)
        self._booster: xgb.Booster | None = None
        self._n_features: int | None = None

    @property
    def params(self) -> dict[str, object]:
        """Immutable view of the effective booster params (deep-copied)."""
        return deepcopy(self._params)

    @property
    def n_features(self) -> int | None:
        return self._n_features

    def fit(self, x: np.ndarray, y: np.ndarray) -> MulticlassXGBoost:
        """Fit the booster on a natural-unit feature matrix and 3-way integer target.

        Parameters
        ----------
        x
            ``(n, n_features)`` float feature matrix (no scaling applied; D-05).
        y
            ``(n,)`` integer target in ``{0, 1, 2}``; all three classes must be present.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y)
        if x.ndim != 2:
            raise ValueError(f"x must be 2-D (n, n_features), got shape {x.shape!r}")
        if y.ndim != 1 or len(y) != len(x):
            raise ValueError("y must be 1-D and aligned with x rows")
        if len(x) == 0:
            raise ValueError("cannot fit on an empty feature matrix")

        labels = np.unique(y)
        if not np.array_equal(labels, np.arange(NUM_CLASSES)):
            raise ValueError(
                "MulticlassXGBoost requires exactly the canonical 3 classes {0,1,2} present; "
                f"got labels {labels.tolist()!r}"
            )

        dtrain = xgb.DMatrix(x, label=y.astype(float))
        self._booster = xgb.train(
            self._params,
            dtrain,
            num_boost_round=self._num_boost_round,
        )
        self._n_features = int(x.shape[1])
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Return ``(n, 3)`` class probabilities in canonical [home_win, draw, away_win] order."""
        if self._booster is None or self._n_features is None:
            raise RuntimeError("predict_proba called before fit")
        x = np.asarray(x, dtype=float)
        if x.ndim != 2:
            raise ValueError(f"x must be 2-D (n, n_features), got shape {x.shape!r}")
        if x.shape[1] != self._n_features:
            raise ValueError(
                f"feature count mismatch: model was fit on {self._n_features} features, "
                f"got {x.shape[1]}"
            )
        probs = self._booster.predict(xgb.DMatrix(x))
        probs = np.asarray(probs, dtype=float).reshape(len(x), NUM_CLASSES)
        # softprob already sums to 1; renormalize defensively against float drift.
        return probs / probs.sum(axis=1, keepdims=True)
