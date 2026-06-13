"""Strict dataframe contracts for the Phase 4 live publication layer.

This module freezes the canonical interface for the official daily run so that
later Phase 4 plans (prediction tables, frozen market benchmark, calibration
ledger) implement against a fixed surface without re-touching contracts.

Every schema inherits ``strict = True`` / ``coerce = True`` from the shared
Phase 1 ``CanonicalSchema`` base, matching the established repo convention of a
single source of truth for canonical stage-exit validation.

``LiveResultsSchema`` mirrors the played-results contract enforced by
``cdd_mundial.simulation.state`` (``match_id``, ``team_a``/``team_b``,
``goals_*`` >= 0, optional ``fair_play_*`` <= 0 conduct deductions, optional
``advanced_team``) and nothing operational (D-03).
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.typing.pandas import Series

from cdd_mundial.data.contracts import CanonicalSchema


class LiveResultsSchema(CanonicalSchema):
    """Canonical ``results_2026.csv`` contract: only what ``TournamentState`` needs.

    No operational metadata columns (timestamps, sources, scraper notes) are
    permitted; those live in separate artifacts per D-03. ``strict = True``
    rejects any extra column, and ``coerce = True`` parses CSV strings into the
    declared dtypes.
    """

    match_id: Series[str] = pa.Field(unique=True)
    team_a: Series[str]
    team_b: Series[str]
    goals_a: Series[int] = pa.Field(ge=0)
    goals_b: Series[int] = pa.Field(ge=0)
    fair_play_a: Series[float] = pa.Field(nullable=True, le=0)
    fair_play_b: Series[float] = pa.Field(nullable=True, le=0)
    advanced_team: Series[str] = pa.Field(nullable=True)

    @pa.dataframe_check
    def teams_are_distinct(cls, frame: pd.DataFrame) -> Series[bool]:
        return frame["team_a"] != frame["team_b"]


class UpcomingPredictionsSchema(CanonicalSchema):
    """Per-match 1/X/2 predictions for the next block of unresolved fixtures.

    Probabilities use the frozen Phase 2 ``team_a``/``team_b`` convention and
    must sum to one within numerical tolerance.
    """

    match_id: Series[str] = pa.Field(unique=True)
    team_a: Series[str]
    team_b: Series[str]
    prob_a: Series[float] = pa.Field(ge=0, le=1)
    prob_draw: Series[float] = pa.Field(ge=0, le=1)
    prob_b: Series[float] = pa.Field(ge=0, le=1)

    @pa.dataframe_check
    def probabilities_are_normalized(cls, frame: pd.DataFrame) -> Series[bool]:
        total = frame["prob_a"] + frame["prob_draw"] + frame["prob_b"]
        return (total - 1.0).abs() <= 1e-9


class FrozenBenchmarkSchema(CanonicalSchema):
    """Market benchmark frozen at the moment the official snapshot is published (D-21).

    ``captured_at_utc`` records the freeze instant; de-margined probabilities are
    the median across valid bookmakers (D-20) and must be normalized.
    """

    match_id: Series[str] = pa.Field(unique=True)
    captured_at_utc: Series[str] = pa.Field(str_matches=r".*Z$")
    prob_home: Series[float] = pa.Field(ge=0, le=1)
    prob_draw: Series[float] = pa.Field(ge=0, le=1)
    prob_away: Series[float] = pa.Field(ge=0, le=1)

    @pa.dataframe_check
    def probabilities_are_normalized(cls, frame: pd.DataFrame) -> Series[bool]:
        total = frame["prob_home"] + frame["prob_draw"] + frame["prob_away"]
        return (total - 1.0).abs() <= 1e-9


class CalibrationLedgerSchema(CanonicalSchema):
    """Per-match calibration ledger row (D-18): one canonical record per resolved match.

    Aggregated per-jornada views are derived downstream; the canonical unit is
    the match. ``outcome_idx`` follows the project convention 0=home/team_a win,
    1=draw, 2=away/team_b win.
    """

    match_id: Series[str]
    snapshot_id: Series[str]
    model_version: Series[str]
    prob_a: Series[float] = pa.Field(ge=0, le=1)
    prob_draw: Series[float] = pa.Field(ge=0, le=1)
    prob_b: Series[float] = pa.Field(ge=0, le=1)
    outcome_idx: Series[int] = pa.Field(isin=[0, 1, 2])

    @pa.dataframe_check
    def probabilities_are_normalized(cls, frame: pd.DataFrame) -> Series[bool]:
        total = frame["prob_a"] + frame["prob_draw"] + frame["prob_b"]
        return (total - 1.0).abs() <= 1e-9
