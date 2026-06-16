"""ML v1 point-in-time feature builder tests (Phase 5, ML-01).

These tests freeze the data contract BEFORE any modeling code exists:

* strict ``date < kickoff`` rolling-feature generation (no look-ahead, T-05-01),
* the exact fixed 12-feature column set from D-02,
* ``last_5`` window semantics for form/goal rollings (D-03, D-06, D-07),
* natural units only -- no normalization/scaling (D-05),
* every row is retained for auditability but marked ML-ineligible when either
  team has fewer than five prior matches (D-04, T-05-02).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cdd_mundial.models.ml_features import (
    ML_FEATURE_COLUMNS,
    MIN_PRIOR_MATCHES,
    build_ml_dataset,
)


# The frozen 12-feature contract (D-02). Encoded here as the authoritative
# membership test so a silent rename/add/drop in the builder fails loudly.
EXPECTED_FEATURES = (
    "elo_diff",
    "is_host_home",
    "days_rest_diff",
    "form_points_diff_last_5",
    "goal_diff_per_match_diff_last_5",
    "goals_for_per_match_diff_last_5",
    "goals_against_per_match_diff_last_5",
    "lambda_home_dc",
    "lambda_away_dc",
    "p_home_win_dc",
    "p_draw_dc",
    "p_away_win_dc",
)


def _toy_history() -> pd.DataFrame:
    """A small two-team league plus a third team, fully deterministic.

    ``home`` and ``away`` accumulate a long head-to-head series so that by the
    final scored match both have >=5 prior matches; ``newbie`` only appears once
    at the end so its match must be ML-ineligible under D-04.
    """
    rows = []
    base = pd.Timestamp("2020-01-01")
    # 6 prior home-vs-away matches (alternating venues) before the target match.
    scripted = [
        ("home", "away", 2, 0),
        ("away", "home", 1, 1),
        ("home", "away", 3, 1),
        ("away", "home", 0, 2),
        ("home", "away", 1, 0),
        ("away", "home", 2, 2),
    ]
    def _row(match_id, day, h, a, hs, as_, neutral):
        # Emit every canonical column so the builder's internal load_matches
        # validation (strict schema) passes on this synthetic frame.
        return {
            "match_id": match_id,
            "date": (base + pd.Timedelta(days=day)).strftime("%Y-%m-%d"),
            "home_team_id": h,
            "away_team_id": a,
            "home_team_source_name": h,
            "away_team_source_name": a,
            "home_score": hs,
            "away_score": as_,
            "tournament": "Friendly",
            "city": "Testville",
            "country": "TST",
            "neutral": neutral,
            "shootout_winner_team_id": None,
            "result_after_extra_time": False,
            "source": "synthetic",
            "source_version": "test-1",
        }

    for i, (h, a, hs, as_) in enumerate(scripted):
        rows.append(_row(f"m{i}", 30 * i, h, a, hs, as_, False))
    # Target match: home vs away, both now have 6 priors -> ML-eligible.
    rows.append(_row("target_eligible", 400, "home", "away", 2, 1, False))
    # Target match involving a brand-new team -> ML-ineligible (newbie 0 priors).
    rows.append(_row("target_newbie", 410, "home", "newbie", 0, 0, True))
    return pd.DataFrame(rows)


def _stub_dc_predict(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    """Deterministic Dixon-Coles stand-in so tests never need a fitted artifact."""
    return (1.5, 1.1)


def _build(history: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = history if history is not None else _toy_history()
    return build_ml_dataset(frame=frame, dc_predict=_stub_dc_predict)


def test_feature_column_set_is_exactly_the_frozen_twelve() -> None:
    assert tuple(ML_FEATURE_COLUMNS) == EXPECTED_FEATURES
    assert len(ML_FEATURE_COLUMNS) == 12


def test_builder_emits_every_frozen_feature_column() -> None:
    dataset = _build()
    for column in EXPECTED_FEATURES:
        assert column in dataset.columns


def test_builder_preserves_target_and_join_keys() -> None:
    dataset = _build()
    for column in ("match_id", "date", "home_team_id", "away_team_id", "target_outcome_idx"):
        assert column in dataset.columns
    # outcome_idx semantics preserved: home_win=0 for the 2-1 eligible target.
    target = dataset.loc[dataset["match_id"] == "target_eligible"].iloc[0]
    assert int(target["target_outcome_idx"]) == 0


def test_every_row_retained_but_eligibility_flagged() -> None:
    dataset = _build()
    # No silent drops: all input rows survive (D-04 -> audited, not removed).
    assert len(dataset) == len(_toy_history())
    assert "ml_eligible" in dataset.columns
    assert "has_min_history_home" in dataset.columns
    assert "has_min_history_away" in dataset.columns

    eligible = dataset.loc[dataset["match_id"] == "target_eligible"].iloc[0]
    assert bool(eligible["ml_eligible"]) is True

    newbie = dataset.loc[dataset["match_id"] == "target_newbie"].iloc[0]
    assert bool(newbie["ml_eligible"]) is False
    assert bool(newbie["has_min_history_away"]) is False


def test_min_prior_matches_is_five() -> None:
    assert MIN_PRIOR_MATCHES == 5


def test_rolling_features_use_only_strictly_prior_matches() -> None:
    """No look-ahead: the target's own result must not enter its rolling window."""
    dataset = _build()
    target = dataset.loc[dataset["match_id"] == "target_eligible"].iloc[0]

    # Appearances of "home": m0 H 2-0 W, m1 A 1-1 D, m2 H 3-1 W, m3 A 0-2 W,
    #   m4 H 1-0 W, m5 A 2-2 D  -> last 5 = m1..m5 = D,W,W,W,D = 1+3+3+3+1=11 /5
    home_ppm = (1 + 3 + 3 + 3 + 1) / 5
    # away's last 5: m1 H 1-1 D, m2 A 3-1 L, m3 H 0-2 L, m4 A 1-0 L, m5 H 2-2 D
    #   = 1+0+0+0+1=2 /5
    away_ppm = (1 + 0 + 0 + 0 + 1) / 5
    expected_form_diff = home_ppm - away_ppm
    assert target["form_points_diff_last_5"] == pytest.approx(expected_form_diff)


def test_features_are_not_normalized() -> None:
    """Natural units only (D-05): probabilities sum ~1, lambdas untouched."""
    dataset = _build()
    eligible = dataset.loc[dataset["ml_eligible"]].copy()
    p_sum = (
        eligible["p_home_win_dc"]
        + eligible["p_draw_dc"]
        + eligible["p_away_win_dc"]
    )
    assert np.allclose(p_sum.to_numpy(dtype=float), 1.0, atol=1e-6)
    # lambdas are the raw stubbed expected goals, untouched by any scaler.
    assert eligible["lambda_home_dc"].iloc[0] == pytest.approx(1.5)
    assert eligible["lambda_away_dc"].iloc[0] == pytest.approx(1.1)


def test_is_host_home_reflects_real_home_advantage() -> None:
    dataset = _build()
    # Eligible target is a non-neutral home match -> host_home = 1.
    eligible = dataset.loc[dataset["match_id"] == "target_eligible"].iloc[0]
    assert int(eligible["is_host_home"]) == 1
    # Newbie target is neutral -> host_home = 0.
    newbie = dataset.loc[dataset["match_id"] == "target_newbie"].iloc[0]
    assert int(newbie["is_host_home"]) == 0


# --- Task 2: one builder, two sources (historical parquet vs live frame) ---


def test_public_builder_is_exported_from_models_package() -> None:
    """Later plans import the builder from the package, not the private module."""
    from cdd_mundial.models import build_ml_dataset as exported
    from cdd_mundial.models import ML_FEATURE_COLUMNS as exported_cols

    assert exported is build_ml_dataset
    assert tuple(exported_cols) == EXPECTED_FEATURES


def test_path_and_frame_sources_yield_identical_contract(test_workspace) -> None:
    """The source switch (disk parquet vs passed-in frame) must not alter output.

    This is the live-vs-backtest guarantee: ``materialize_live_training`` hands a
    dated frame, backtests read the canonical parquet, and both must flow through
    one feature path with identical column semantics and values.

    Uses the workspace-local fixture (not ``tmp_path``) because the OS temp dir's
    ACLs are unreliable on this OneDrive Windows checkout.
    """
    history = _toy_history()
    parquet_path = test_workspace / "history.parquet"
    history.to_parquet(parquet_path, index=False)

    from_frame = build_ml_dataset(frame=history, dc_predict=_stub_dc_predict)
    from_path = build_ml_dataset(path=parquet_path, dc_predict=_stub_dc_predict)

    # Identical columns (contract) and identical values (semantics).
    assert list(from_frame.columns) == list(from_path.columns)
    pd.testing.assert_frame_equal(
        from_frame.reset_index(drop=True),
        from_path.reset_index(drop=True),
    )


def test_elo_history_injection_populates_elo_diff() -> None:
    """A live-training caller can supply pre-match Elo without changing the contract."""
    history = _toy_history()
    elo_rows = []
    for row in history.itertuples(index=False):
        elo_rows.append({"match_id": row.match_id, "team_id": row.home_team_id, "rating_pre": 1500.0})
        elo_rows.append({"match_id": row.match_id, "team_id": row.away_team_id, "rating_pre": 1400.0})
    elo_history = pd.DataFrame(elo_rows)

    dataset = build_ml_dataset(
        frame=history, elo_history=elo_history, dc_predict=_stub_dc_predict
    )
    # Same 12-feature contract regardless of the Elo source switch.
    for column in EXPECTED_FEATURES:
        assert column in dataset.columns
    # Non-neutral home match: 1500 + 100 host bonus - 1400 = 200.
    eligible = dataset.loc[dataset["match_id"] == "target_eligible"].iloc[0]
    assert eligible["elo_diff"] == pytest.approx(200.0)
    # Neutral match: no host bonus -> 1500 - 1400 = 100.
    newbie = dataset.loc[dataset["match_id"] == "target_newbie"].iloc[0]
    assert newbie["elo_diff"] == pytest.approx(100.0)
