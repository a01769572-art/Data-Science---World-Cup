from pathlib import Path
import json

import pandas as pd
import pandera.pandas as pa
import pytest

from cdd_mundial.data.contracts import FixtureSchema
from cdd_mundial.data.ingest_fixture import (
    FIXTURE_COLUMNS,
    load_fixture_2026,
    validate_fixture_structure,
)
from cdd_mundial.data.provenance import file_sha256


FIXTURE_PATH = Path("data/external/fixture_2026.csv")
SAMPLE_PATH = Path("tests/fixtures/fixture/fixture_2026_sample.csv")


def test_sample_fixture_preserves_group_ids_and_knockout_slots() -> None:
    sample = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=True)
    validated = FixtureSchema.validate(sample[FIXTURE_COLUMNS])

    group = validated.loc[validated["stage"] == "group"].iloc[0]
    assert group["home_team_id"] == "mexico"
    assert group["away_team_id"] == "south-africa"

    knockout = validated.loc[validated["stage"] == "round_of_32"].iloc[0]
    assert knockout["home_slot"] == "2A"
    assert knockout["away_slot"] == "2B"
    assert pd.isna(knockout["home_team_id"])
    assert pd.isna(knockout["away_team_id"])


def test_full_fixture_has_complete_canonical_structure() -> None:
    fixture = load_fixture_2026(FIXTURE_PATH)
    group = fixture[fixture["stage"] == "group"]
    knockout = fixture[fixture["stage"] != "group"]

    assert len(fixture) == 104
    assert fixture["match_id"].is_unique
    assert len(group) == 72
    assert group.groupby("group", observed=True).size().eq(6).all()
    assert group[["home_team_id", "away_team_id"]].notna().all().all()
    assert fixture["kickoff_utc"].str.endswith("Z").all()
    assert knockout[["home_slot", "away_slot"]].notna().all().all()
    assert knockout[["home_team_id", "away_team_id"]].isna().all().all()
    assert fixture["source_url"].eq(
        "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/"
        "scores-fixtures"
    ).all()
    assert fixture["verified_at_utc"].eq("2026-06-11T18:00:00Z").all()


def test_fixture_provenance_matches_frozen_csv() -> None:
    manifest_path = Path("data/metadata/fixture_2026.csv.provenance.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["source_url"] == (
        "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/"
        "scores-fixtures"
    )
    assert manifest["retrieved_at_utc"] == "2026-06-11T18:00:00Z"
    assert manifest["sha256"] == file_sha256(FIXTURE_PATH)


def test_fixture_rejects_wrong_match_count() -> None:
    fixture = pd.read_csv(FIXTURE_PATH, dtype=str, keep_default_na=True).iloc[:-1]
    with pytest.raises(ValueError, match="exactly 104"):
        validate_fixture_structure(fixture)


def test_fixture_rejects_duplicate_slot_pairing() -> None:
    fixture = pd.read_csv(FIXTURE_PATH, dtype=str, keep_default_na=True)
    fixture.loc[1, ["home_slot", "away_slot"]] = fixture.loc[
        0, ["home_slot", "away_slot"]
    ].to_numpy()
    with pytest.raises(ValueError, match="duplicate scheduled slot pairings"):
        validate_fixture_structure(fixture)


def test_fixture_rejects_non_utc_kickoff() -> None:
    fixture = pd.read_csv(FIXTURE_PATH, dtype=str, keep_default_na=True)
    fixture.loc[0, "kickoff_utc"] = "2026-06-11T13:00:00-06:00"
    with pytest.raises(pa.errors.SchemaError):
        validate_fixture_structure(fixture)


def test_fixture_rejects_unknown_host_country() -> None:
    fixture = pd.read_csv(FIXTURE_PATH, dtype=str, keep_default_na=True)
    fixture.loc[0, "host_country"] = "GBR"
    with pytest.raises(ValueError, match="unsupported host countries"):
        validate_fixture_structure(fixture)


def test_fixture_rejects_missing_group_team_id() -> None:
    fixture = pd.read_csv(FIXTURE_PATH, dtype=str, keep_default_na=True)
    fixture.loc[0, "home_team_id"] = None
    with pytest.raises(ValueError, match="group-stage participants"):
        validate_fixture_structure(fixture)
