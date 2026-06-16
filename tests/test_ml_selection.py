"""Production model-selection layer for live dual publication + fallback (Phase 5, ML-03).

These tests freeze the contract that turns the Phase-5 promotion gate verdict into a
*per-match* publication decision (D-13/D-14, T-05-10/T-05-11):

* publication is always **dual** when an upgrade is promoted: the baseline row is
  published unconditionally and the promoted candidate is published *alongside* it,
  never as a silent replacement;
* if the gate did not promote a candidate, OR a specific match is ML-ineligible
  (``ml_eligible == False`` / no ML probability available), the published prediction
  falls back to the baseline *explicitly*, with a recorded reason;
* every published row carries traceability of which model family produced it and why,
  so no failed-gate or ineligible candidate can quietly displace the baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cdd_mundial.live.ml_selection import (
    BASELINE_FAMILY,
    UPGRADE_FAMILY,
    PublicationDecision,
    build_dual_publication,
    decide_publication,
)


def _baseline_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": ["WC26-001", "WC26-002", "WC26-003"],
            "team_a": ["alpha", "charlie", "echo"],
            "team_b": ["bravo", "delta", "foxtrot"],
            "prob_a": [0.50, 0.40, 0.33],
            "prob_draw": [0.27, 0.30, 0.34],
            "prob_b": [0.23, 0.30, 0.33],
        }
    )


def _promoted_gate() -> dict:
    return {
        "promoted": True,
        "winner": "ensemble",
        "mean_log_loss": {"baseline": 1.02, "ml": 1.00, "ensemble": 0.98},
        "beats_baseline_all_holdouts": {"ml": True, "ensemble": True},
    }


def _no_promotion_gate() -> dict:
    return {
        "promoted": False,
        "winner": "baseline",
        "mean_log_loss": {"baseline": 1.00, "ml": 1.03, "ensemble": 1.01},
        "beats_baseline_all_holdouts": {"ml": False, "ensemble": False},
    }


def _ml_probs() -> dict[str, np.ndarray]:
    # ML candidate probabilities for the two ML-eligible matches only.
    return {
        "WC26-001": np.array([0.55, 0.25, 0.20]),
        "WC26-002": np.array([0.42, 0.31, 0.27]),
    }


# --------------------------------------------------------------------------- #
# decide_publication: the pure per-match decision                             #
# --------------------------------------------------------------------------- #


def test_promoted_and_eligible_publishes_dual_baseline_and_upgrade() -> None:
    decision = decide_publication(
        match_id="WC26-001",
        gate_promoted=True,
        winner="ensemble",
        ml_eligible=True,
        has_ml_prob=True,
    )
    assert isinstance(decision, PublicationDecision)
    # Dual publication: baseline stays, the upgrade is added (D-14).
    assert decision.baseline_published is True
    assert decision.upgrade_published is True
    assert decision.published_family == UPGRADE_FAMILY
    assert decision.fallback_reason is None


def test_ineligible_match_falls_back_to_baseline_explicitly() -> None:
    """An ML-ineligible row (D-04) reverts to baseline even when the gate promoted."""
    decision = decide_publication(
        match_id="WC26-003",
        gate_promoted=True,
        winner="ensemble",
        ml_eligible=False,
        has_ml_prob=False,
    )
    assert decision.baseline_published is True
    assert decision.upgrade_published is False
    assert decision.published_family == BASELINE_FAMILY
    assert decision.fallback_reason == "ml_ineligible"


def test_failed_gate_keeps_baseline_only_with_reason() -> None:
    """If the gate did not promote, no upgrade is published even for eligible rows."""
    decision = decide_publication(
        match_id="WC26-001",
        gate_promoted=False,
        winner="baseline",
        ml_eligible=True,
        has_ml_prob=True,
    )
    assert decision.baseline_published is True
    assert decision.upgrade_published is False
    assert decision.published_family == BASELINE_FAMILY
    assert decision.fallback_reason == "gate_not_promoted"


def test_promoted_but_missing_ml_prob_falls_back() -> None:
    """Eligible by metadata but no ML probability available -> explicit baseline fallback."""
    decision = decide_publication(
        match_id="WC26-002",
        gate_promoted=True,
        winner="ml",
        ml_eligible=True,
        has_ml_prob=False,
    )
    assert decision.upgrade_published is False
    assert decision.published_family == BASELINE_FAMILY
    assert decision.fallback_reason == "ml_probability_unavailable"


# --------------------------------------------------------------------------- #
# build_dual_publication: the table-level orchestration                       #
# --------------------------------------------------------------------------- #


def test_dual_publication_preserves_every_baseline_row() -> None:
    """The baseline path is never shrunk: one published baseline row per input match."""
    result = build_dual_publication(
        baseline_predictions=_baseline_predictions(),
        gate=_promoted_gate(),
        ml_eligible={"WC26-001": True, "WC26-002": True, "WC26-003": False},
        ml_probs=_ml_probs(),
    )
    published = result.published
    # Every input match still has a published baseline row.
    baseline_rows = published[published["model_family"] == BASELINE_FAMILY]
    assert set(baseline_rows["match_id"]) == {"WC26-001", "WC26-002", "WC26-003"}
    # Baseline probabilities are unchanged from the input baseline table.
    src = _baseline_predictions().set_index("match_id")
    for row in baseline_rows.itertuples(index=False):
        assert row.prob_a == pytest.approx(float(src.loc[row.match_id, "prob_a"]))


def test_dual_publication_adds_upgrade_rows_only_for_eligible_promoted_matches() -> None:
    result = build_dual_publication(
        baseline_predictions=_baseline_predictions(),
        gate=_promoted_gate(),
        ml_eligible={"WC26-001": True, "WC26-002": True, "WC26-003": False},
        ml_probs=_ml_probs(),
    )
    upgrade_rows = result.published[result.published["model_family"] == UPGRADE_FAMILY]
    # Only the two eligible matches get an upgrade row; the ineligible one does not.
    assert set(upgrade_rows["match_id"]) == {"WC26-001", "WC26-002"}
    # Upgrade probabilities come from the ML candidate, not the baseline.
    upgrade_001 = upgrade_rows[upgrade_rows["match_id"] == "WC26-001"].iloc[0]
    assert upgrade_001["prob_a"] == pytest.approx(0.55)


def test_no_promotion_publishes_baseline_only_and_records_negative_result() -> None:
    """A failed gate publishes baseline-only: zero upgrade rows, explicit reasons (T-05-12)."""
    result = build_dual_publication(
        baseline_predictions=_baseline_predictions(),
        gate=_no_promotion_gate(),
        ml_eligible={"WC26-001": True, "WC26-002": True, "WC26-003": False},
        ml_probs=_ml_probs(),
    )
    assert result.promoted is False
    assert (result.published["model_family"] == UPGRADE_FAMILY).sum() == 0
    # Every published row is baseline, each carrying the gate_not_promoted reason.
    assert (result.published["model_family"] == BASELINE_FAMILY).all()
    reasons = set(result.published["fallback_reason"].dropna())
    assert reasons == {"gate_not_promoted"}


def test_every_published_row_carries_provenance() -> None:
    result = build_dual_publication(
        baseline_predictions=_baseline_predictions(),
        gate=_promoted_gate(),
        ml_eligible={"WC26-001": True, "WC26-002": True, "WC26-003": False},
        ml_probs=_ml_probs(),
    )
    published = result.published
    # Provenance columns exist and are populated for every published row (T-05-11).
    for col in ("model_family", "published_family", "fallback_reason", "winner"):
        assert col in published.columns
    assert published["model_family"].isin({BASELINE_FAMILY, UPGRADE_FAMILY}).all()
    # The ineligible match's baseline row records why the upgrade did not displace it.
    ineligible = published[
        (published["match_id"] == "WC26-003") & (published["model_family"] == BASELINE_FAMILY)
    ].iloc[0]
    assert ineligible["fallback_reason"] == "ml_ineligible"


def test_selection_summary_counts_are_auditable() -> None:
    result = build_dual_publication(
        baseline_predictions=_baseline_predictions(),
        gate=_promoted_gate(),
        ml_eligible={"WC26-001": True, "WC26-002": True, "WC26-003": False},
        ml_probs=_ml_probs(),
    )
    summary = result.summary
    assert summary["promoted"] is True
    assert summary["winner"] == "ensemble"
    assert summary["n_baseline_published"] == 3
    assert summary["n_upgrade_published"] == 2
    assert summary["n_baseline_fallback"] == 1  # the ineligible match
    assert summary["fallback_reasons"]["ml_ineligible"] == 1


def test_baseline_predictions_are_never_mutated() -> None:
    original = _baseline_predictions()
    snapshot = original.copy(deep=True)
    build_dual_publication(
        baseline_predictions=original,
        gate=_promoted_gate(),
        ml_eligible={"WC26-001": True, "WC26-002": True, "WC26-003": False},
        ml_probs=_ml_probs(),
    )
    pd.testing.assert_frame_equal(original, snapshot)
