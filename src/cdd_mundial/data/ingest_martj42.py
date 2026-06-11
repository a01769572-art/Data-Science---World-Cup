"""Acquire martj42 data and build the canonical historical match dataset."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

import kagglehub
import pandas as pd

from cdd_mundial.data.contracts import HistoricalMatchesSchema
from cdd_mundial.data.identities import TeamResolver
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    copy_immutable_capture,
    file_sha256,
    write_provenance_manifest,
)

DATASET_HANDLE = "martj42/international-football-results-from-1872-to-2017"
DATASET_URL = f"https://www.kaggle.com/datasets/{DATASET_HANDLE}"
RAW_FILENAMES = ("results.csv", "shootouts.csv", "former_names.csv")


def _find_downloaded_file(download_root: Path, filename: str) -> Path:
    matches = sorted(download_root.rglob(filename))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected exactly one {filename!r} below {download_root}, found {len(matches)}"
        )
    return matches[0]


def download_martj42(
    source_version: str,
    raw_root: Path = Path("data/raw/martj42"),
    metadata_root: Path = Path("data/metadata"),
    retrieved_at_utc: datetime | None = None,
) -> dict[str, Path]:
    """Download and immutably capture the three martj42 source files."""
    download_root = Path(kagglehub.dataset_download(DATASET_HANDLE))
    capture_root = raw_root / source_version
    retrieved_at = retrieved_at_utc or datetime.now(timezone.utc)
    captured: dict[str, Path] = {}

    for filename in RAW_FILENAMES:
        source_path = _find_downloaded_file(download_root, filename)
        destination = copy_immutable_capture(source_path, capture_root / filename)
        record = ProvenanceRecord(
            source="martj42",
            source_url=DATASET_URL,
            retrieved_at_utc=retrieved_at,
            source_version=source_version,
            sha256=file_sha256(destination),
            license="CC0-1.0",
            local_path=destination,
            notes="Unmodified capture downloaded with kagglehub.",
        )
        write_provenance_manifest(record, metadata_root)
        captured[filename] = destination

    return captured


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return normalized.strip("-")


def _resolve_series(
    frame: pd.DataFrame,
    name_column: str,
    resolver: TeamResolver,
) -> pd.Series:
    return pd.Series(
        [
            resolver.resolve("martj42", source_name, match_date)
            for source_name, match_date in zip(
                frame[name_column],
                frame["date"],
                strict=True,
            )
        ],
        index=frame.index,
        dtype="string",
    )


def _match_ids(frame: pd.DataFrame) -> pd.Series:
    bases = frame.apply(
        lambda row: (
            f"{row['date']}-{_slug(row['home_team_source_name'])}-"
            f"{_slug(row['away_team_source_name'])}"
        ),
        axis=1,
    )
    collision_number = bases.groupby(bases).cumcount()
    return pd.Series(
        [
            base if collision == 0 else f"{base}-{collision + 1}"
            for base, collision in zip(bases, collision_number, strict=True)
        ],
        index=frame.index,
        dtype="string",
    )


def build_historical_matches(
    results_path: Path,
    shootouts_path: Path,
    output_path: Path = Path("data/processed/historical_matches.parquet"),
    source_version: str = "unknown",
    resolver: TeamResolver | None = None,
) -> pd.DataFrame:
    """Resolve, validate, and serialize martj42 matches without changing scores."""
    active_resolver = resolver or TeamResolver.from_csv()
    results = pd.read_csv(results_path)
    shootouts = pd.read_csv(shootouts_path)

    required_results = {
        "date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "tournament",
        "city",
        "country",
        "neutral",
    }
    required_shootouts = {"date", "home_team", "away_team", "winner"}
    if missing := required_results - set(results.columns):
        raise ValueError(f"results.csv missing columns: {sorted(missing)}")
    if missing := required_shootouts - set(shootouts.columns):
        raise ValueError(f"shootouts.csv missing columns: {sorted(missing)}")

    results["date"] = pd.to_datetime(results["date"], errors="raise").dt.strftime("%Y-%m-%d")
    shootouts["date"] = pd.to_datetime(shootouts["date"], errors="raise").dt.strftime(
        "%Y-%m-%d"
    )
    shootout_keys = ["date", "home_team", "away_team"]
    if shootouts.duplicated(shootout_keys).any():
        raise ValueError("shootouts.csv contains duplicate date/home/away rows")

    joined = results.merge(
        shootouts[shootout_keys + ["winner"]],
        how="left",
        on=shootout_keys,
        validate="many_to_one",
    )
    output = pd.DataFrame(
        {
            "date": joined["date"],
            "home_team_source_name": joined["home_team"],
            "away_team_source_name": joined["away_team"],
            "home_score": joined["home_score"],
            "away_score": joined["away_score"],
            "tournament": joined["tournament"],
            "city": joined["city"],
            "country": joined["country"],
            "neutral": joined["neutral"],
        }
    )
    output["home_team_id"] = _resolve_series(joined, "home_team", active_resolver)
    output["away_team_id"] = _resolve_series(joined, "away_team", active_resolver)
    output["shootout_winner_team_id"] = pd.Series(
        [
            None
            if pd.isna(winner)
            else active_resolver.resolve("martj42", str(winner), match_date)
            for winner, match_date in zip(joined["winner"], joined["date"], strict=True)
        ],
        dtype="string",
    )
    output["result_after_extra_time"] = joined["winner"].notna()
    output["source"] = "martj42"
    output["source_version"] = source_version
    output.insert(0, "match_id", _match_ids(output))

    canonical_columns = [
        "match_id",
        "date",
        "home_team_id",
        "away_team_id",
        "home_team_source_name",
        "away_team_source_name",
        "home_score",
        "away_score",
        "tournament",
        "city",
        "country",
        "neutral",
        "shootout_winner_team_id",
        "result_after_extra_time",
        "source",
        "source_version",
    ]
    validated = HistoricalMatchesSchema.validate(output[canonical_columns])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validated.to_parquet(output_path, index=False)
    return validated
