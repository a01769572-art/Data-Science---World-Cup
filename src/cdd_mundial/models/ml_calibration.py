"""Multiclass probability calibration for the ML/ensemble candidates (Phase 5, ML-04).

The phase must compare candidates in their *best calibrated form*, and the choice
between Platt/sigmoid and isotonic must be empirical, not assumed (D-11/D-12). This
module provides the two pieces that requirement needs:

* :class:`MulticlassCalibrator` — a thin, deterministic one-vs-rest calibrator for
  3-class probability vectors. It fits one per-class 1-D calibrator (isotonic or
  sigmoid/Platt) on already-computed probabilities + true labels, then transforms a
  probability matrix by applying each per-class map and renormalizing so every output
  row stays a valid distribution. ``method="none"`` is an exact pass-through so the
  uncalibrated candidate competes on equal footing.

* :func:`select_best_calibration` — fits each method on a calibration slice and scores
  it on a *disjoint* validation slice by log-loss, returning the empirical winner plus
  every method's score for auditability.

Anti-leakage is structural (T-05-07). A calibrator only ever sees the rows passed to
``fit``; the harness (``ml_validation``) is responsible for passing strictly
pre-holdout rows. ``transform`` is a pure function of fitted state, so applying a
calibrator to a later holdout cannot perturb its fit. We deliberately calibrate on
already-computed probabilities rather than wrapping the estimator: the ML candidate is
a custom XGBoost wrapper and the ensemble is a probability blend that has no single
``sklearn`` estimator, so a probability-in/probability-out calibrator is the only
representation that covers all three candidates uniformly.

The per-class sigmoid uses scikit-learn's internal ``_SigmoidCalibration`` (the exact
Platt fit ``CalibratedClassifierCV(method="sigmoid")`` uses), and the isotonic path
uses ``sklearn.isotonic.IsotonicRegression`` — the same primitives the project's
mandated calibration stack is built on. ``cv="prefit"`` is not used anywhere; this is
an explicit calibrate-already-computed-probabilities design, not a wrapped estimator.
"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import _SigmoidCalibration
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import log_loss

NUM_CLASSES = 3

# The calibration methods compared empirically (D-12). "none" is the uncalibrated
# pass-through baseline so the comparison is honest.
CALIBRATION_METHODS: tuple[str, ...] = ("none", "sigmoid", "isotonic")

# Floor used when renormalizing per-class calibrated scores so a row whose per-class
# maps all collapse to ~0 still yields a finite, valid distribution instead of 0/0.
_EPS = 1e-12


def _validate_probs(probs: np.ndarray) -> np.ndarray:
    arr = np.asarray(probs, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != NUM_CLASSES:
        raise ValueError(
            f"expected a (n, {NUM_CLASSES}) probability matrix, got shape {arr.shape!r}"
        )
    return arr


def _renormalize(scores: np.ndarray) -> np.ndarray:
    """Turn per-class one-vs-rest scores into valid 3-class rows.

    Clips to ``[0, 1]`` (per-class maps are calibrated probabilities) and renormalizes
    each row. Rows whose scores all vanish fall back to a uniform distribution so the
    output is always a valid distribution.
    """
    clipped = np.clip(scores, 0.0, 1.0)
    row_sums = clipped.sum(axis=1, keepdims=True)
    safe = np.where(row_sums < _EPS, 1.0, row_sums)
    out = clipped / safe
    # Rows that were entirely ~0 become uniform rather than NaN/zero.
    degenerate = (row_sums < _EPS).ravel()
    if degenerate.any():
        out[degenerate] = 1.0 / NUM_CLASSES
    return out


class MulticlassCalibrator:
    """One-vs-rest calibrator for 3-class probability vectors (isotonic / sigmoid / none).

    Parameters
    ----------
    method
        ``"isotonic"``, ``"sigmoid"`` (Platt), or ``"none"`` (exact pass-through).

    Notes
    -----
    Calibrators are fit on the probabilities and labels passed to :meth:`fit` only.
    The harness must pass strictly pre-holdout rows; this class never reaches for data
    it was not given (T-05-07).
    """

    def __init__(self, *, method: str = "isotonic") -> None:
        if method not in CALIBRATION_METHODS:
            raise ValueError(
                f"unknown calibration method {method!r}; expected one of {CALIBRATION_METHODS}"
            )
        self.method = method
        self._per_class: list[object] | None = None
        self._n_fit_samples: int | None = None

    @property
    def n_fit_samples(self) -> int | None:
        """Number of rows the per-class calibrators were fit on (audit of leakage)."""
        return self._n_fit_samples

    def fit(self, probs: np.ndarray, y: np.ndarray) -> MulticlassCalibrator:
        """Fit one per-class 1-D calibrator on already-computed probabilities + labels."""
        arr = _validate_probs(probs)
        y = np.asarray(y, dtype=int)
        if y.ndim != 1 or len(y) != len(arr):
            raise ValueError("y must be 1-D and aligned with the probability rows")

        if self.method == "none":
            self._per_class = []
            self._n_fit_samples = int(len(arr))
            return self

        per_class: list[object] = []
        for cls in range(NUM_CLASSES):
            target = (y == cls).astype(float)
            column = arr[:, cls]
            if self.method == "isotonic":
                calibrator = IsotonicRegression(
                    y_min=0.0, y_max=1.0, out_of_bounds="clip"
                )
                calibrator.fit(column, target)
            else:  # sigmoid / Platt
                calibrator = _SigmoidCalibration()
                calibrator.fit(column, target)
            per_class.append(calibrator)

        self._per_class = per_class
        self._n_fit_samples = int(len(arr))
        return self

    def transform(self, probs: np.ndarray) -> np.ndarray:
        """Apply the fitted per-class maps and renormalize to valid 3-class rows."""
        if self._per_class is None:
            raise RuntimeError("transform called before fit")
        arr = _validate_probs(probs)
        if self.method == "none":
            # Exact pass-through (defensive renormalize against float drift only).
            return arr / arr.sum(axis=1, keepdims=True)

        calibrated = np.empty_like(arr)
        for cls, calibrator in enumerate(self._per_class):
            column = arr[:, cls]
            if self.method == "isotonic":
                calibrated[:, cls] = calibrator.predict(column)
            else:
                calibrated[:, cls] = calibrator.predict(column)
        return _renormalize(calibrated)

    def fit_transform(self, probs: np.ndarray, y: np.ndarray) -> np.ndarray:
        return self.fit(probs, y).transform(probs)


def select_best_calibration(
    fit_probs: np.ndarray,
    fit_y: np.ndarray,
    val_probs: np.ndarray,
    val_y: np.ndarray,
) -> dict[str, object]:
    """Pick the best calibration method empirically by validation log-loss (D-12).

    Each method is fit on ``(fit_probs, fit_y)`` and scored on the *disjoint*
    ``(val_probs, val_y)`` slice. The winner is the argmin of validation log-loss; ties
    are broken deterministically by the fixed ``CALIBRATION_METHODS`` order with
    ``"none"`` first, so calibration is never preferred over the raw probabilities
    without strictly improving them.

    Returns a dict with the chosen ``method`` and the full ``log_loss_by_method`` map so
    the decision is reproducible from the artifact alone.
    """
    val_y = np.asarray(val_y, dtype=int)
    log_loss_by_method: dict[str, float] = {}
    for method in CALIBRATION_METHODS:
        calibrator = MulticlassCalibrator(method=method).fit(fit_probs, fit_y)
        calibrated_val = calibrator.transform(val_probs)
        log_loss_by_method[method] = float(
            log_loss(val_y, calibrated_val, labels=list(range(NUM_CLASSES)))
        )

    # Deterministic argmin in the fixed method order ("none" first => no-op preferred
    # on ties, so we only ever calibrate when it strictly helps).
    best_method = min(
        CALIBRATION_METHODS, key=lambda m: (log_loss_by_method[m], CALIBRATION_METHODS.index(m))
    )
    return {
        "method": best_method,
        "log_loss_by_method": log_loss_by_method,
    }


def fit_selected_calibrator(
    method: str,
    probs: np.ndarray,
    y: np.ndarray,
) -> MulticlassCalibrator:
    """Convenience: fit a calibrator of a chosen method on a slice (no selection)."""
    return MulticlassCalibrator(method=method).fit(probs, y)
