"""Per-match live model selection for dual publication + explicit fallback (Phase 5, ML-03).

This is the single, explicit production module that turns the Phase-5 promotion gate
verdict (:func:`cdd_mundial.models.ml_validation.evaluate_ml_gate`) into a *per-match*
publication decision. It centralizes the baseline / upgrade / fallback logic in one
place so a failed-gate or ML-ineligible candidate can never silently displace the
stable baseline line (T-05-10).

Two locked invariants drive every decision (D-13/D-14):

1. **Publication stays dual when an upgrade is promoted.** The baseline row is
   published *unconditionally*, and the promoted candidate is published *alongside* it
   — never as a replacement. The baseline remains the stable operational line.
2. **Fallback to baseline is explicit.** If the gate did not promote a candidate, OR a
   specific match is ML-ineligible (``ml_eligible == False`` under D-04) or has no ML
   probability available, the published prediction reverts to the baseline with a
   recorded ``fallback_reason``. The negative result is surfaced, never buried
   (T-05-11/T-05-12).

The module is deliberately a pure transformation over already-computed probabilities:
the baseline probabilities come from the existing live path (Dixon-Coles), the ML
probabilities are supplied by the caller (the calibrated promoted candidate), and this
layer only *decides and labels* which family is published per match. It never fits a
model or mutates its inputs, so it is trivially testable and auditable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

# Canonical family labels stamped on every published row for provenance (T-05-11).
BASELINE_FAMILY = "baseline"
UPGRADE_FAMILY = "upgrade"

# The explicit fallback reasons. ``None`` means the row was published by its intended
# family with no fallback; any other value names exactly why the upgrade did not
# (or could not) be published alongside / instead of the baseline for that match.
REASON_GATE_NOT_PROMOTED = "gate_not_promoted"
REASON_ML_INELIGIBLE = "ml_ineligible"
REASON_ML_PROB_UNAVAILABLE = "ml_probability_unavailable"

_PROB_COLUMNS = ("prob_a", "prob_draw", "prob_b")
_PUBLISH_COLUMNS = [
    "match_id",
    "team_a",
    "team_b",
    "prob_a",
    "prob_draw",
    "prob_b",
    "model_family",
    "published_family",
    "fallback_reason",
    "winner",
]


@dataclass(frozen=True)
class PublicationDecision:
    """The per-match decision: which families publish and why (T-05-11).

    ``baseline_published`` is always ``True`` — the baseline is the stable line and is
    never dropped. ``upgrade_published`` is ``True`` only when the gate promoted a
    candidate *and* the match is ML-eligible with an available ML probability.
    ``published_family`` records the *operationally preferred* family for the row
    (the upgrade when dual-published, else the baseline), and ``fallback_reason``
    explains any reversion to baseline-only.
    """

    match_id: str
    baseline_published: bool
    upgrade_published: bool
    published_family: str
    fallback_reason: str | None


@dataclass(frozen=True)
class DualPublication:
    """Result of building the dual-publication table for a snapshot."""

    published: pd.DataFrame
    promoted: bool
    winner: str
    summary: dict[str, Any]


def decide_publication(
    *,
    match_id: str,
    gate_promoted: bool,
    winner: str,
    ml_eligible: bool,
    has_ml_prob: bool,
) -> PublicationDecision:
    """Decide, for a single match, which model families are published and why.

    The baseline is always published (D-14). The upgrade is published alongside it only
    when *all* of the following hold: the gate promoted a candidate, the match is
    ML-eligible (D-04), and an ML probability is actually available for the row. Any
    missing precondition produces an explicit baseline-only fallback with a reason
    (T-05-11), in a fixed priority so the recorded cause is deterministic.
    """
    if not gate_promoted:
        reason = REASON_GATE_NOT_PROMOTED
    elif not ml_eligible:
        reason = REASON_ML_INELIGIBLE
    elif not has_ml_prob:
        reason = REASON_ML_PROB_UNAVAILABLE
    else:
        reason = None

    upgrade_published = reason is None
    return PublicationDecision(
        match_id=str(match_id),
        baseline_published=True,
        upgrade_published=upgrade_published,
        published_family=UPGRADE_FAMILY if upgrade_published else BASELINE_FAMILY,
        fallback_reason=reason,
    )


def _normalize_triplet(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    total = float(arr.sum())
    if total <= 0.0:
        raise ValueError(f"cannot publish a non-positive probability triplet: {arr!r}")
    return arr / total


def build_dual_publication(
    *,
    baseline_predictions: pd.DataFrame,
    gate: Mapping[str, Any],
    ml_eligible: Mapping[str, bool],
    ml_probs: Mapping[str, np.ndarray],
) -> DualPublication:
    """Build the per-match dual publication table from baseline preds + the gate verdict.

    Parameters
    ----------
    baseline_predictions
        The existing live baseline 1/X/2 table (``match_id``, ``team_a``, ``team_b``,
        ``prob_a``/``prob_draw``/``prob_b``). This is the stable operational line and is
        never mutated; every input match yields a published baseline row (D-14).
    gate
        The promotion-gate verdict from ``evaluate_ml_gate`` / ``run_ml_comparison``
        (must carry ``promoted`` and ``winner``). When ``promoted`` is ``False`` the
        whole table is baseline-only and that negative result is recorded explicitly
        (T-05-12).
    ml_eligible
        ``{match_id: bool}`` per-match ML eligibility (D-04). Matches absent from the
        map are treated as ineligible (conservative baseline fallback).
    ml_probs
        ``{match_id: [p_home, p_draw, p_away]}`` calibrated promoted-candidate
        probabilities for the eligible matches. A missing entry yields an explicit
        ``ml_probability_unavailable`` fallback.

    Returns
    -------
    DualPublication
        ``published`` is the labelled table: one baseline row per input match plus, for
        every promoted+eligible match, a second upgrade row carrying the ML probability.
        ``summary`` gives auditable counts and the fallback-reason breakdown.
    """
    required = {"match_id", "team_a", "team_b", *_PROB_COLUMNS}
    missing = required - set(baseline_predictions.columns)
    if missing:
        raise ValueError(
            f"baseline predictions are missing required columns: {sorted(missing)}"
        )

    promoted = bool(gate.get("promoted", False))
    winner = str(gate.get("winner", BASELINE_FAMILY))

    rows: list[dict[str, Any]] = []
    fallback_reasons: Counter[str] = Counter()
    n_upgrade = 0

    for pred in baseline_predictions.itertuples(index=False):
        match_id = str(pred.match_id)
        eligible = bool(ml_eligible.get(match_id, False))
        has_prob = match_id in ml_probs

        decision = decide_publication(
            match_id=match_id,
            gate_promoted=promoted,
            winner=winner,
            ml_eligible=eligible,
            has_ml_prob=has_prob,
        )

        # --- baseline row: always published, stable line, labelled with its reason ---
        rows.append(
            {
                "match_id": match_id,
                "team_a": str(pred.team_a),
                "team_b": str(pred.team_b),
                "prob_a": float(pred.prob_a),
                "prob_draw": float(pred.prob_draw),
                "prob_b": float(pred.prob_b),
                "model_family": BASELINE_FAMILY,
                "published_family": decision.published_family,
                "fallback_reason": decision.fallback_reason,
                "winner": winner,
            }
        )
        if decision.fallback_reason is not None:
            fallback_reasons[decision.fallback_reason] += 1

        # --- upgrade row: added ALONGSIDE the baseline only when truly promoted ---
        if decision.upgrade_published:
            triplet = _normalize_triplet(ml_probs[match_id])
            rows.append(
                {
                    "match_id": match_id,
                    "team_a": str(pred.team_a),
                    "team_b": str(pred.team_b),
                    "prob_a": float(triplet[0]),
                    "prob_draw": float(triplet[1]),
                    "prob_b": float(triplet[2]),
                    "model_family": UPGRADE_FAMILY,
                    "published_family": UPGRADE_FAMILY,
                    "fallback_reason": None,
                    "winner": winner,
                }
            )
            n_upgrade += 1

    published = pd.DataFrame(rows, columns=_PUBLISH_COLUMNS)
    n_baseline = int((published["model_family"] == BASELINE_FAMILY).sum())

    summary = {
        "promoted": promoted,
        "winner": winner,
        "n_input_matches": int(len(baseline_predictions)),
        "n_baseline_published": n_baseline,
        "n_upgrade_published": int(n_upgrade),
        "n_baseline_fallback": int(sum(fallback_reasons.values())),
        "fallback_reasons": dict(fallback_reasons),
        "gate_mean_log_loss": dict(gate.get("mean_log_loss", {})),
    }
    return DualPublication(
        published=published.reset_index(drop=True),
        promoted=promoted,
        winner=winner,
        summary=summary,
    )


__all__ = [
    "BASELINE_FAMILY",
    "UPGRADE_FAMILY",
    "REASON_GATE_NOT_PROMOTED",
    "REASON_ML_INELIGIBLE",
    "REASON_ML_PROB_UNAVAILABLE",
    "PublicationDecision",
    "DualPublication",
    "decide_publication",
    "build_dual_publication",
]
