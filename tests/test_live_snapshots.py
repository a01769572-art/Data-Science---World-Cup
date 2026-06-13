"""Append-only snapshot staging/finalization invariants (LIVE-02, D-08..D-13).

The official snapshot must be assembled in a temporary sibling directory, have
its metadata finalized exactly once after every staged artifact is registered,
and be published only by an atomic rename into a timestamped append-only
destination. No file inside a published snapshot may be mutated afterward, and
explicit hooks must exist so later Phase 4 plans can add the frozen benchmark
slice, append ledger rows, and register rendered report assets before finalize.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from cdd_mundial.live.snapshots import SnapshotWriter


def _team_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "team_id": ["alpha", "bravo"],
            "p_r32": [1.0, 1.0],
            "p_champion": [0.6, 0.4],
        }
    )


def test_writer_stages_in_sibling_temp_then_publishes_by_rename(
    test_workspace: Path,
) -> None:
    root = test_workspace / "snapshots"
    writer = SnapshotWriter(
        snapshots_root=root, snapshot_id="2026-06-13T00-00-00Z_baseline-v1-abc1234"
    )
    # Staging directory is a sibling of the final destination, not the final dir.
    assert writer.staging_dir.parent == root
    assert writer.staging_dir != writer.destination
    assert not writer.destination.exists()

    writer.add_table("team_probabilities", _team_table())
    writer.add_table("upcoming_match_predictions", _team_table())
    writer.finalize_metadata({"model_version": "baseline-v1-2026-06-13-abc1234"})
    published = writer.publish()

    assert published == writer.destination
    assert published.exists()
    assert (published / "metadata.json").exists()
    assert (published / "team_probabilities.parquet").exists()
    # Staging directory is gone after the atomic publish.
    assert not writer.staging_dir.exists()


def test_metadata_records_checksums_for_every_staged_artifact(
    test_workspace: Path,
) -> None:
    writer = SnapshotWriter(
        snapshots_root=test_workspace / "snapshots", snapshot_id="snap-checksums"
    )
    writer.add_table("team_probabilities", _team_table())
    writer.add_table("upcoming_match_predictions", _team_table())
    writer.finalize_metadata({"model_version": "baseline-v1-2026-06-13-abc1234"})
    published = writer.publish()

    metadata = json.loads((published / "metadata.json").read_text(encoding="utf-8"))
    checksums = metadata["checksums"]
    assert "team_probabilities.parquet" in checksums
    assert "upcoming_match_predictions.parquet" in checksums
    assert all(len(digest) == 64 for digest in checksums.values())
    # metadata.json never lists its own checksum (it is written last).
    assert "metadata.json" not in checksums


def test_finalize_metadata_can_only_run_once(test_workspace: Path) -> None:
    writer = SnapshotWriter(
        snapshots_root=test_workspace / "snapshots", snapshot_id="snap-once"
    )
    writer.add_table("team_probabilities", _team_table())
    writer.finalize_metadata({"model_version": "v"})
    with pytest.raises(RuntimeError, match="finaliz"):
        writer.finalize_metadata({"model_version": "v2"})


def test_publish_requires_finalized_metadata(test_workspace: Path) -> None:
    writer = SnapshotWriter(
        snapshots_root=test_workspace / "snapshots", snapshot_id="snap-nometa"
    )
    writer.add_table("team_probabilities", _team_table())
    with pytest.raises(RuntimeError, match="metadata"):
        writer.publish()


def test_published_snapshot_directory_is_not_overwritten(test_workspace: Path) -> None:
    root = test_workspace / "snapshots"
    first = SnapshotWriter(snapshots_root=root, snapshot_id="dup")
    first.add_table("team_probabilities", _team_table())
    first.finalize_metadata({"model_version": "v"})
    first.publish()

    second = SnapshotWriter(snapshots_root=root, snapshot_id="dup")
    second.add_table("team_probabilities", _team_table())
    second.finalize_metadata({"model_version": "v2"})
    with pytest.raises(FileExistsError):
        second.publish()


def test_report_assets_and_ledger_hooks_are_staged(test_workspace: Path) -> None:
    writer = SnapshotWriter(
        snapshots_root=test_workspace / "snapshots", snapshot_id="snap-hooks"
    )
    writer.add_table("team_probabilities", _team_table())
    ledger = pd.DataFrame(
        {
            "match_id": ["WC26-001"],
            "snapshot_id": ["snap-hooks"],
            "model_version": ["baseline-v1-2026-06-13-abc1234"],
            "prob_a": [0.5],
            "prob_draw": [0.3],
            "prob_b": [0.2],
            "outcome_idx": [0],
        }
    )
    writer.append_ledger_rows("calibration_ledger", ledger)
    writer.add_report_asset("report.html", "<html><body>ok</body></html>")
    writer.finalize_metadata({"model_version": "baseline-v1-2026-06-13-abc1234"})
    published = writer.publish()

    assert (published / "calibration_ledger.parquet").exists()
    assert (published / "report.html").exists()
    metadata = json.loads((published / "metadata.json").read_text(encoding="utf-8"))
    assert "calibration_ledger.parquet" in metadata["checksums"]
    assert "report.html" in metadata["checksums"]
