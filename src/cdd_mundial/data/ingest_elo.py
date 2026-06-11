"""Acquire current World Football Elo ratings and build a canonical snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path

import pandas as pd

from cdd_mundial.data.contracts import EloRatingsSchema
from cdd_mundial.data.http import fetch_bytes
from cdd_mundial.data.identities import TeamResolver
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    file_sha256,
    write_provenance_manifest,
)

WORLD_URL = "https://www.eloratings.net/World.tsv"
TEAMS_URL = "https://www.eloratings.net/en.teams.tsv"


def _capture_bytes(payload: bytes, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload_checksum = sha256(payload).hexdigest()
    if destination.exists():
        if file_sha256(destination) != payload_checksum:
            raise FileExistsError(
                f"immutable capture already exists with different content: {destination}"
            )
        return destination
    try:
        destination.write_bytes(payload)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    if file_sha256(destination) != payload_checksum:
        destination.unlink(missing_ok=True)
        raise OSError(f"checksum mismatch after writing immutable capture: {destination}")
    return destination


def _parse_team_names(payload: bytes) -> dict[str, str]:
    names: dict[str, str] = {}
    for line_number, line in enumerate(payload.decode("utf-8-sig").splitlines(), start=1):
        fields = line.split("\t")
        if len(fields) < 2 or not fields[0] or not fields[1]:
            raise ValueError(f"en.teams.tsv malformed row {line_number}")
        code, primary_name = fields[:2]
        if code in names:
            raise ValueError(f"en.teams.tsv duplicate code: {code}")
        names[code] = primary_name
    return names


def _parse_world(payload: bytes) -> pd.DataFrame:
    world = pd.read_csv(
        StringIO(payload.decode("utf-8-sig")),
        sep="\t",
        header=None,
        dtype={2: "string"},
    )
    if world.shape[1] < 4:
        raise ValueError("World.tsv must contain at least rank, code, and rating columns")
    world = world.loc[world.iloc[:, 2].notna()].copy()
    parsed = pd.DataFrame(
        {
            "rank": pd.to_numeric(world.iloc[:, 0], errors="raise"),
            "elo_source_code": world.iloc[:, 2].astype("string"),
            "elo_rating": pd.to_numeric(world.iloc[:, 3], errors="raise"),
        }
    )
    if parsed["elo_source_code"].duplicated().any():
        raise ValueError("World.tsv contains duplicate team codes")
    return parsed


def fetch_elo_snapshot(
    *,
    raw_root: Path = Path("data/raw/eloratings"),
    metadata_root: Path = Path("data/metadata"),
    output_path: Path = Path("data/processed/elo_current.parquet"),
    retrieved_at_utc: datetime | None = None,
    resolver: TeamResolver | None = None,
) -> pd.DataFrame:
    """Fetch, immutably capture, resolve, validate, and serialize current Elo ratings."""
    retrieved_at = retrieved_at_utc or datetime.now(timezone.utc)
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at_utc must be timezone-aware")
    retrieved_at = retrieved_at.astimezone(timezone.utc)
    source_version = retrieved_at.strftime("%Y-%m-%dT%H-%M-%SZ")
    active_resolver = resolver or TeamResolver.from_csv()

    payloads = {
        "World.tsv": (WORLD_URL, fetch_bytes(WORLD_URL)),
        "en.teams.tsv": (TEAMS_URL, fetch_bytes(TEAMS_URL)),
    }
    for filename, (url, payload) in payloads.items():
        destination = _capture_bytes(payload, raw_root / source_version / filename)
        write_provenance_manifest(
            ProvenanceRecord(
                source="eloratings",
                source_url=url,
                retrieved_at_utc=retrieved_at,
                source_version=source_version,
                sha256=file_sha256(destination),
                license="Source terms not stated; captured for reproducible research.",
                local_path=destination,
                notes="Unmodified TSV response from eloratings.net.",
            ),
            metadata_root,
        )

    names_by_code = _parse_team_names(payloads["en.teams.tsv"][1])
    world = _parse_world(payloads["World.tsv"][1])
    world["source_name"] = world["elo_source_code"].map(names_by_code)
    if world["source_name"].isna().any():
        missing = sorted(world.loc[world["source_name"].isna(), "elo_source_code"].tolist())
        raise ValueError(f"World.tsv codes missing from en.teams.tsv: {missing}")

    participants = active_resolver.teams.loc[
        active_resolver.teams["is_world_cup_2026"], "team_id"
    ].tolist()
    aliases = active_resolver.aliases[
        (active_resolver.aliases["source"] == "eloratings")
        & (active_resolver.aliases["team_id"].isin(participants))
    ][["source_name", "team_id"]]
    if aliases["team_id"].duplicated().any():
        raise ValueError("multiple Elo aliases configured for a World Cup participant")

    selected = aliases.merge(world, how="left", on="source_name", validate="one_to_one")
    unresolved = sorted(selected.loc[selected["elo_rating"].isna(), "team_id"].tolist())
    if unresolved:
        raise ValueError(f"unresolved World Cup Elo identities: {unresolved}")

    selected["rating_date_utc"] = retrieved_at.isoformat().replace("+00:00", "Z")
    selected["source"] = "eloratings"
    selected["source_version"] = source_version
    output = selected[
        [
            "team_id",
            "elo_rating",
            "rank",
            "rating_date_utc",
            "source",
            "source_version",
        ]
    ]
    validated = EloRatingsSchema.validate(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validated.to_parquet(output_path, index=False)
    return validated
