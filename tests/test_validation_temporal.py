"""Temporal validation harness tests: holdout selection, D-13 gate logic, strict cutoffs."""

from pathlib import Path
import datetime as dt

import pandas as pd
import pytest

from cdd_mundial.models import predict_lambdas
from cdd_mundial.models.dixon_coles import load_production_model
from cdd_mundial.models.loading import load_matches
from cdd_mundial.models.validation import (
    HOLDOUTS,
    XI_GRID,
    Holdout,
    evaluate_gate,
    verify_model04_materialization,
    select_holdout,
)


def _synthetic_frame() -> pd.DataFrame:
    rows = [
        ("m1", "2018-06-14", "FIFA World Cup"),
        ("m2", "2018-07-15", "FIFA World Cup"),
        ("m3", "2022-11-20", "FIFA World Cup"),
        ("m4", "2024-06-20", "Copa América"),
        ("m5", "2024-06-25", "Copa América"),
        ("m6", "2024-03-23", "Copa América qualification"),
        ("m7", "2018-06-14", "Friendly"),
    ]
    frame = pd.DataFrame(rows, columns=["match_id", "date", "tournament"])
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_xi_grid_matches_director_mini_grid() -> None:
    assert XI_GRID == (0.00095, 0.0018)


def test_select_holdout_uses_exact_string_and_year() -> None:
    frame = _synthetic_frame()

    selected = select_holdout(frame, Holdout("FIFA World Cup", "2018-06-14", 2018, 2))
    assert list(selected["match_id"]) == ["m1", "m2"]

    # Igualdad EXACTA de string: excluye "Copa América qualification" (pitfall 5).
    copa = select_holdout(frame, Holdout("Copa América", "2024-06-20", 2024, 2))
    assert list(copa["match_id"]) == ["m4", "m5"]


def test_select_holdout_fails_loudly_on_count_mismatch() -> None:
    frame = _synthetic_frame()

    with pytest.raises(ValueError, match="expected 5 matches, got 2"):
        select_holdout(frame, Holdout("FIFA World Cup", "2018-06-14", 2018, 5))


def test_gate_logic_with_synthetic_metrics() -> None:
    passing = evaluate_gate({"dixon_coles": 0.95, "uniform": 1.10, "solo_elo": 1.02})
    assert passing["passed"] is True

    failing = evaluate_gate({"dixon_coles": 1.05, "uniform": 1.10, "solo_elo": 1.02})
    assert failing["passed"] is False
    assert "uniform" in failing["criterion"]
    assert "solo_elo" in failing["criterion"]


@pytest.mark.data_acceptance
def test_holdout_counts_are_exact_on_real_history() -> None:
    matches = load_matches(path=Path("data/processed/historical_matches.parquet"))

    counts = {name: len(select_holdout(matches, holdout)) for name, holdout in HOLDOUTS.items()}
    assert counts == {"wc2018": 64, "wc2022": 64, "euro2024": 51, "copa2024": 32}


@pytest.mark.data_acceptance
def test_training_cut_is_strict_for_every_holdout() -> None:
    matches = load_matches(path=Path("data/processed/historical_matches.parquet"))

    for holdout in HOLDOUTS.values():
        cutoff = pd.Timestamp(holdout.start)
        train = matches[matches["date"] < cutoff]
        assert train["date"].max() < cutoff
        holdout_frame = select_holdout(matches, holdout)
        assert holdout_frame["date"].min() >= cutoff


@pytest.mark.data_acceptance
def test_model04_artifacts_verify_cleanly() -> None:
    summary = verify_model04_materialization(Path("data"))
    assert isinstance(summary["gate_passed"], bool)
    assert summary["prediction_rows"] == 3 * (64 + 64 + 51 + 32)


@pytest.mark.data_acceptance
def test_validation_report_covers_all_holdouts_and_models() -> None:
    summary = verify_model04_materialization(Path("data"))
    report = pd.read_json(summary["report_path"], typ="series")
    assert set(report["per_holdout"].keys()) == set(HOLDOUTS)
    for holdout_metrics in report["per_holdout"].values():
        assert set(holdout_metrics["metrics"]) == {"dixon_coles", "uniform", "solo_elo"}
        for metrics in holdout_metrics["metrics"].values():
            assert set(metrics) == {"log_loss", "brier", "rps"}


@pytest.mark.data_acceptance
def test_production_model_contract_is_live() -> None:
    model = load_production_model()
    lam, mu = model.predict_lambdas(
        "argentina",
        "mexico",
        {
            "neutral": True,
            "date": dt.datetime(2026, 6, 15),
            "tournament_type": "FIFA World Cup",
        },
    )
    assert 0.1 < lam < 6.0
    assert 0.1 < mu < 6.0

    live_lam, live_mu = predict_lambdas(
        "argentina",
        "mexico",
        {
            "neutral": True,
            "date": dt.datetime(2026, 6, 15),
            "tournament_type": "FIFA World Cup",
        },
    )
    assert 0.1 < live_lam < 6.0
    assert 0.1 < live_mu < 6.0
