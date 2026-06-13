"""Immutable live-training materialization and deterministic model selection (D-06).

The official daily run must, *before* it ever simulates or publishes, prove that
the canonical live results have been folded into model-facing training inputs in
a reproducible, auditable way. This module implements exactly that stage and the
refit-vs-reuse decision that follows it:

1. :func:`map_live_rows_to_canonical` maps validated ``PlayedMatchResult`` rows
   into the canonical 90-minute match schema enforced by
   :mod:`cdd_mundial.data.contracts` (``HistoricalMatchesSchema``), reusing the
   same neutral-venue / FIFA-World-Cup semantics the Phase 2 loader expects. It
   never mutates raw history; it only derives new canonical rows.
2. :func:`materialize_live_training` writes a dated, immutable derived
   live-training artifact (history + live rows) under ``data/processed/live/``
   with deterministic provenance and a SHA-256, then refreshes the custom Elo
   features chronologically over the combined frame via the existing Phase 2
   ``recompute_elo`` API. Identical canonical inputs replay to the same checksum;
   changed/corrected results change it.
3. :func:`compute_input_fingerprint` hashes the derived artifact plus the
   relevant feature/model parameters, and :func:`select_model_artifact`
   deterministically reuses the pinned dated production model when the
   fingerprint is unchanged and refits exactly one new dated artifact (with a
   ``baseline-v1-YYYY-MM-DD-<shortsha>`` ``model_version``, D-13) when it changes.

This ordering mirrors the dated-artifact materialization precedent in
:mod:`cdd_mundial.models.validation` and the deterministic JSON / SHA-256 /
exclusive-write discipline in :mod:`cdd_mundial.data.provenance`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pandas as pd

from cdd_mundial.data.contracts import HistoricalMatchesSchema
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    file_sha256,
    write_provenance_manifest,
)
from cdd_mundial.models.dixon_coles import fit_dixon_coles
from cdd_mundial.models.elo import recompute_elo, snapshot_ratings
from cdd_mundial.models.loading import load_matches
from cdd_mundial.models.tournaments import TournamentKTable
from cdd_mundial.simulation.state import PlayedMatchResult

# World Cup 2026 matches are neutral-venue except hosts; the live-training rows
# keep the tournament tag the K-table and Dixon-Coles fit expect.
LIVE_TOURNAMENT = "FIFA World Cup"
LIVE_SOURCE = "cdd-mundial-live"

_CANONICAL_COLUMNS: tuple[str, ...] = (
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
)

MODEL_FAMILY = "baseline-v1"


def map_live_rows_to_canonical(
    results: Iterable[PlayedMatchResult],
    *,
    fixture: pd.DataFrame,
    source_version: str,
    as_of_date: str,
) -> pd.DataFrame:
    """Map validated played results into the canonical 90-minute match schema.

    The fixture supplies authoritative metadata (kickoff date, venue/host) and
    gates membership: a result whose ``match_id`` is absent from the fixture is
    rejected fail-loud, never silently dropped. ``advanced_team`` on a drawn
    knockout match is recorded as a 90-minute draw decided after extra time, so
    ``result_after_extra_time`` is set and the loader labels it a draw (the same
    semantics the historical parquet uses for martj42 FT+ET scores).
    """
    if "match_id" not in fixture.columns:
        raise ValueError("fixture must contain a 'match_id' column")
    fixture_meta = fixture.set_index("match_id")
    valid_ids = set(fixture_meta.index)

    def _meta(match_id: str, column: str, default: object) -> object:
        if column in fixture_meta.columns:
            value = fixture_meta.at[match_id, column]
            if pd.notna(value):
                return value
        return default

    rows: list[dict[str, Any]] = []
    for record in results:
        if record.match_id not in valid_ids:
            raise ValueError(
                f"live result {record.match_id!r} is not in the fixture; refusing to "
                "materialize an out-of-fixture training row"
            )
        kickoff = str(_meta(record.match_id, "kickoff_utc", f"{as_of_date}T00:00:00Z"))
        date_str = kickoff[:10]
        # Contract (WR-06): ``goals_a``/``goals_b`` on the canonical results
        # boundary are 90-MINUTE scores, never full-time-including-ET figures.
        # A knockout that was level after 90' carries ``advanced_team`` with an
        # equal score; we record it as a draw decided after extra time
        # (``result_after_extra_time=True``) and feed the literal 90' scoreline
        # to the Dixon-Coles fit (matching the martj42 historical convention).
        # If a post-90 (incl. ET) score were miskeyed here, the goal model would
        # silently train on the wrong margin, so guard the only locally
        # detectable inconsistency: a decided 90' knockout whose recorded
        # ``advanced_team`` does not match the side that actually won on goals.
        drew_after_et = (
            record.advanced_team is not None and record.goals_a == record.goals_b
        )
        if record.advanced_team is not None and record.goals_a != record.goals_b:
            winner = record.team_a if record.goals_a > record.goals_b else record.team_b
            if record.advanced_team != winner:
                raise ValueError(
                    f"live result {record.match_id!r}: advanced_team "
                    f"{record.advanced_team!r} does not match the 90-minute "
                    f"winner {winner!r}; canonical goals must be 90' scores "
                    "(refusing to materialize a row with inconsistent margin)"
                )
        rows.append(
            {
                "match_id": record.match_id,
                "date": date_str,
                "home_team_id": record.team_a,
                "away_team_id": record.team_b,
                "home_team_source_name": record.team_a,
                "away_team_source_name": record.team_b,
                "home_score": int(record.goals_a),
                "away_score": int(record.goals_b),
                "tournament": LIVE_TOURNAMENT,
                "city": str(_meta(record.match_id, "host_city", "")),
                "country": str(_meta(record.match_id, "host_country", "")),
                "neutral": True,
                "shootout_winner_team_id": None,
                "result_after_extra_time": bool(drew_after_et),
                "source": LIVE_SOURCE,
                "source_version": source_version,
            }
        )

    frame = pd.DataFrame(rows, columns=list(_CANONICAL_COLUMNS))
    # Revalidate against the canonical contract so drift fails loud here, not
    # downstream inside the Dixon-Coles fit.
    return HistoricalMatchesSchema.validate(frame).reset_index(drop=True)


def _live_training_dir(data_root: Path) -> Path:
    return data_root / "processed" / "live"


def materialize_live_training(
    results: Iterable[PlayedMatchResult],
    *,
    fixture: pd.DataFrame,
    as_of_date: str,
    data_root: Path = Path("data"),
) -> dict[str, Any]:
    """Materialize the dated immutable live-training artifact and refreshed Elo.

    Reads the immutable historical parquet, maps the live results into canonical
    rows, concatenates them chronologically, and writes a dated derived parquet
    under ``data/processed/live/``. The write is content-addressed: re-running
    with identical canonical inputs reproduces a byte-identical artifact (same
    SHA-256), and the raw historical parquet is never rewritten. Elo/form
    features are then refreshed sequentially over the combined frame using the
    existing Phase 2 ``recompute_elo`` API and returned as a feature snapshot.
    """
    results = tuple(results)
    history_path = data_root / "processed" / "historical_matches.parquet"
    history = load_matches(path=history_path)

    source_versions = history["source_version"].drop_duplicates().tolist()
    source_version = str(source_versions[0]) if source_versions else "unknown"

    live_rows = map_live_rows_to_canonical(
        results, fixture=fixture, source_version=source_version, as_of_date=as_of_date
    )

    # Combine into a single canonical frame ordered chronologically for the
    # sequential Elo recomputation; load_matches already sorted history.
    history_canonical = history[list(_CANONICAL_COLUMNS)].copy()
    history_canonical["date"] = history_canonical["date"].dt.strftime("%Y-%m-%d")

    # Guard match_id disjointness across the union BEFORE writing (WR-01).
    # map_live_rows_to_canonical only checks uniqueness within the live slice;
    # HistoricalMatchesSchema requires match_id unique over the whole frame, but
    # that is revalidated downstream in load_matches — after the dated immutable
    # parquet and its provenance manifest are already on disk. Fail loud here so
    # a live/history match_id collision cannot leave a poisoned artifact.
    overlap = set(history_canonical["match_id"]) & set(live_rows["match_id"])
    if overlap:
        raise ValueError(
            f"live match_id(s) collide with history: {sorted(overlap)}"
        )

    combined = pd.concat([history_canonical, live_rows], ignore_index=True)

    out_dir = _live_training_dir(data_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / f"live_training_{as_of_date}.parquet"

    # Deterministic artifact: stable row order and no index. Re-materializing the
    # same canonical inputs must reproduce the same bytes, so we sort by the
    # canonical (date, match_id) key before writing.
    deterministic = combined.sort_values(["date", "match_id"], kind="stable").reset_index(
        drop=True
    )
    # Content hash over the canonical sorted frame (CR-02). Unlike the parquet
    # file bytes (which embed a pyarrow writer version and may vary
    # compression/row-group framing across library versions and platforms),
    # this is content-stable: identical canonical inputs always hash equal.
    # It is the equality basis for the immutable-write guard AND the input
    # fingerprint that drives the refit-vs-reuse decision and model_version.
    content_sha = _canonical_content_sha(deterministic)
    _write_immutable_parquet(deterministic, artifact_path, content_sha=content_sha)
    # Parquet file hash is still recorded for provenance/audit, but it is NOT
    # the reproducibility basis (see compute_input_fingerprint).
    artifact_sha = file_sha256(artifact_path)

    # Refresh Elo/form features chronologically over history + live rows.
    elo_input = load_matches(frame=deterministic.assign(date=deterministic["date"]))
    elo_history = recompute_elo(elo_input, TournamentKTable.from_csv())
    ratings = snapshot_ratings(elo_history, source_version)
    elo_ratings = {
        str(team): float(rating)
        for team, rating in zip(ratings["team_id"], ratings["elo_rating"], strict=True)
    }

    teams = sorted(set(deterministic["home_team_id"]) | set(deterministic["away_team_id"]))

    _write_live_provenance(artifact_path, source_version, history_path, data_root, results)

    return {
        "live_training_path": artifact_path.as_posix(),
        "live_training_sha256": artifact_sha,
        "live_training_content_sha256": content_sha,
        "source_version": source_version,
        "as_of_date": as_of_date,
        "live_match_ids": sorted(record.match_id for record in results),
        "n_history_rows": int(len(history_canonical)),
        "n_live_rows": int(len(live_rows)),
        "teams": teams,
        "elo_ratings": elo_ratings,
        "_frame": deterministic,
    }


def _canonical_content_sha(frame: pd.DataFrame) -> str:
    """Content-stable SHA-256 over the canonical CSV serialization of ``frame``.

    Hashing the CSV payload (rather than parquet file bytes) makes the digest
    independent of the pyarrow writer version, compression choice, and
    row-group framing, all of which vary across library versions/platforms and
    would otherwise break the "identical inputs replay to the same checksum"
    invariant (CR-02). Callers are responsible for passing an already
    deterministically-ordered frame.
    """
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256(payload).hexdigest()


def _write_immutable_parquet(
    frame: pd.DataFrame, destination: Path, *, content_sha: str
) -> None:
    """Write ``frame`` to parquet, accepting identical replay, rejecting mutation.

    Mirrors :func:`cdd_mundial.data.provenance.copy_immutable_capture` semantics
    for derived artifacts: if the destination already exists with the same
    *content* it is left untouched; if it exists with different content the run
    fails loud rather than silently overwriting a dated artifact.

    Equality is decided on the content hash of the canonical frame (CR-02), not
    on raw parquet bytes: ``DataFrame.to_parquet`` is not guaranteed
    byte-deterministic across pyarrow/OS, so a byte comparison would falsely
    trip this guard on a legitimate identical-input re-run.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = pd.read_parquet(destination)
        if _canonical_content_sha(existing) != content_sha:
            raise FileExistsError(
                f"live-training artifact already exists with different content: {destination}"
            )
        return
    new_bytes = _frame_to_parquet_bytes(frame)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_bytes(new_bytes)
    tmp.replace(destination)


def _frame_to_parquet_bytes(frame: pd.DataFrame) -> bytes:
    import io

    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()


def _write_live_provenance(
    artifact_path: Path,
    source_version: str,
    history_path: Path,
    data_root: Path,
    results: tuple[PlayedMatchResult, ...],
) -> None:
    metadata_root = data_root / "metadata"
    note = (
        f"Derived live-training artifact: {len(results)} live row(s) folded into "
        f"historical_matches.parquet sha256={file_sha256(history_path)}"
    )
    manifest = write_provenance_manifest(
        ProvenanceRecord(
            source="cdd-mundial-live-materialization",
            source_url="local:src/cdd_mundial/live/materialization.py",
            retrieved_at_utc=datetime.now(timezone.utc),
            source_version=source_version,
            sha256=file_sha256(artifact_path),
            license="CC0-1.0 (derived from martj42 + canonical 2026 results)",
            local_path=artifact_path,
            notes=note,
        ),
        metadata_root,
    )
    manifest.replace(metadata_root / f"{artifact_path.name}.provenance.json")


def compute_input_fingerprint(materialization: dict[str, Any], *, xi: float) -> str:
    """Deterministic SHA-256 over the derived artifact plus model/feature params.

    The fingerprint is what drives the refit-vs-reuse decision: it changes if and
    only if the derived live-training artifact changes (corrected/new results) or
    a relevant model parameter (the Dixon-Coles decay ``xi``) changes. The team
    roster is included so a structural change in coverage also forces a refit.

    The artifact identity is taken from the *content* hash of the canonical
    frame, not the parquet file SHA (CR-02): hashing the non-deterministic
    parquet bytes would flip the fingerprint — forcing a spurious refit and a
    new ``model_version`` — on a different pyarrow/OS despite identical inputs.
    """
    payload = {
        "live_training_content_sha256": materialization["live_training_content_sha256"],
        "source_version": materialization["source_version"],
        "teams": list(materialization["teams"]),
        "xi": float(xi),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return sha256(encoded).hexdigest()


def _fingerprint_record_path(data_root: Path) -> Path:
    return data_root / "processed" / "models" / "live_model_fingerprint.json"


def select_model_artifact(
    materialization: dict[str, Any],
    *,
    xi: float,
    data_root: Path = Path("data"),
    as_of_date: str,
) -> dict[str, Any]:
    """Reuse the pinned dated model when the fingerprint is unchanged, else refit.

    The decision is deterministic and recorded: a sidecar
    ``live_model_fingerprint.json`` pins the last published fingerprint and the
    dated ``dc_params_*.json`` it produced. When the current input fingerprint
    matches and that artifact still exists, the run reuses it verbatim (no new
    artifact, no churn). When the fingerprint differs (or nothing is pinned yet),
    the run fits exactly one new dated Dixon-Coles artifact and re-pins.

    ``model_version`` follows ``baseline-v1-YYYY-MM-DD-<shortsha>`` (D-13), where
    the short SHA is the leading 7 hex chars of the input fingerprint, tying the
    version string to the exact canonical inputs that produced it.
    """
    fingerprint = compute_input_fingerprint(materialization, xi=xi)
    models_root = data_root / "processed" / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    record_path = _fingerprint_record_path(data_root)

    pinned: dict[str, Any] | None = None
    if record_path.exists():
        pinned = json.loads(record_path.read_text(encoding="utf-8"))

    if (
        pinned is not None
        and pinned.get("input_fingerprint") == fingerprint
        and Path(pinned["model_path"]).exists()
    ):
        # Verify on-disk integrity before reusing (WR-05): compare the recomputed
        # digest against the SHA pinned at fit time. A model file mutated or
        # corrupted after pinning must not be reused silently and stamped with
        # the old model_version, which would break the version<->inputs tie
        # (D-13). On mismatch (or a legacy record with no pinned SHA), fall
        # through to a fresh refit rather than trusting the artifact.
        recomputed_sha = file_sha256(Path(pinned["model_path"]))
        pinned_sha = pinned.get("model_sha256")
        if pinned_sha is not None and recomputed_sha == pinned_sha:
            return {
                "reused": True,
                "model_path": pinned["model_path"],
                "model_sha256": recomputed_sha,
                "model_version": pinned["model_version"],
                "input_fingerprint": fingerprint,
                "xi": float(xi),
            }

    # Fingerprint changed, first run, or pinned model failed its integrity
    # check: refit exactly one new dated artifact.
    short_sha = fingerprint[:7]
    frame = materialization["_frame"]
    matches = load_matches(frame=frame)
    cutoff = matches["date"].max() + pd.Timedelta(days=1)
    model = fit_dixon_coles(matches, cutoff=cutoff, xi=float(xi))

    model_path = models_root / f"dc_params_{as_of_date}.json"
    model.save(model_path)
    model_version = f"{MODEL_FAMILY}-{as_of_date}-{short_sha}"
    # Persist the digest at fit time so a later reuse can prove on-disk
    # integrity before trusting the artifact (WR-05).
    model_sha = file_sha256(model_path)

    record = {
        "input_fingerprint": fingerprint,
        "model_path": model_path.as_posix(),
        "model_version": model_version,
        "model_sha256": model_sha,
        "as_of_date": as_of_date,
        "xi": float(xi),
        "live_training_sha256": materialization["live_training_sha256"],
        "live_training_content_sha256": materialization["live_training_content_sha256"],
    }
    record_path.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return {
        "reused": False,
        "model_path": model_path.as_posix(),
        "model_sha256": model_sha,
        "model_version": model_version,
        "input_fingerprint": fingerprint,
        "xi": float(xi),
    }
