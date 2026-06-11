"""Checksum, provenance manifest, and immutable capture utilities."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any


def file_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a file."""
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ProvenanceRecord:
    """Serializable metadata required for every acquired source artifact."""

    source: str
    source_url: str
    retrieved_at_utc: datetime
    source_version: str
    sha256: str
    license: str
    local_path: Path
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the record to deterministic JSON-compatible values."""
        if self.retrieved_at_utc.tzinfo is None:
            raise ValueError("retrieved_at_utc must be timezone-aware")

        retrieved_at = self.retrieved_at_utc.astimezone(timezone.utc)
        return {
            "license": self.license,
            "local_path": self.local_path.as_posix(),
            "notes": self.notes,
            "retrieved_at_utc": retrieved_at.isoformat().replace("+00:00", "Z"),
            "sha256": self.sha256,
            "source": self.source,
            "source_url": self.source_url,
            "source_version": self.source_version,
        }


def write_provenance_manifest(
    record: ProvenanceRecord,
    metadata_root: Path = Path("data/metadata"),
) -> Path:
    """Write a deterministic UTF-8 JSON manifest and return its path."""
    metadata_root.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_root / f"{record.local_path.name}.provenance.json"
    payload = json.dumps(record.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    manifest_path.write_text(payload, encoding="utf-8", newline="\n")
    return manifest_path


def copy_immutable_capture(source_path: Path, destination_path: Path) -> Path:
    """Copy a source once, accepting identical replay and rejecting mutation."""
    source_checksum = file_sha256(source_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if destination_path.exists():
        if file_sha256(destination_path) != source_checksum:
            raise FileExistsError(f"immutable capture already exists with different content: {destination_path}")
        return destination_path

    try:
        with source_path.open("rb") as source, destination_path.open("xb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
    except FileExistsError:
        if file_sha256(destination_path) != source_checksum:
            raise FileExistsError(
                f"immutable capture already exists with different content: {destination_path}"
            ) from None
    except BaseException:
        destination_path.unlink(missing_ok=True)
        raise

    if file_sha256(destination_path) != source_checksum:
        destination_path.unlink(missing_ok=True)
        raise OSError(f"checksum mismatch after copying immutable capture: {destination_path}")
    return destination_path

