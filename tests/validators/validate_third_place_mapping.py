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

import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from itertools import combinations
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


def _load_fixture_selectors() -> dict[str, dict]:
    """Read the frozen fixture and return the real third-place selector rows."""
    if not FIXTURE_PATH.exists():
        _fail(f"frozen fixture is missing: {FIXTURE_PATH.as_posix()}")
    with FIXTURE_PATH.open(encoding="utf-8", newline="") as handle:
        fixture_rows = list(csv.DictReader(handle))
    selectors: dict[str, dict] = {}
    for row in fixture_rows:
        if row.get("stage") != "round_of_32":
            continue
        away = row.get("away_slot") or ""
        if THIRD_PLACE_TOKEN_PATTERN.match(away):
            match_id = row["match_id"]
            if match_id in selectors:
                _fail(f"fixture contains duplicate third-place selector match_id: {match_id}")
            selectors[match_id] = {
                "home_slot": row.get("home_slot") or "",
                "token": away,
                "allowed_groups": set(away[1:]),
            }
        home = row.get("home_slot") or ""
        if THIRD_PLACE_TOKEN_PATTERN.match(home):
            _fail(f"unexpected third-place token on the home side of {row['match_id']}: {home}")
    if len(selectors) != 8:
        _fail(f"frozen fixture must contain exactly 8 third-place selector rows, found {len(selectors)}")
    return selectors


def _validate_expected_combinations(manifest_sha: str) -> list[str]:
    """Validate the independent expected-combinations fixture; return its sets."""
    payload = _load_json(EXPECTED_COMBINATIONS_PATH, "expected combinations fixture")

    refs = payload.get("annex_refs")
    if not isinstance(refs, dict):
        _fail("expected combinations fixture must contain an 'annex_refs' object")
    _require_nonempty_str(refs, "article", "annex_refs")
    _require_nonempty_str(refs, "annex", "annex_refs")
    manifest_ref = _require_nonempty_str(refs, "regulations_manifest", "annex_refs")
    if (REPO_ROOT / manifest_ref) != PROVENANCE_PATH:
        _fail(f"annex_refs.regulations_manifest must point at the provenance manifest, got: {manifest_ref}")
    ref_sha = _require_nonempty_str(refs, "regulations_sha256", "annex_refs")
    if ref_sha != manifest_sha:
        _fail(f"annex_refs.regulations_sha256 does not match the provenance manifest: {ref_sha}")
    _require_nonempty_str(payload, "authoring_method", "expected combinations fixture")

    combos = payload.get("combinations")
    if not isinstance(combos, list) or not combos:
        _fail("expected combinations fixture must contain a non-empty 'combinations' list")
    seen = set()
    for combo in combos:
        if not isinstance(combo, str) or len(combo) != 8:
            _fail(f"each expected combination must be an 8-character string, got: {combo!r}")
        if combo != "".join(sorted(combo)) or len(set(combo)) != 8 or not set(combo) <= set(GROUPS):
            _fail(f"expected combination must be 8 distinct sorted groups from A-L, got: {combo}")
        if combo in seen:
            _fail(f"duplicate expected combination: {combo}")
        seen.add(combo)
    full = {"".join(c) for c in combinations(GROUPS, 8)}
    if seen != full:
        missing = sorted(full - seen)[:5]
        extra = sorted(seen - full)[:5]
        _fail(f"expected combinations must equal all C(12,8)=495 sets; missing={missing} extra={extra}")
    print(f"  [ok] expected combinations: {len(combos)} sets, complete C(12,8), annex refs verified")
    return combos


def validate_mapping() -> None:
    """Validate expected combinations, official mapping, and the real fixture."""
    manifest = _load_json(PROVENANCE_PATH, "provenance manifest")
    manifest_sha = _require_nonempty_str(manifest, "sha256", "provenance manifest")

    expected = set(_validate_expected_combinations(manifest_sha))
    fixture_selectors = _load_fixture_selectors()

    payload = _load_json(MAPPING_PATH, "official mapping fixture")

    prov = payload.get("provenance")
    if not isinstance(prov, dict):
        _fail("official mapping fixture must contain a 'provenance' object")
    manifest_ref = _require_nonempty_str(prov, "regulations_manifest", "mapping provenance")
    if (REPO_ROOT / manifest_ref) != PROVENANCE_PATH:
        _fail(f"mapping provenance.regulations_manifest must point at the provenance manifest, got: {manifest_ref}")
    ref_sha = _require_nonempty_str(prov, "regulations_sha256", "mapping provenance")
    if ref_sha != manifest_sha:
        _fail(f"mapping provenance.regulations_sha256 does not match the provenance manifest: {ref_sha}")
    _require_nonempty_str(prov, "annex", "mapping provenance")
    _require_nonempty_str(prov, "extracted_by", "mapping provenance")
    _require_utc_timestamp(prov, "extracted_at_utc", "mapping provenance")
    _require_nonempty_str(prov, "review", "mapping provenance")

    declared = payload.get("selectors")
    if not isinstance(declared, dict) or len(declared) != 8:
        _fail("official mapping fixture must declare exactly 8 selectors")
    declared_match_ids = set()
    for label, info in declared.items():
        if not isinstance(info, dict):
            _fail(f"selector '{label}' must be an object")
        match_id = _require_nonempty_str(info, "match_id", f"selector {label}")
        token = _require_nonempty_str(info, "slot_token", f"selector {label}")
        side = _require_nonempty_str(info, "side", f"selector {label}")
        if side != "away":
            _fail(f"selector '{label}' side must be 'away' (all real third-place tokens are away slots), got: {side}")
        real = fixture_selectors.get(match_id)
        if real is None:
            _fail(f"selector '{label}' references unknown fixture selector position: {match_id}")
        if token != real["token"]:
            _fail(f"selector '{label}' token mismatch for {match_id}: declared {token}, fixture has {real['token']}")
        if label != real["home_slot"]:
            _fail(f"selector '{label}' does not match the fixture winner slot {real['home_slot']} on {match_id}")
        if match_id in declared_match_ids:
            _fail(f"selector match_id declared more than once: {match_id}")
        declared_match_ids.add(match_id)
    if declared_match_ids != set(fixture_selectors):
        missing = sorted(set(fixture_selectors) - declared_match_ids)
        _fail(f"declared selectors must cover every real fixture selector position; missing: {missing}")
    print("  [ok] 8 declared selectors match the real round-of-32 fixture rows (match_id, side, token, winner slot)")

    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        _fail("official mapping fixture must contain a non-empty 'cases' list")

    seen_options: set[int] = set()
    seen_combinations: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            _fail("every mapping case must be an object")
        option = case.get("option")
        if not isinstance(option, int) or option < 1:
            _fail(f"mapping case has invalid option number: {option!r}")
        if option in seen_options:
            _fail(f"duplicate mapping option number: {option}")
        seen_options.add(option)

        qualified = case.get("qualified_groups")
        if (
            not isinstance(qualified, str)
            or len(qualified) != 8
            or qualified != "".join(sorted(qualified))
            or len(set(qualified)) != 8
            or not set(qualified) <= set(GROUPS)
        ):
            _fail(f"option {option}: qualified_groups must be 8 distinct sorted groups, got: {qualified!r}")
        if qualified not in expected:
            _fail(f"option {option}: combination {qualified} is not in the independent expected set")
        if qualified in seen_combinations:
            _fail(f"combination covered by more than one mapping case: {qualified}")
        seen_combinations.add(qualified)

        assignments = case.get("assignments")
        if not isinstance(assignments, dict):
            _fail(f"option {option}: assignments must be an object")
        if set(assignments) != set(fixture_selectors):
            unknown = sorted(set(assignments) - set(fixture_selectors))
            missing = sorted(set(fixture_selectors) - set(assignments))
            _fail(
                f"option {option}: assignments must use each real selector exactly once; "
                f"unknown={unknown} missing={missing}"
            )
        groups_used = list(assignments.values())
        if len(set(groups_used)) != 8:
            _fail(f"option {option}: a third-place group is assigned more than once")
        if set(groups_used) != set(qualified):
            _fail(f"option {option}: assigned groups {sorted(groups_used)} do not equal qualified_groups {qualified}")
        for match_id, group in assignments.items():
            if group not in fixture_selectors[match_id]["allowed_groups"]:
                _fail(
                    f"option {option}: group {group} is not allowed by the real slot token "
                    f"{fixture_selectors[match_id]['token']} on {match_id}"
                )

    if seen_combinations != expected:
        missing = sorted(expected - seen_combinations)[:5]
        _fail(f"mapping cases do not cover every expected combination; missing (first 5): {missing}")
    print(
        f"  [ok] {len(cases)} mapping cases: exhaustive over the independent expected set, "
        "bijective per case, token-compatible against the frozen fixture"
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
