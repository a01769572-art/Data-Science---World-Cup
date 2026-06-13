"""Fail-closed contract validator for the FIFA 2026 third-place regulatory gate.

Modes (PowerShell-safe, stdlib only, ASCII output):

    .venv/python.exe tests/validators/validate_third_place_mapping.py provenance
    .venv/python.exe tests/validators/validate_third_place_mapping.py mapping
    .venv/python.exe tests/validators/validate_third_place_mapping.py all

Exit code 0 means every check passed; any missing artifact, missing field or
contract violation exits 1 with an explicit reason. The validator never guesses:
secondary sources and token inference are not accepted as authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_PATH = REPO_ROOT / "data" / "metadata" / "fifa_2026_regulations.provenance.json"
EXPECTED_COMBINATIONS_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "tournament" / "third_place_expected_combinations.json"
)
MAPPING_PATH = REPO_ROOT / "tests" / "fixtures" / "tournament" / "third_place_mapping_official.json"
FIXTURE_PATH = REPO_ROOT / "data" / "external" / "fixture_2026.csv"

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
THIRD_PLACE_TOKEN_PATTERN = re.compile(r"^3[A-L]{5}$")
GROUPS = "ABCDEFGHIJKL"


class ValidationFailure(Exception):
    """Raised when a fail-closed contract check does not hold."""


def _fail(message: str) -> None:
    raise ValidationFailure(message)


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        _fail(f"{label} is missing: {path.as_posix()}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        _fail(f"{label} is not valid JSON ({error}): {path.as_posix()}")
    if not isinstance(payload, dict):
        _fail(f"{label} must be a JSON object: {path.as_posix()}")
    return payload


def _require_nonempty_str(payload: dict, key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} field '{key}' must be a non-empty string")
    return value


def _require_utc_timestamp(payload: dict, key: str, label: str) -> str:
    value = _require_nonempty_str(payload, key, label)
    if not value.endswith("Z"):
        _fail(f"{label} field '{key}' must be a UTC timestamp ending in Z, got: {value}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"{label} field '{key}' is not a valid ISO-8601 timestamp: {value}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_provenance() -> dict:
    """Validate the official-rule provenance manifest; return its payload."""
    manifest = _load_json(PROVENANCE_PATH, "provenance manifest")

    source_url = _require_nonempty_str(manifest, "source_url", "provenance manifest")
    if not source_url.startswith("https://"):
        _fail(f"source_url must use HTTPS, got: {source_url}")
    host = source_url.split("/", 3)[2].lower()
    if host != "fifa.com" and not host.endswith(".fifa.com"):
        _fail(f"source_url must point at an official FIFA host, got host: {host}")

    _require_utc_timestamp(manifest, "retrieved_at_utc", "provenance manifest")

    sha = _require_nonempty_str(manifest, "sha256", "provenance manifest")
    if not SHA256_PATTERN.match(sha):
        _fail(f"sha256 must be 64 lowercase hex characters, got: {sha}")

    local_path = _require_nonempty_str(manifest, "local_path", "provenance manifest")
    pdf_path = REPO_ROOT / local_path
    if pdf_path.exists():
        actual = _file_sha256(pdf_path)
        if actual != sha:
            _fail(
                "local regulations PDF checksum mismatch: "
                f"manifest={sha} actual={actual} ({pdf_path.as_posix()})"
            )
        print(f"  [ok] local PDF present and checksum matches: {local_path}")
    else:
        print(f"  [ok] local PDF not present (uncommitted by design); manifest stands alone: {local_path}")

    articles = manifest.get("article_pointers")
    if not isinstance(articles, dict):
        _fail("provenance manifest must contain an 'article_pointers' object")
    for required in ("group_tie_break", "fair_play_conduct_score", "best_third_ranking"):
        pointer = articles.get(required)
        if not isinstance(pointer, dict) or not pointer:
            _fail(f"article_pointers must contain a non-empty '{required}' object")
        _require_nonempty_str(pointer, "article", f"article_pointers.{required}")
        _require_nonempty_str(pointer, "printed_pages", f"article_pointers.{required}")

    annexes = manifest.get("annex_pointers")
    if not isinstance(annexes, dict):
        _fail("provenance manifest must contain an 'annex_pointers' object")
    annex_c = annexes.get("annex_c_third_place_combinations")
    if not isinstance(annex_c, dict) or not annex_c:
        _fail("annex_pointers must contain a non-empty 'annex_c_third_place_combinations' object")
    if annex_c.get("option_count") != 495:
        _fail(f"annex C option_count must be 495, got: {annex_c.get('option_count')}")
    _require_nonempty_str(annex_c, "physical_pages", "annex_pointers.annex_c_third_place_combinations")
    _require_nonempty_str(annex_c, "referenced_by", "annex_pointers.annex_c_third_place_combinations")

    review = manifest.get("reviewed_extraction")
    if not isinstance(review, dict):
        _fail("provenance manifest must contain a 'reviewed_extraction' object")
    _require_nonempty_str(review, "extracted_by", "reviewed_extraction")
    _require_utc_timestamp(review, "extracted_at_utc", "reviewed_extraction")
    _require_nonempty_str(review, "method", "reviewed_extraction")
    _require_nonempty_str(review, "verification", "reviewed_extraction")

    for key in ("document_title", "edition", "license", "source", "source_version"):
        _require_nonempty_str(manifest, key, "provenance manifest")

    print("  [ok] official FIFA HTTPS source, timestamp, SHA-256, article and annex pointers, reviewed extraction")
    return manifest


def validate_mapping() -> None:
    """Validate expected combinations, official mapping, and the real fixture."""
    _fail(
        "mapping validation artifacts are not yet present: "
        "third_place_expected_combinations.json and third_place_mapping_official.json "
        "are authored in plan 03-01 task 2"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"provenance", "mapping", "all"}:
        print("usage: validate_third_place_mapping.py [provenance|mapping|all]")
        return 1
    mode = argv[1]
    try:
        if mode in {"provenance", "all"}:
            print("checking provenance manifest...")
            validate_provenance()
        if mode in {"mapping", "all"}:
            print("checking expected combinations, official mapping, and fixture selectors...")
            validate_mapping()
    except ValidationFailure as failure:
        print(f"FAIL: {failure}")
        return 1
    print(f"PASS: {mode} checks satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
