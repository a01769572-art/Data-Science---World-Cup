"""Multiclass temporal-calibration contract tests (Phase 5, Plan 03, ML-04).

These tests freeze the calibration contract BEFORE the phase compares calibrated
candidates. They encode three load-bearing properties:

* **Probability-mass preservation (D-11/D-12):** every calibrated output row is a
  valid 3-class distribution (>=0, sums to 1, shape ``(n, 3)``). Calibrating
  per-class one-vs-rest and renormalizing must never produce a degenerate row.
* **No future-holdout leakage (T-05-07):** a calibrator is fit only on probabilities
  and labels available strictly before the holdout it is later applied to. The fit
  object exposes no holdout rows and the transform is a pure function of already-fit
  state.
* **Empirical method selection (D-12):** sigmoid/Platt and isotonic are both
  available and the chosen winner per candidate is decided by held-out evidence, not
  assumed. ``isotonic`` is *not* hard-wired as superior.
"""

from __future__ import annotations

import numpy as np
import pytest


def _miscalibrated_probs(
    n: int = 600, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """A deliberately over-confident 3-class problem.

    True labels are drawn from a mild signal; the "raw" probabilities sharpen that
    signal (push mass toward the argmax) so a calibrator has real work to do. This
    lets the tests assert that calibration both preserves mass and can improve
    log-loss without depending on a trained model.
    """
    rng = np.random.default_rng(seed)
    # Latent class probabilities with a moderate signal.
    logits = rng.normal(0.0, 1.0, size=(n, 3))
    true_p = np.exp(logits)
    true_p /= true_p.sum(axis=1, keepdims=True)
    y = np.array([rng.choice(3, p=row) for row in true_p], dtype=int)
    # Over-confident raw probabilities: temperature < 1 sharpens.
    sharp = np.exp(logits / 0.5)
    raw = sharp / sharp.sum(axis=1, keepdims=True)
    return raw, y


def test_calibrated_outputs_are_valid_distributions() -> None:
    from cdd_mundial.models.ml_calibration import MulticlassCalibrator

    raw, y = _miscalibrated_probs(seed=1)
    for method in ("sigmoid", "isotonic"):
        cal = MulticlassCalibrator(method=method).fit(raw, y)
        out = cal.transform(raw)
        assert out.shape == raw.shape
        assert (out >= 0.0).all()
        assert (out <= 1.0).all()
        np.testing.assert_allclose(out.sum(axis=1), 1.0, atol=1e-6)


def test_identity_method_passes_probabilities_through() -> None:
    """The 'none' (uncalibrated) baseline must be a true no-op for fair comparison."""
    from cdd_mundial.models.ml_calibration import MulticlassCalibrator

    raw, y = _miscalibrated_probs(seed=2)
    cal = MulticlassCalibrator(method="none").fit(raw, y)
    np.testing.assert_allclose(cal.transform(raw), raw, atol=1e-12)


def test_transform_before_fit_is_rejected() -> None:
    from cdd_mundial.models.ml_calibration import MulticlassCalibrator

    with pytest.raises(RuntimeError):
        MulticlassCalibrator(method="isotonic").transform(np.zeros((3, 3)))


def test_unknown_method_is_rejected() -> None:
    from cdd_mundial.models.ml_calibration import MulticlassCalibrator

    with pytest.raises(ValueError):
        MulticlassCalibrator(method="platt-v2")


def test_calibrator_fits_only_on_provided_pre_holdout_rows() -> None:
    """T-05-07: the calibrator never sees the holdout it will be applied to.

    We fit on a strict training slice and then transform a disjoint holdout slice.
    The fit object must not retain any holdout row, and transforming the same holdout
    twice must be deterministic (pure function of fit state).
    """
    from cdd_mundial.models.ml_calibration import MulticlassCalibrator

    raw, y = _miscalibrated_probs(n=800, seed=3)
    train_raw, train_y = raw[:600], y[:600]
    holdout_raw = raw[600:]

    cal = MulticlassCalibrator(method="isotonic").fit(train_raw, train_y)
    first = cal.transform(holdout_raw)
    second = cal.transform(holdout_raw)
    np.testing.assert_array_equal(first, second)

    # The number of points each per-class isotonic fit saw equals the TRAIN size,
    # never train+holdout — proving holdout rows did not leak into fitting.
    assert cal.n_fit_samples == len(train_raw)


def test_select_best_calibration_names_a_method_and_improves_or_ties() -> None:
    """D-12: choose sigmoid vs isotonic vs none empirically by validation log-loss.

    The selection runs on a held-out validation slice that is disjoint from the slice
    used to fit the calibrators, mirroring the temporal protocol. The winner is named
    explicitly and never assumed to be isotonic.
    """
    from cdd_mundial.models.ml_calibration import select_best_calibration

    raw, y = _miscalibrated_probs(n=1200, seed=4)
    fit_raw, fit_y = raw[:600], y[:600]
    val_raw, val_y = raw[600:], y[600:]

    result = select_best_calibration(fit_raw, fit_y, val_raw, val_y)

    assert result["method"] in {"none", "sigmoid", "isotonic"}
    # Every candidate method must be scored so the choice is auditable.
    assert set(result["log_loss_by_method"]) == {"none", "sigmoid", "isotonic"}
    # The chosen method's validation log-loss is the minimum (argmin, deterministic).
    chosen = result["method"]
    chosen_score = result["log_loss_by_method"][chosen]
    assert chosen_score == min(result["log_loss_by_method"].values())
    # On an over-confident problem, calibration should not hurt vs raw.
    assert chosen_score <= result["log_loss_by_method"]["none"] + 1e-9


# --------------------------------------------------------------------------- #
# CR-01: calibration contract under the repaired train/serve-identity flow      #
# --------------------------------------------------------------------------- #


def test_calibrator_applied_to_same_producers_later_rows_stays_valid() -> None:
    """CR-01 contract: a calibrator fit on one producer's distribution and applied to
    that SAME producer's later (holdout) rows yields valid distributions.

    The repaired ``run_ml_comparison`` fits the calibrator on the inner model's raw
    probabilities and then transforms that *same* inner model's holdout raw
    probabilities. This freezes the property that flow relies on: per-class maps learned
    on a producer's output distribution remain a valid, mass-preserving transform when
    applied to fresh rows drawn from the identical distribution.
    """
    from cdd_mundial.models.ml_calibration import MulticlassCalibrator

    # One producer, two disjoint draws from its identical output distribution: the slice
    # used to fit the calibrator (mirrors inner_fit/inner_cal) and a later slice that
    # mirrors the holdout the SAME producer scores.
    raw, y = _miscalibrated_probs(n=900, seed=11)
    fit_raw, fit_y = raw[:600], y[:600]
    serve_raw = raw[600:]

    for method in ("none", "sigmoid", "isotonic"):
        cal = MulticlassCalibrator(method=method).fit(fit_raw, fit_y)
        served = cal.transform(serve_raw)
        assert served.shape == serve_raw.shape
        assert (served >= 0.0).all()
        assert (served <= 1.0).all()
        np.testing.assert_allclose(served.sum(axis=1), 1.0, atol=1e-6)


def test_calibration_choice_describes_the_distribution_it_is_applied_to() -> None:
    """CR-01: the empirical isotonic/Platt/none choice must describe the SAME producer
    distribution it is later applied to.

    Under the defect, the method was selected on the inner model's distribution but
    applied to a re-fit final model's (different) distribution, so the recorded log-loss
    evidence no longer described the scored probabilities. With train/serve identity the
    method selected on a producer's validation slice and the method that wins when scored
    on a fresh slice from the SAME producer agree, and the chosen calibrator does not
    worsen log-loss on the served distribution versus raw.
    """
    from cdd_mundial.models.ml_calibration import (
        MulticlassCalibrator,
        select_best_calibration,
    )
    from sklearn.metrics import log_loss

    raw, y = _miscalibrated_probs(n=1500, seed=12)
    fit_raw, fit_y = raw[:600], y[:600]
    val_raw, val_y = raw[600:1050], y[600:1050]
    serve_raw, serve_y = raw[1050:], y[1050:]  # same producer, fresh rows (the holdout)

    result = select_best_calibration(fit_raw, fit_y, val_raw, val_y)
    chosen = result["method"]

    # Apply the chosen calibrator (fit on the producer's fit slice) to the producer's
    # own later rows — exactly the repaired harness pattern.
    cal = MulticlassCalibrator(method=chosen).fit(fit_raw, fit_y)
    served = cal.transform(serve_raw)

    served_ll = float(log_loss(serve_y, served, labels=[0, 1, 2]))
    raw_served = serve_raw / serve_raw.sum(axis=1, keepdims=True)
    raw_ll = float(log_loss(serve_y, raw_served, labels=[0, 1, 2]))

    # Because the evidence and the served rows come from one distribution, the empirical
    # choice generalizes: the calibrated served log-loss is no worse than raw by more
    # than sampling noise (it is honestly calibrated for the served distribution).
    assert served_ll <= raw_ll + 0.02
