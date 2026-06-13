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
from cdd_mundial.live.materialization import (
    materialize_live_training,
    select_model_artifact,
)
from cdd_mundial.live.predict import upcoming_match_predictions
from cdd_mundial.live.results import CANONICAL_RESULTS_PATH, build_live_state
from cdd_mundial.live.snapshots import SnapshotWriter
from cdd_mundial.models.dixon_coles import DixonColesModel
from cdd_mundial.simulation.engine import simulate_tournaments
from cdd_mundial.simulation.outputs import advancement_table, group_position_table

# Strict order every official run must follow; verify-only reports it explicitly.
OFFICIAL_ORDER = ["materialize", "select_model", "simulate", "publish"]
DEFAULT_XI = 0.00095
DEFAULT_SEED = 20260613


def _git_status_porcelain() -> str:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


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


def _resolve_dirty(allow_dirty: bool, force_dirty: bool) -> tuple[bool, list[str]]:
    """Return (is_dirty, modified_files), honouring a test override."""
    if force_dirty:
        return True, ["<forced-dirty>"]
    porcelain = _git_status_porcelain()
    modified = [line[3:] for line in porcelain.splitlines() if line.strip()]
    return bool(modified), modified


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
    is_dirty, _ = _resolve_dirty(allow_dirty, force_dirty=False)
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
    n_sims: int = 10000,
    seed: int = DEFAULT_SEED,
    as_of: str | None = None,
    xi: float = DEFAULT_XI,
    allow_dirty: bool = False,
    _force_dirty: bool = False,
) -> dict[str, Any]:
    """Execute the official run end-to-end and publish one append-only snapshot.

    Fails closed (``RuntimeError``) on a dirty worktree unless ``allow_dirty`` is
    set, in which case ``metadata.json`` records ``dirty=true`` and the modified
    files. ``_force_dirty`` is a test hook that simulates a dirty worktree.
    """
    is_dirty, modified = _resolve_dirty(allow_dirty, force_dirty=_force_dirty)
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

    # --- stage + publish ---------------------------------------------------
    now = datetime.now(timezone.utc)
    published_at_iso = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    published_at_id = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    snapshot_id = f"{published_at_id}_{selection['model_version']}"
    writer = SnapshotWriter(snapshots_root=snapshots_root, snapshot_id=snapshot_id)
    try:
        writer.add_table("team_probabilities", team_probs)
        writer.add_table("group_positions", group_positions)
        writer.add_table("upcoming_match_predictions", upcoming)

        metadata = {
            "published_at_utc": published_at_iso,
            "as_of_date": prep["as_of_date"],
            "commit": _git_commit(),
            "commit_short": _git_short_commit(),
            "dirty": is_dirty,
            "modified_files": modified if is_dirty else [],
            "allow_dirty_override": bool(allow_dirty),
            "model_version": selection["model_version"],
            "model_path": selection["model_path"],
            "model_sha256": selection["model_sha256"],
            "input_fingerprint": selection["input_fingerprint"],
            "reused_model": selection["reused"],
            "live_training_path": materialization["live_training_path"],
            "live_training_sha256": materialization["live_training_sha256"],
            "live_match_ids": materialization["live_match_ids"],
            "n_sims": int(n_sims),
            "seed": int(seed),
            "xi": float(xi),
            "order": list(OFFICIAL_ORDER),
        }
        writer.finalize_metadata(metadata)
        destination = writer.publish()
    except BaseException:
        writer.abort()
        raise

    return {
        "snapshot_dir": destination.as_posix(),
        "snapshot_id": snapshot_id,
        "model_version": selection["model_version"],
        "input_fingerprint": selection["input_fingerprint"],
        "reused_model": selection["reused"],
        "dirty": is_dirty,
        "published": True,
    }


__all__ = ["run_official", "verify_official", "OFFICIAL_ORDER"]
