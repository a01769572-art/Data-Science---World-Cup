"""Phase 4 live-input contract and fail-closed results-loading invariants (DATA-06, LIVE-01).

These tests freeze the canonical interface for the official daily run before any
pipeline orchestration exists:

* ``LiveResultsSchema`` is the strict/coercing contract for ``results_2026.csv``.
* The downstream publication schemas (upcoming predictions, frozen benchmark,
  calibration ledger) are frozen here so later Phase 4 plans implement against a
  fixed surface without re-touching contracts.
* The loader (``load_live_results`` / ``build_live_state``) must end in
  ``TournamentState.from_results(...)`` and fail closed on duplicate rows,
  out-of-fixture matches, missing columns, incomplete played-match coverage,
  and silent scraper-assist overrides.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from cdd_mundial.data.identities import UnknownTeamError
from cdd_mundial.live.contracts import (
    CalibrationLedgerSchema,
    FrozenBenchmarkSchema,
    LiveResultsSchema,
    UpcomingPredictionsSchema,
)
from cdd_mundial.live.results import (
    CANONICAL_RESULTS_PATH,
    LIVE_RESULTS_COLUMNS,
    DiscrepancyError,
    IncompleteResultsError,
    OverrideToken,
    build_live_state,
    load_live_results,
)
from cdd_mundial.simulation.state import TournamentState

RESULTS_PATH = Path("data/external/results_2026.csv")


# --- Mini fixtures (table-driven, fixture-backed) ---


def mini_fixture() -> pd.DataFrame:
    """Two played group matches plus one open knockout slot."""
    return pd.DataFrame(
        [
            {
                "match_id": "WC26-001",
                "stage": "group",
                "home_team_id": "mexico",
                "away_team_id": "south-africa",
                "kickoff_utc": "2026-06-11T19:00:00Z",
            },
            {
                "match_id": "WC26-002",
                "stage": "group",
                "home_team_id": "south-korea",
                "away_team_id": "czechia",
                "kickoff_utc": "2026-06-12T02:00:00Z",
            },
            {
                "match_id": "WC26-073",
                "stage": "round_of_32",
                "home_team_id": None,
                "away_team_id": None,
                "kickoff_utc": "2026-07-01T19:00:00Z",
            },
        ]
    )


def results_frame(rows: list[dict] | None = None) -> pd.DataFrame:
    """Canonical results frame with the two played group matches by default."""
    rows = rows if rows is not None else [
        {
            "match_id": "WC26-001",
            "team_a": "mexico",
            "team_b": "south-africa",
            "goals_a": 2,
            "goals_b": 1,
            "fair_play_a": None,
            "fair_play_b": None,
            "advanced_team": None,
        },
        {
            "match_id": "WC26-002",
            "team_a": "south-korea",
            "team_b": "czechia",
            "goals_a": 0,
            "goals_b": 0,
            "fair_play_a": None,
            "fair_play_b": None,
            "advanced_team": None,
        },
    ]
    return pd.DataFrame(rows, columns=list(LIVE_RESULTS_COLUMNS))


def write_results_csv(path: Path, frame: pd.DataFrame) -> Path:
    frame.to_csv(path, index=False)
    return path


# --- Canonical CSV shape: minimal, no operational metadata (D-03) ---


def test_canonical_results_csv_exists_with_minimal_columns() -> None:
    assert RESULTS_PATH.exists(), "canonical results_2026.csv must be versioned"
    frame = pd.read_csv(RESULTS_PATH)
    assert list(frame.columns) == list(LIVE_RESULTS_COLUMNS)


def test_canonical_results_columns_carry_no_operational_metadata() -> None:
    # D-03: only what TournamentState needs. No timestamps, sources, notes, etc.
    forbidden = {"captured_at_utc", "source", "scraper", "note", "updated_at", "provider"}
    assert forbidden.isdisjoint(set(LIVE_RESULTS_COLUMNS))
    assert set(LIVE_RESULTS_COLUMNS) == {
        "match_id",
        "team_a",
        "team_b",
        "goals_a",
        "goals_b",
        "fair_play_a",
        "fair_play_b",
        "advanced_team",
    }


def test_canonical_results_path_constant_points_at_versioned_file() -> None:
    assert CANONICAL_RESULTS_PATH == RESULTS_PATH


# --- LiveResultsSchema: strict and coercing (T-04-01) ---


def test_live_results_schema_is_strict_and_coercing() -> None:
    assert LiveResultsSchema.Config.strict is True
    assert LiveResultsSchema.Config.coerce is True


def test_live_results_schema_accepts_canonical_frame() -> None:
    validated = LiveResultsSchema.validate(results_frame())
    assert list(validated["match_id"]) == ["WC26-001", "WC26-002"]


def test_live_results_schema_rejects_extra_metadata_column() -> None:
    frame = results_frame()
    frame["captured_at_utc"] = "2026-06-13T00:00:00Z"
    with pytest.raises(pa.errors.SchemaError):
        LiveResultsSchema.validate(frame)


def test_live_results_schema_rejects_negative_goals() -> None:
    frame = results_frame()
    frame.loc[0, "goals_a"] = -1
    with pytest.raises(pa.errors.SchemaError):
        LiveResultsSchema.validate(frame)


def test_live_results_schema_rejects_positive_fair_play() -> None:
    # Art. 13 conduct scores are deductions (<= 0).
    frame = results_frame()
    frame.loc[0, "fair_play_a"] = 2
    with pytest.raises(pa.errors.SchemaError):
        LiveResultsSchema.validate(frame)


def test_live_results_schema_rejects_duplicate_match_id() -> None:
    frame = results_frame()
    dup = frame.iloc[[0]].copy()
    frame = pd.concat([frame, dup], ignore_index=True)
    with pytest.raises(pa.errors.SchemaError):
        LiveResultsSchema.validate(frame)


# --- Downstream publication schemas are frozen here (interface stability) ---


def test_downstream_publication_schemas_are_strict_and_coercing() -> None:
    for schema in (
        UpcomingPredictionsSchema,
        FrozenBenchmarkSchema,
        CalibrationLedgerSchema,
    ):
        assert schema.Config.strict is True
        assert schema.Config.coerce is True


def test_upcoming_predictions_schema_requires_normalized_probabilities() -> None:
    good = pd.DataFrame(
        [
            {
                "match_id": "WC26-010",
                "team_a": "brazil",
                "team_b": "serbia",
                "prob_a": 0.5,
                "prob_draw": 0.3,
                "prob_b": 0.2,
            }
        ]
    )
    UpcomingPredictionsSchema.validate(good)

    bad = good.copy()
    bad.loc[0, "prob_a"] = 0.9
    with pytest.raises(pa.errors.SchemaError):
        UpcomingPredictionsSchema.validate(bad)


def test_frozen_benchmark_schema_requires_normalized_probabilities() -> None:
    bad = pd.DataFrame(
        [
            {
                "match_id": "WC26-010",
                "captured_at_utc": "2026-06-13T00:00:00Z",
                "prob_home": 0.7,
                "prob_draw": 0.7,
                "prob_away": 0.7,
            }
        ]
    )
    with pytest.raises(pa.errors.SchemaError):
        FrozenBenchmarkSchema.validate(bad)


def test_calibration_ledger_schema_constrains_outcome_index() -> None:
    bad = pd.DataFrame(
        [
            {
                "match_id": "WC26-001",
                "snapshot_id": "2026-06-13T000000Z",
                "model_version": "baseline-v1-2026-06-13-abc1234",
                "prob_a": 0.5,
                "prob_draw": 0.3,
                "prob_b": 0.2,
                "outcome_idx": 5,
            }
        ]
    )
    with pytest.raises(pa.errors.SchemaError):
        CalibrationLedgerSchema.validate(bad)


# --- Loader: fail-closed path ending in TournamentState.from_results (Task 2) ---


def test_load_live_results_returns_validated_played_records(test_workspace: Path) -> None:
    path = write_results_csv(test_workspace / "results.csv", results_frame())
    records = load_live_results(path)
    assert {r.match_id for r in records} == {"WC26-001", "WC26-002"}
    assert records[0].goals_a == 2


def test_build_live_state_constructs_tournament_state_from_canonical_csv(
    test_workspace: Path,
) -> None:
    path = write_results_csv(test_workspace / "results.csv", results_frame())
    state = build_live_state(path, fixture=mini_fixture())
    assert isinstance(state, TournamentState)
    assert set(state.played) == {"WC26-001", "WC26-002"}


def test_build_live_state_rejects_out_of_fixture_match(test_workspace: Path) -> None:
    rows = results_frame().to_dict("records")
    rows.append(
        {
            "match_id": "WC26-999",
            "team_a": "brazil",
            "team_b": "serbia",
            "goals_a": 1,
            "goals_b": 0,
            "fair_play_a": None,
            "fair_play_b": None,
            "advanced_team": None,
        }
    )
    path = write_results_csv(test_workspace / "results.csv", pd.DataFrame(rows, columns=list(LIVE_RESULTS_COLUMNS)))
    with pytest.raises(ValueError, match="WC26-999"):
        build_live_state(path, fixture=mini_fixture())


def test_build_live_state_rejects_unknown_team(test_workspace: Path) -> None:
    rows = [
        {
            "match_id": "WC26-001",
            "team_a": "atlantis",
            "team_b": "south-africa",
            "goals_a": 1,
            "goals_b": 0,
            "fair_play_a": None,
            "fair_play_b": None,
            "advanced_team": None,
        }
    ]
    path = write_results_csv(test_workspace / "results.csv", pd.DataFrame(rows, columns=list(LIVE_RESULTS_COLUMNS)))
    with pytest.raises(UnknownTeamError, match="atlantis"):
        build_live_state(path, fixture=mini_fixture())


def test_build_live_state_rejects_missing_required_column(test_workspace: Path) -> None:
    frame = results_frame().drop(columns=["goals_a"])
    path = write_results_csv(test_workspace / "results.csv", frame)
    with pytest.raises((ValueError, pa.errors.SchemaError)):
        build_live_state(path, fixture=mini_fixture())


# --- Completeness gate: incomplete already-played matches fail closed (D-05) ---


def test_incomplete_played_coverage_fails_closed(test_workspace: Path) -> None:
    # WC26-002 has already kicked off (relative to as_of) but is absent from the CSV.
    one_row = results_frame(
        [
            {
                "match_id": "WC26-001",
                "team_a": "mexico",
                "team_b": "south-africa",
                "goals_a": 2,
                "goals_b": 1,
                "fair_play_a": None,
                "fair_play_b": None,
                "advanced_team": None,
            }
        ]
    )
    path = write_results_csv(test_workspace / "results.csv", one_row)
    with pytest.raises(IncompleteResultsError, match="WC26-002"):
        build_live_state(
            path,
            fixture=mini_fixture(),
            as_of="2026-06-13T00:00:00Z",
        )


def test_incomplete_coverage_can_continue_with_traceable_override(
    test_workspace: Path,
) -> None:
    one_row = results_frame(
        [
            {
                "match_id": "WC26-001",
                "team_a": "mexico",
                "team_b": "south-africa",
                "goals_a": 2,
                "goals_b": 1,
                "fair_play_a": None,
                "fair_play_b": None,
                "advanced_team": None,
            }
        ]
    )
    path = write_results_csv(test_workspace / "results.csv", one_row)
    override = OverrideToken(
        reason="WC26-002 postponed; awaiting official confirmation",
        allow_missing=("WC26-002",),
    )
    state = build_live_state(
        path,
        fixture=mini_fixture(),
        as_of="2026-06-13T00:00:00Z",
        override=override,
    )
    assert set(state.played) == {"WC26-001"}
    # The override must leave a traceable record for later snapshot metadata.
    assert "WC26-002" in override.missing_matches
    assert override.reason


def test_override_only_excuses_listed_missing_matches(test_workspace: Path) -> None:
    empty = results_frame([])
    path = write_results_csv(test_workspace / "results.csv", empty)
    override = OverrideToken(
        reason="only excusing WC26-002",
        allow_missing=("WC26-002",),
    )
    # WC26-001 is still missing and not excused -> fail closed.
    with pytest.raises(IncompleteResultsError, match="WC26-001"):
        build_live_state(
            path,
            fixture=mini_fixture(),
            as_of="2026-06-13T00:00:00Z",
            override=override,
        )


# --- Scraper-assist comparison: verification only, never silent override (D-04) ---


def test_scraper_assist_agreement_passes(test_workspace: Path) -> None:
    path = write_results_csv(test_workspace / "results.csv", results_frame())
    assist = results_frame()  # identical scores -> no discrepancy
    state = build_live_state(path, fixture=mini_fixture(), scraper_assist=assist)
    assert set(state.played) == {"WC26-001", "WC26-002"}


def test_scraper_assist_discrepancy_fails_closed(test_workspace: Path) -> None:
    path = write_results_csv(test_workspace / "results.csv", results_frame())
    assist = results_frame()
    assist.loc[0, "goals_a"] = 5  # disagrees with the canonical CSV
    with pytest.raises(DiscrepancyError, match="WC26-001"):
        build_live_state(path, fixture=mini_fixture(), scraper_assist=assist)


def test_scraper_assist_never_overrides_canonical_scores(test_workspace: Path) -> None:
    path = write_results_csv(test_workspace / "results.csv", results_frame())
    assist = results_frame()
    assist.loc[0, "goals_a"] = 9
    # Even when forced through, the canonical CSV value wins; assist cannot rewrite it.
    override = OverrideToken(reason="accept canonical despite assist", allow_discrepancies=True)
    state = build_live_state(
        path, fixture=mini_fixture(), scraper_assist=assist, override=override
    )
    assert state.played["WC26-001"].goals_a == 2  # canonical, not 9
    assert override.discrepancies  # traceable record retained


# --- Real canonical artifact round-trips against the official fixture ---


def test_official_results_csv_builds_state_against_real_fixture() -> None:
    from cdd_mundial.data.ingest_fixture import load_fixture_2026

    state = build_live_state(
        CANONICAL_RESULTS_PATH,
        fixture=load_fixture_2026(),
        as_of="2026-06-13T00:00:00Z",
    )
    assert set(state.played) >= {"WC26-001", "WC26-002", "WC26-003"}
