"""Official daily-run orchestration: materialize -> select -> simulate -> publish.

This is the one-command official path (D-06, D-07). It enforces a strict order so
no snapshot is ever published before its model-facing inputs are materialized and
the reuse/refit decision is resolved:

1. **materialize** an immutable dated live-training artifact from the canonical
   results + history, and refresh Elo/form features
   (:mod:`cdd_mundial.live.materialization`).
2. **select_model** deterministically: reuse the pinned dated production model
   when the input fingerprint is unchanged, else refit exactly one new dated
   artifact (``baseline-v1-YYYY-MM-DD-<shortsha>``, D-13).
3. **simulate** the remaining tournament conditioned on played results with a
   fixed publication seed (:mod:`cdd_mundial.simulation.engine`).
4. **publish** an append-only snapshot bundle by atomic rename
   (:mod:`cdd_mundial.live.snapshots`), with ``metadata.json`` recording the
   commit hash, dirty status, live-training provenance, model provenance /
   fingerprint, and checksums for every artifact (D-08, D-10, D-11).

``verify_official`` runs steps 1-2 and reports the order and the materialization
artifact / fingerprint that would feed model selection, without writing or
publishing anything (the CLI ``--verify-only`` mode). The default official path
fails closed on a dirty worktree (D-11); ``allow_dirty`` only records the
override in metadata, it never hides it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any

import pandas as pd

from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.data.ingest_odds import OddsValidationError, build_odds_benchmark
from cdd_mundial.live.calibration import (
    build_ledger_rows,
    derive_realized_outcomes,
    freeze_market_benchmark,
    publish_calibration,
    register_frozen_benchmark,
)
from cdd_mundial.live.materialization import (
    materialize_live_training,
    select_model_artifact,
)
from cdd_mundial.live.predict import upcoming_match_predictions
from cdd_mundial.live.report import render_snapshot_report
from cdd_mundial.live.results import CANONICAL_RESULTS_PATH, build_live_state
from cdd_mundial.live.snapshots import SnapshotWriter
from cdd_mundial.models.dixon_coles import DixonColesModel
from cdd_mundial.simulation.engine import simulate_tournaments
from cdd_mundial.simulation.outputs import advancement_table, group_position_table

# Strict order every official run must follow; verify-only reports it explicitly.
OFFICIAL_ORDER = ["materialize", "select_model", "simulate", "publish"]
DEFAULT_XI = 0.00095
DEFAULT_SEED = 20260613


def _git_status_porcelain() -> str | None:
    """Return porcelain status text, or ``None`` if git could not be queried.

    A ``None`` return means the worktree cleanliness is *unknown* (git missing
    or errored) — distinct from an empty string, which means a verified-clean
    worktree (IN-03). The publication gate must fail closed on unknown rather
    than treating it as clean.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _git_short_commit() -> str:
    commit = _git_commit()
    return commit[:7] if commit != "unknown" else "unknown"


def _resolve_dirty(*, force_dirty: bool) -> tuple[bool, list[str]]:
    """Return (is_dirty, modified_files), honouring a test override.

    The publication-gate decision (whether a dirty worktree blocks an official
    run) lives entirely in ``run_official``; this helper only *detects*
    dirtiness. The former ``allow_dirty`` parameter was dead and misleadingly
    implied this function honoured the override (WR-03), so it has been dropped.
    """
    if force_dirty:
        return True, ["<forced-dirty>"]
    porcelain = _git_status_porcelain()
    if porcelain is None:
        # Cleanliness could not be determined; fail closed on the publication
        # gate by treating the worktree as dirty (IN-03) rather than failing
        # open on an unverifiable repo state.
        return True, ["<git-status-unknown>"]
    modified = [line[3:] for line in porcelain.splitlines() if line.strip()]
    return bool(modified), modified


def _kickoff_boundary(
    fixture: pd.DataFrame, state, *, now: datetime
) -> str:
    """Return the next pre-kickoff boundary this official publication races (D-02).

    The boundary is the earliest kickoff among still-unresolved fixtures that has
    not yet started at ``now``. A snapshot published before this instant is a
    genuine *pre-kickoff* publication for the next match block. If every
    remaining match has already kicked off (e.g. a late catch-up run), the
    tournament's final scheduled kickoff is used so the field stays monotone and
    auditable.
    """
    played = set(state.played)
    kickoffs = pd.to_datetime(fixture["kickoff_utc"], utc=True, errors="coerce")
    unresolved = fixture.loc[
        ~fixture["match_id"].isin(played) & kickoffs.notna()
    ].copy()
    unresolved["_ko"] = kickoffs[unresolved.index]
    if unresolved.empty:
        boundary = pd.to_datetime(fixture["kickoff_utc"], utc=True, errors="coerce").max()
    else:
        future = unresolved.loc[unresolved["_ko"] > now]
        boundary = (
            future["_ko"].min() if not future.empty else unresolved["_ko"].max()
        )
    return boundary.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_frozen_benchmark(
    *,
    manual_odds_path: Path | None,
    fixture_path: Path,
    captured_at: datetime,
) -> tuple[pd.DataFrame | None, str | None]:
    """Freeze the publication-time market benchmark from the manual-odds fallback.

    Returns ``(frozen_slice_or_None, error_summary_or_None)``:

    * No odds path / missing file -> ``(None, None)``: a genuinely *absent*
      benchmark is a documented fallback (D-04), not a data-quality regression.
    * Present file that fails to parse -> ``(None, "<ExcType: msg>")``: the
      benchmark is dropped, but the failure summary is surfaced so the caller
      can record it in metadata, keeping the drop auditable rather than
      invisible (WR-04).
    * Usable odds -> ``(frozen_slice, None)``.
    """
    if manual_odds_path is None:
        return None, None
    manual_odds_path = Path(manual_odds_path)
    if not manual_odds_path.exists():
        return None, None
    try:
        # output_path=None: do not overwrite the canonical odds parquet from a run.
        per_book = build_odds_benchmark(
            manual_csv_path=manual_odds_path,
            fixture_path=fixture_path,
            captured_at_utc=captured_at,
            output_path=None,
        )
    except (OddsValidationError, ValueError) as exc:
        # A PRESENT file that fails to parse is a data-quality signal, not the
        # silent absent-file fallback: report the exception so the dropped
        # benchmark is auditable in metadata (WR-04). (An empty template still
        # raises here, but recording the reason is strictly more informative.)
        return None, f"{type(exc).__name__}: {exc}"
    return freeze_market_benchmark(per_book, captured_at_utc=captured_at), None


def _prepare_run(
    *,
    results_path: Path,
    fixture_path: Path,
    data_root: Path,
    as_of: str | None,
    xi: float,
) -> dict[str, Any]:
    """Steps 1-2: build state, materialize, and resolve the model selection."""
    fixture = load_fixture_2026(fixture_path)
    state = build_live_state(results_path, fixture=fixture, as_of=as_of)

    as_of_date = (as_of or datetime.now(timezone.utc).isoformat())[:10]
    materialization = materialize_live_training(
        state.played.values(),
        fixture=fixture,
        as_of_date=as_of_date,
        data_root=data_root,
    )
    selection = select_model_artifact(
        materialization, xi=xi, data_root=data_root, as_of_date=as_of_date
    )
    return {
        "fixture": fixture,
        "state": state,
        "as_of_date": as_of_date,
        "materialization": materialization,
        "selection": selection,
    }


def verify_official(
    *,
    results_path: Path = CANONICAL_RESULTS_PATH,
    fixture_path: Path = Path("data/external/fixture_2026.csv"),
    data_root: Path = Path("data"),
    snapshots_root: Path = Path("reports/snapshots"),
    as_of: str | None = None,
    xi: float = DEFAULT_XI,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    """Validate prerequisites and report the intended run without writing artifacts.

    Resolves the materialization artifact / fingerprint that would feed model
    selection and proves the canonical order, but never simulates or publishes.
    """
    prep = _prepare_run(
        results_path=results_path,
        fixture_path=fixture_path,
        data_root=data_root,
        as_of=as_of,
        xi=xi,
    )
    selection = prep["selection"]
    materialization = prep["materialization"]
    is_dirty, _ = _resolve_dirty(force_dirty=False)
    return {
        "order": list(OFFICIAL_ORDER),
        "as_of_date": prep["as_of_date"],
        "live_training_path": materialization["live_training_path"],
        "live_training_sha256": materialization["live_training_sha256"],
        "input_fingerprint": selection["input_fingerprint"],
        "model_path": selection["model_path"],
        "model_version": selection["model_version"],
        "reused_model": selection["reused"],
        "dirty": is_dirty,
        "published": False,
    }


def run_official(
    *,
    results_path: Path = CANONICAL_RESULTS_PATH,
    fixture_path: Path = Path("data/external/fixture_2026.csv"),
    data_root: Path = Path("data"),
    snapshots_root: Path = Path("reports/snapshots"),
    manual_odds_path: Path | None = None,
    ledger_path: Path | None = None,
    n_sims: int = 10000,
    seed: int = DEFAULT_SEED,
    as_of: str | None = None,
    xi: float = DEFAULT_XI,
    allow_dirty: bool = False,
    _force_dirty: bool = False,
    _snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Execute the official run end-to-end and publish one append-only snapshot.

    The full publication chain runs in the strict order
    ``materialize -> select_model -> simulate -> publish`` and, within publish,
    stages the snapshot tables, freezes the publication-time market benchmark,
    appends the authoritative calibration ledger plus a snapshot-local slice,
    finalizes ``metadata.json`` exactly once (nested live-training / model
    provenance, kickoff boundary, preflight, publication row ids, checksums),
    atomically publishes the bundle, and renders the static HTML report beside
    it.

    Fails closed (``RuntimeError``) on a dirty worktree unless ``allow_dirty`` is
    set, in which case ``metadata.json`` records ``git_dirty=true`` and the
    modified files. ``_force_dirty`` / ``_snapshot_id`` are test hooks.
    """
    is_dirty, modified = _resolve_dirty(force_dirty=_force_dirty)
    if is_dirty and not allow_dirty:
        raise RuntimeError(
            "official publication requires a clean worktree; the repository is dirty. "
            "Commit your changes or pass allow_dirty to record the override in metadata."
        )

    prep = _prepare_run(
        results_path=results_path,
        fixture_path=fixture_path,
        data_root=data_root,
        as_of=as_of,
        xi=xi,
    )
    fixture = prep["fixture"]
    state = prep["state"]
    selection = prep["selection"]
    materialization = prep["materialization"]

    ledger_path = (
        Path(ledger_path)
        if ledger_path is not None
        else data_root / "processed" / "live" / "calibration" / "calibration_matches.parquet"
    )

    # --- simulate (only after materialization + selection resolved) --------
    model = DixonColesModel.load(Path(selection["model_path"]))
    result = simulate_tournaments(
        fixture=fixture,
        state=state,
        predict_lambdas=model.predict_lambdas,
        n_sims=n_sims,
        seed=seed,
    )
    team_probs = advancement_table(result)
    group_positions = group_position_table(result)
    upcoming = upcoming_match_predictions(fixture, state=state, model=model)

    # --- timestamps + kickoff boundary ------------------------------------
    now = datetime.now(timezone.utc)
    generated_at_iso = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    published_at_id = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    kickoff_boundary = _kickoff_boundary(fixture, state, now=now)
    snapshot_id = _snapshot_id or f"{published_at_id}_{selection['model_version']}"

    # --- freeze publication-time market benchmark (D-21) -------------------
    frozen_benchmark, benchmark_error = _build_frozen_benchmark(
        manual_odds_path=manual_odds_path,
        fixture_path=fixture_path,
        captured_at=now,
    )

    # --- stage + publish ---------------------------------------------------
    writer = SnapshotWriter(snapshots_root=snapshots_root, snapshot_id=snapshot_id)
    publication_row_ids: list[str] = []
    benchmark_ref: dict[str, Any] | None = None
    calibration_ref: dict[str, Any] | None = None
    try:
        writer.add_table("team_probabilities", team_probs)
        writer.add_table("group_positions", group_positions)
        writer.add_table("upcoming_match_predictions", upcoming)

        if frozen_benchmark is not None and not frozen_benchmark.empty:
            benchmark_ref = register_frozen_benchmark(writer, frozen_benchmark)

            # Ledger rows only for upcoming predictions that have a frozen
            # benchmark (intersection); knockout / un-priced matches are skipped.
            covered_ids = set(frozen_benchmark["match_id"])
            covered_predictions = upcoming[upcoming["match_id"].isin(covered_ids)]
            if not covered_predictions.empty:
                played_results = pd.DataFrame(
                    [
                        {
                            "match_id": r.match_id,
                            "goals_a": r.goals_a,
                            "goals_b": r.goals_b,
                        }
                        for r in state.played.values()
                    ]
                )
                outcomes = (
                    derive_realized_outcomes(played_results)
                    if not played_results.empty
                    else {}
                )
                ledger_rows = build_ledger_rows(
                    predictions=covered_predictions,
                    frozen_benchmark=frozen_benchmark,
                    outcomes=outcomes,
                    snapshot_id=snapshot_id,
                    model_version=selection["model_version"],
                )
                calibration_ref = publish_calibration(writer, ledger_path, ledger_rows)
                publication_row_ids = list(calibration_ref["ledger_row_ids"])

        metadata = {
            # New canonical fields (operator interface contract).
            "generated_at_utc": generated_at_iso,
            "kickoff_boundary_utc": kickoff_boundary,
            "git_commit": _git_commit(),
            "git_commit_short": _git_short_commit(),
            "git_dirty": is_dirty,
            "modified_files": modified if is_dirty else [],
            "allow_dirty_override": bool(allow_dirty),
            "seed": int(seed),
            "n_sims": int(n_sims),
            "xi": float(xi),
            "as_of_date": prep["as_of_date"],
            "order": list(OFFICIAL_ORDER),
            "preflight": {
                "results_validated": True,
                "materialized_before_simulation": True,
                "worktree_clean": not is_dirty,
                "benchmark_frozen": benchmark_ref is not None,
                # Auditable reason a present odds file was dropped (WR-04);
                # None when odds were absent or successfully frozen.
                "benchmark_error": benchmark_error,
            },
            "live_training_provenance": {
                "artifact_path": materialization["live_training_path"],
                "artifact_sha256": materialization["live_training_sha256"],
                "live_match_ids": materialization["live_match_ids"],
                "source_version": materialization["source_version"],
            },
            "model_provenance": {
                "model_version": selection["model_version"],
                "model_path": selection["model_path"],
                "artifact_sha256": selection["model_sha256"],
                "input_fingerprint": selection["input_fingerprint"],
                "reused": selection["reused"],
            },
            "publication_row_ids": publication_row_ids,
            "frozen_benchmark": benchmark_ref,
            "calibration": calibration_ref,
            # Back-compat fields consumed by the report renderer / earlier tests.
            "published_at_utc": generated_at_iso,
            "model_version": selection["model_version"],
            "input_fingerprint": selection["input_fingerprint"],
            "live_training_sha256": materialization["live_training_sha256"],
        }
        writer.finalize_metadata(metadata)
        destination = writer.publish()
    except BaseException:
        writer.abort()
        raise

    # --- render the static HTML report beside the published bundle (D-12) --
    report = render_snapshot_report(
        destination,
        snapshots_root=snapshots_root,
        ledger_path=ledger_path,
        output_dir=destination,
    )

    return {
        "snapshot_dir": destination.as_posix(),
        "snapshot_id": snapshot_id,
        "model_version": selection["model_version"],
        "input_fingerprint": selection["input_fingerprint"],
        "reused_model": selection["reused"],
        "kickoff_boundary_utc": kickoff_boundary,
        "publication_row_ids": publication_row_ids,
        "report_html": report["html_path"],
        "dirty": is_dirty,
        "published": True,
    }


__all__ = ["run_official", "verify_official", "OFFICIAL_ORDER"]
