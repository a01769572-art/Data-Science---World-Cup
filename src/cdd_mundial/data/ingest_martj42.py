"""Acquire martj42 data and build the canonical historical match dataset."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import kagglehub
import pandas as pd

from cdd_mundial.data.contracts import HistoricalMatchesSchema
from cdd_mundial.data.identities import TeamResolver, UnknownTeamError
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    copy_immutable_capture,
    file_sha256,
    write_provenance_manifest,
)

DATASET_HANDLE = "martj42/international-football-results-from-1872-to-2017"
DATASET_URL = f"https://www.kaggle.com/datasets/{DATASET_HANDLE}"
RAW_FILENAMES = ("results.csv", "shootouts.csv", "former_names.csv")
SOURCE_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_source_version(source_version: str) -> None:
    if not SOURCE_VERSION_PATTERN.fullmatch(source_version) or source_version in {".", ".."}:
        raise ValueError(
            "source_version must be one safe path segment containing only "
            "letters, numbers, dot, underscore, or hyphen"
        )


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
    _validate_source_version(source_version)
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


def audit_martj42_identity_coverage(
    results_path: Path,
    shootouts_path: Path,
    resolver: TeamResolver | None = None,
) -> pd.DataFrame:
    """Report every martj42 name/date combination that lacks a reviewed alias."""
    active_resolver = resolver or TeamResolver.from_csv()
    results = pd.read_csv(results_path, usecols=["date", "home_team", "away_team"])
    shootouts = pd.read_csv(shootouts_path, usecols=["date", "winner"])
    appearances = pd.concat(
        [
            results[["date", "home_team"]].rename(columns={"home_team": "source_name"}),
            results[["date", "away_team"]].rename(columns={"away_team": "source_name"}),
            shootouts[["date", "winner"]].rename(columns={"winner": "source_name"}),
        ],
        ignore_index=True,
    ).dropna(subset=["source_name"])
    appearances["date"] = pd.to_datetime(appearances["date"], errors="raise").dt.strftime(
        "%Y-%m-%d"
    )

    unresolved_rows: list[dict[str, str]] = []
    for row in appearances.drop_duplicates().itertuples(index=False):
        try:
            active_resolver.resolve("martj42", str(row.source_name), str(row.date))
        except UnknownTeamError:
            unresolved_rows.append(
                {"source_name": str(row.source_name), "date": str(row.date)}
            )

    if not unresolved_rows:
        return pd.DataFrame(
            columns=["source_name", "first_seen", "last_seen", "match_count"]
        )

    unresolved = pd.DataFrame(unresolved_rows)
    return (
        unresolved.groupby("source_name", as_index=False)
        .agg(
            first_seen=("date", "min"),
            last_seen=("date", "max"),
            match_count=("date", "size"),
        )
        .sort_values("source_name", ignore_index=True)
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

    partial_scores = results["home_score"].isna() ^ results["away_score"].isna()
    if partial_scores.any():
        raise ValueError("results.csv contains rows with only one score populated")
    results = results[
        results["home_score"].notna() & results["away_score"].notna()
    ].copy()

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


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required provenance manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_martj42_materialization(
    data_root: Path = Path("data"),
) -> dict[str, int | str]:
    """Fail unless the real parquet and its source provenance are internally consistent."""
    output_path = data_root / "processed" / "historical_matches.parquet"
    if not output_path.exists():
        raise FileNotFoundError(f"required DATA-01 artifact is missing: {output_path}")

    historical = HistoricalMatchesSchema.validate(pd.read_parquet(output_path))
    versions = historical["source_version"].drop_duplicates().tolist()
    if len(versions) != 1 or not versions[0] or versions[0] == "unknown":
        raise ValueError(f"historical parquet must contain one explicit source version: {versions}")
    source_version = str(versions[0])
    if set(historical["source"]) != {"martj42"}:
        raise ValueError("historical parquet contains non-martj42 source rows")

    raw_root = data_root / "raw" / "martj42" / source_version
    metadata_root = data_root / "metadata"
    raw_paths: dict[str, Path] = {}
    for filename in RAW_FILENAMES:
        manifest = _load_manifest(metadata_root / f"{filename}.provenance.json")
        raw_path = Path(str(manifest["local_path"]))
        if not raw_path.is_absolute():
            raw_path = data_root.resolve().parent / raw_path
        if not raw_path.exists():
            raise FileNotFoundError(f"provenance points to a missing raw file: {raw_path}")
        if raw_path.resolve() != (raw_root / filename).resolve():
            raise ValueError(
                f"provenance path does not match parquet source version: {raw_path}"
            )
        if manifest["source"] != "martj42" or manifest["source_version"] != source_version:
            raise ValueError(f"invalid martj42 provenance metadata: {filename}")
        if manifest["sha256"] != file_sha256(raw_path):
            raise ValueError(f"raw checksum does not match provenance: {raw_path}")
        raw_paths[filename] = raw_path

    output_manifest = _load_manifest(
        metadata_root / f"{output_path.name}.provenance.json"
    )
    if output_manifest["sha256"] != file_sha256(output_path):
        raise ValueError("historical parquet checksum does not match provenance")
    if output_manifest["source_version"] != source_version:
        raise ValueError("historical parquet provenance has the wrong source version")

    results = pd.read_csv(raw_paths["results.csv"])
    shootouts = pd.read_csv(raw_paths["shootouts.csv"])
    partial_scores = results["home_score"].isna() ^ results["away_score"].isna()
    if partial_scores.any():
        raise ValueError("raw results contain rows with only one score populated")
    completed_results = results[
        results["home_score"].notna() & results["away_score"].notna()
    ]
    if len(historical) != len(completed_results):
        raise ValueError(
            "historical parquet row count "
            f"{len(historical)} != completed raw results {len(completed_results)}"
        )
    unresolved = audit_martj42_identity_coverage(
        raw_paths["results.csv"],
        raw_paths["shootouts.csv"],
    )
    if not unresolved.empty:
        raise UnknownTeamError(
            f"{len(unresolved)} unresolved martj42 names remain:\n"
            f"{unresolved.to_string(index=False)}"
        )

    source_names = set(results["home_team"]) | set(results["away_team"])
    source_names |= set(shootouts["winner"].dropna())
    return {
        "row_count": len(historical),
        "team_count": len(source_names),
        "source_version": source_version,
        "parquet_sha256": file_sha256(output_path),
        "unplayed_row_count": len(results) - len(completed_results),
    }


def materialize_martj42(
    source_version: str,
    data_root: Path = Path("data"),
) -> dict[str, int | str]:
    """Download, resolve, build, provenance, and verify the DATA-01 artifact."""
    _validate_source_version(source_version)
    captured = download_martj42(
        source_version=source_version,
        raw_root=data_root / "raw" / "martj42",
        metadata_root=data_root / "metadata",
    )
    unresolved = audit_martj42_identity_coverage(
        captured["results.csv"],
        captured["shootouts.csv"],
    )
    if not unresolved.empty:
        raise UnknownTeamError(
            f"{len(unresolved)} unresolved martj42 names block materialization:\n"
            f"{unresolved.to_string(index=False)}"
        )

    output_path = data_root / "processed" / "historical_matches.parquet"
    build_historical_matches(
        captured["results.csv"],
        captured["shootouts.csv"],
        output_path=output_path,
        source_version=source_version,
    )
    raw_checksums = {
        filename: file_sha256(path) for filename, path in sorted(captured.items())
    }
    write_provenance_manifest(
        ProvenanceRecord(
            source="martj42",
            source_url=DATASET_URL,
            retrieved_at_utc=datetime.now(timezone.utc),
            source_version=source_version,
            sha256=file_sha256(output_path),
            license="CC0-1.0",
            local_path=output_path,
            notes=f"Derived canonical parquet from immutable raw captures: {raw_checksums}",
        ),
        data_root / "metadata",
    )
    return verify_martj42_materialization(data_root=data_root)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize and verify martj42 history.")
    parser.add_argument(
        "--source-version",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Immutable snapshot identifier stored in raw paths and provenance.",
    )
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing artifacts without downloading or rebuilding.",
    )
    args = parser.parse_args()
    summary = (
        verify_martj42_materialization(args.data_root)
        if args.verify_only
        else materialize_martj42(args.source_version, args.data_root)
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
