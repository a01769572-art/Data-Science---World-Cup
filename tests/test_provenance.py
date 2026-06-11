from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    copy_immutable_capture,
    file_sha256,
    write_provenance_manifest,
)


def test_file_sha256_is_stable_and_content_sensitive(test_workspace: Path) -> None:
    capture = test_workspace / "capture.csv"
    capture.write_bytes(b"team,rating\nmexico,1810\n")

    first = file_sha256(capture)
    second = file_sha256(capture)

    assert first == second
    assert len(first) == 64
    capture.write_bytes(b"team,rating\nmexico,1811\n")
    assert file_sha256(capture) != first


def test_manifest_contains_all_provenance_fields_in_utc(data_root: Path) -> None:
    capture = data_root / "raw" / "source.csv"
    capture.parent.mkdir(parents=True)
    capture.write_text("value\n1\n", encoding="utf-8")
    record = ProvenanceRecord(
        source="example-source",
        source_url="https://example.test/source.csv",
        retrieved_at_utc=datetime(2026, 6, 11, 7, 30, tzinfo=timezone(timedelta(hours=-5))),
        source_version="2026-06-11",
        sha256=file_sha256(capture),
        license="CC0-1.0",
        local_path=capture,
        notes="Test fixture",
    )

    manifest = write_provenance_manifest(record, data_root / "metadata")
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert set(payload) == {
        "source",
        "source_url",
        "retrieved_at_utc",
        "source_version",
        "sha256",
        "license",
        "local_path",
        "notes",
    }
    assert payload["retrieved_at_utc"] == "2026-06-11T12:30:00Z"
    assert payload["sha256"] == file_sha256(capture)
    assert payload["local_path"] == capture.as_posix()


def test_manifest_json_is_deterministic(data_root: Path) -> None:
    record = ProvenanceRecord(
        source="example-source",
        source_url="https://example.test/source.csv",
        retrieved_at_utc=datetime(2026, 6, 11, 12, 30, tzinfo=timezone.utc),
        source_version="v1",
        sha256="a" * 64,
        license="CC0-1.0",
        local_path=Path("data/raw/example/source.csv"),
    )

    manifest = write_provenance_manifest(record, data_root / "metadata")
    first = manifest.read_bytes()
    write_provenance_manifest(record, data_root / "metadata")

    assert manifest.read_bytes() == first
    assert first.endswith(b"\n")


def test_manifest_rejects_naive_retrieval_timestamp(data_root: Path) -> None:
    record = ProvenanceRecord(
        source="example-source",
        source_url="https://example.test/source.csv",
        retrieved_at_utc=datetime(2026, 6, 11, 12, 30),
        source_version="v1",
        sha256="a" * 64,
        license="CC0-1.0",
        local_path=Path("data/raw/example/source.csv"),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        write_provenance_manifest(record, data_root / "metadata")


def test_identical_capture_replay_does_not_rewrite(test_workspace: Path) -> None:
    source = test_workspace / "download.csv"
    destination = test_workspace / "data" / "raw" / "source.csv"
    source.write_bytes(b"immutable payload")

    copy_immutable_capture(source, destination)
    original_mtime = destination.stat().st_mtime_ns
    replayed = copy_immutable_capture(source, destination)

    assert replayed == destination
    assert destination.read_bytes() == source.read_bytes()
    assert destination.stat().st_mtime_ns == original_mtime


def test_different_payload_cannot_overwrite_capture(test_workspace: Path) -> None:
    first_source = test_workspace / "first.csv"
    second_source = test_workspace / "second.csv"
    destination = test_workspace / "data" / "raw" / "source.csv"
    first_source.write_bytes(b"original")
    second_source.write_bytes(b"changed")
    copy_immutable_capture(first_source, destination)

    with pytest.raises(FileExistsError, match="different content"):
        copy_immutable_capture(second_source, destination)

    assert destination.read_bytes() == b"original"
