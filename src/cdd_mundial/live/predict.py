"""Deterministic per-match prediction tables for the official snapshot (LIVE-02).

The official run publishes two team-facing artifacts derived from the simulation
result plus the persisted production model:

* the per-team advancement / champion table (from
  :func:`cdd_mundial.simulation.outputs.advancement_table`), and
* an upcoming-match 1/X/2 table for the next block of still-unresolved fixtures,
  built here against the frozen ``UpcomingPredictionsSchema`` contract using the
  same Dixon-Coles ``predict_lambdas`` surface the simulation uses.

Predictions are computed only after the materialized training artifact and model
provenance are resolved, so they are reproducible from the snapshot metadata.
"""

from __future__ import annotations

import pandas as pd

from cdd_mundial.live.contracts import UpcomingPredictionsSchema
from cdd_mundial.models.dixon_coles import wdl_from_lambdas

_DEFAULT_CTX = {
    "neutral": True,
    "date": None,
    "tournament_type": "FIFA World Cup",
}


def upcoming_match_predictions(
    fixture: pd.DataFrame,
    *,
    state,
    model,
    rho: float | None = None,
    ctx: dict | None = None,
) -> pd.DataFrame:
    """1/X/2 probabilities for the next block of unresolved group fixtures.

    ``state`` is the played-results :class:`TournamentState`; matches already in
    it are excluded (they are resolved). Only group-stage matches with both
    participants assigned are predicted here, because knockout participants are
    not yet known pre-bracket. ``model`` honours the frozen
    ``predict_lambdas(team_a, team_b, ctx)`` contract; ``rho`` defaults to the
    model's fitted low-score correction.
    """
    ctx = dict(_DEFAULT_CTX) if ctx is None else dict(ctx)
    rho = float(getattr(model, "rho", 0.0)) if rho is None else float(rho)
    played = set(state.played)

    group_rows = fixture[fixture["stage"] == "group"]
    rows: list[dict[str, object]] = []
    for row in group_rows.itertuples(index=False):
        if row.match_id in played:
            continue
        if pd.isna(row.home_team_id) or pd.isna(row.away_team_id):
            continue
        lam_a, lam_b = model.predict_lambdas(
            str(row.home_team_id), str(row.away_team_id), ctx
        )
        p_a, p_draw, p_b = wdl_from_lambdas(lam_a, lam_b, rho)
        rows.append(
            {
                "match_id": str(row.match_id),
                "team_a": str(row.home_team_id),
                "team_b": str(row.away_team_id),
                "prob_a": float(p_a),
                "prob_draw": float(p_draw),
                "prob_b": float(p_b),
            }
        )

    frame = pd.DataFrame(
        rows,
        columns=["match_id", "team_a", "team_b", "prob_a", "prob_draw", "prob_b"],
    )
    if frame.empty:
        return frame
    return UpcomingPredictionsSchema.validate(frame).reset_index(drop=True)


__all__ = ["upcoming_match_predictions"]
