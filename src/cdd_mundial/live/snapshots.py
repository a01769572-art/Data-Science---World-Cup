"""Append-only snapshot writer with atomic publication (D-08..D-13, T-04-05).

Every official snapshot is a *directory* (D-09), not a monolithic file. This
writer assembles the bundle in a temporary sibling directory, computes a SHA-256
for every staged artifact, finalizes ``metadata.json`` exactly once after all
artifacts are registered, and publishes the whole bundle by a single atomic
``rename`` into a timestamped, append-only destination. Once published, no file
in the snapshot is ever mutated: a second publish to the same id fails loud
rather than overwriting.

The staging API is intentionally open so later Phase 4 plans can register the
frozen benchmark slice, append authoritative calibration-ledger rows, and add
rendered report assets before metadata is finalized:

* :meth:`add_table` -- stage a parquet table (team probabilities, upcoming
  predictions, frozen benchmark, ...).
* :meth:`append_ledger_rows` -- stage an authoritative ledger table.
* :meth:`add_report_asset` -- stage a rendered report file (HTML, image, ...).
* :meth:`finalize_metadata` -- write ``metadata.json`` once, embedding the
  checksums of every staged artifact.
* :meth:`publish` -- atomically rename staging -> destination.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import time
from typing import Any

import pandas as pd

from cdd_mundial.data.provenance import file_sha256

_METADATA_NAME = "metadata.json"

# Windows/OneDrive can transiently lock a directory mid-publish (sync scan, AV),
# making the atomic staging->destination rename fail with PermissionError. A few
# short bounded retries make publication robust without weakening append-only
# semantics (the destination existence check still runs before each attempt).
_PUBLISH_RETRIES = 8
_PUBLISH_BACKOFF_SECONDS = 0.25


class SnapshotWriter:
    """Stage a snapshot bundle in a sibling temp dir and publish it atomically.

    ``snapshot_id`` becomes the published directory name under ``snapshots_root``;
    callers compose it from the publication timestamp and ``model_version`` (D-13).
    The staging directory lives alongside the destination so the final ``rename``
    is on the same filesystem and therefore atomic.
    """

    def __init__(self, *, snapshots_root: Path, snapshot_id: str) -> None:
        if not snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
            raise ValueError(f"snapshot_id must be a simple directory name, got {snapshot_id!r}")
        self.snapshots_root = Path(snapshots_root)
        self.snapshot_id = snapshot_id
        self.destination = self.snapshots_root / snapshot_id
        # Short staging prefix keeps full paths under the Windows MAX_PATH (260)
        # limit when snapshot ids embed the dated model_version (D-13).
        self.staging_dir = self.snapshots_root / f".stg-{snapshot_id}"
        self._staged: dict[str, Path] = {}
        self._finalized = False

        self.snapshots_root.mkdir(parents=True, exist_ok=True)
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True)

    def _guard_open(self) -> None:
        if self._finalized:
            raise RuntimeError(
                "snapshot metadata is already finalized; no further artifacts may be staged"
            )

    def _register(self, filename: str, path: Path) -> None:
        self._staged[filename] = path

    def add_table(self, name: str, frame: pd.DataFrame) -> Path:
        """Stage a deterministic parquet table named ``<name>.parquet``."""
        self._guard_open()
        filename = f"{name}.parquet"
        path = self.staging_dir / filename
        frame.to_parquet(path, index=False)
        self._register(filename, path)
        return path

    def append_ledger_rows(self, name: str, frame: pd.DataFrame) -> Path:
        """Stage an authoritative ledger table (calibration ledger, ...).

        The official run stages a fresh ledger slice per snapshot; later plans
        aggregate across published snapshots rather than mutating any published
        file, preserving append-only semantics.
        """
        return self.add_table(name, frame)

    def add_report_asset(self, filename: str, content: str | bytes) -> Path:
        """Stage a rendered report asset (HTML string or raw bytes)."""
        self._guard_open()
        path = self.staging_dir / filename
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        self._register(filename, path)
        return path

    def finalize_metadata(self, metadata: dict[str, Any]) -> Path:
        """Write ``metadata.json`` exactly once with checksums for every artifact.

        The checksum map covers all staged artifacts present at finalize time;
        ``metadata.json`` itself is written last and never lists its own digest.
        After this call the bundle is sealed and :meth:`publish` may run.
        """
        if self._finalized:
            raise RuntimeError("snapshot metadata has already been finalized")

        checksums = {
            filename: file_sha256(path)
            for filename, path in sorted(self._staged.items())
        }
        payload = dict(metadata)
        payload["snapshot_id"] = self.snapshot_id
        payload["checksums"] = checksums
        payload["artifacts"] = sorted(self._staged)

        metadata_path = self.staging_dir / _METADATA_NAME
        metadata_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self._finalized = True
        return metadata_path

    def publish(self) -> Path:
        """Atomically rename the staging bundle into the append-only destination.

        Fails loud if metadata was not finalized, or if a snapshot with this id is
        already published (append-only: never overwrite a published bundle).
        """
        if not self._finalized:
            raise RuntimeError("cannot publish before metadata is finalized")
        if self.destination.exists():
            raise FileExistsError(
                f"snapshot already published and is append-only: {self.destination}"
            )
        last_error: OSError | None = None
        for attempt in range(_PUBLISH_RETRIES):
            # Re-check append-only invariant before every attempt.
            if self.destination.exists():
                raise FileExistsError(
                    f"snapshot already published and is append-only: {self.destination}"
                )
            try:
                self.staging_dir.rename(self.destination)
                return self.destination
            except PermissionError as error:  # transient Windows/OneDrive lock
                last_error = error
                if attempt < _PUBLISH_RETRIES - 1:
                    time.sleep(_PUBLISH_BACKOFF_SECONDS * (attempt + 1))
        raise RuntimeError(
            f"failed to atomically publish snapshot after {_PUBLISH_RETRIES} attempts: "
            f"{self.destination}"
        ) from last_error

    def abort(self) -> None:
        """Discard the staging directory without publishing (best-effort)."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir, ignore_errors=True)


__all__ = ["SnapshotWriter"]
