"""Resolve Round-of-32 participants from frozen fixture slot tokens.

Slot strings in ``data/external/fixture_2026.csv`` are the authoritative
bracket topology (D-06). This module parses the four token families that
appear in the knockout fixture and resolves them to concrete participants:

* ``1A`` / ``2L`` -- group-stage finishing position references.
* ``3ABCDF`` -- third-placed-team slots whose group is selected by the
  reviewed official Annexe C mapping produced in ``03-01``.
* ``W74`` -- the winner of an earlier knockout match.
* ``L101`` -- the loser of an earlier knockout match.

The third-place mapping is *consumed*, never re-derived from token families
alone: the official annex uniquely selects which qualifying group lands in
each third-place slot, so we read it and fail loudly on any case that is
absent, ambiguous, or incompatible with the frozen fixture tokens.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MAPPING_PATH = Path("tests/fixtures/tournament/third_place_mapping_official.json")

_GROUP_LETTERS = "ABCDEFGHIJKL"


def _match_id_from_number(number: int) -> str:
    """Render a knockout match reference (``74``) as a fixture ID (``WC26-074``)."""
    return f"WC26-{number:03d}"


@lru_cache(maxsize=None)
def _load_mapping_payload(mapping_path: str) -> dict:
    payload = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    for key in ("cases", "selectors"):
        if key not in payload:
            raise ValueError(
                f"official third-place mapping is missing required key '{key}'"
            )
    return payload


def load_official_third_place_mapping(
    mapping_path: Path = MAPPING_PATH,
) -> dict[str, dict[str, str]]:
    """Return the reviewed Annexe C mapping keyed by qualifying-group string.

    The returned dictionary maps each eight-group combination (e.g. ``"EFGHIJKL"``)
    to its ``{match_id: group}`` third-place assignment exactly as fixed in the
    official annex evidence.
    """
    payload = _load_mapping_payload(str(mapping_path))
    mapping: dict[str, dict[str, str]] = {}
    for case in payload["cases"]:
        groups = case["qualified_groups"]
        if groups in mapping:
            raise ValueError(
                f"official third-place mapping contains duplicate combination: {groups}"
            )
        mapping[groups] = dict(case["assignments"])
    return mapping


def _selectors(mapping_path: Path) -> dict[str, dict[str, str]]:
    return _load_mapping_payload(str(mapping_path))["selectors"]


def resolve_third_place_assignments(
    qualified_groups: str,
    *,
    mapping_path: Path = MAPPING_PATH,
) -> dict[str, str]:
    """Resolve the official ``{match_id: group}`` third-place assignment.

    ``qualified_groups`` is the eight-letter string identifying which groups'
    third-placed teams advanced. The assignment is read from the reviewed
    official mapping and validated against the frozen fixture tokens: every
    assigned group must be admissible for the corresponding third-place slot.
    """
    mapping = load_official_third_place_mapping(mapping_path)
    if qualified_groups not in mapping:
        raise ValueError(
            f"qualifying-group combination '{qualified_groups}' is absent from the "
            "official third-place mapping"
        )
    assignment = dict(mapping[qualified_groups])

    if len(assignment) != 8:
        raise ValueError(
            f"third-place assignment for '{qualified_groups}' must cover eight slots, "
            f"found {len(assignment)}"
        )
    assigned_groups = list(assignment.values())
    if len(set(assigned_groups)) != 8:
        raise ValueError(
            f"third-place assignment for '{qualified_groups}' repeats a group: {assigned_groups}"
        )
    if set(assigned_groups) != set(qualified_groups):
        raise ValueError(
            f"third-place assignment for '{qualified_groups}' must use exactly the "
            f"qualifying groups, found {sorted(set(assigned_groups))}"
        )

    selectors = _selectors(mapping_path)
    for match_id, group in assignment.items():
        winner_slot = _winner_slot_for(match_id, selectors)
        token = selectors[winner_slot]["slot_token"]
        if group not in token[1:]:
            raise ValueError(
                f"third-place assignment {match_id}->{group} is incompatible with "
                f"fixture slot token '{token}'"
            )
    return assignment


def _winner_slot_for(match_id: str, selectors: dict[str, dict[str, str]]) -> str:
    for winner_slot, selector in selectors.items():
        if selector["match_id"] == match_id:
            return winner_slot
    raise ValueError(
        f"official mapping has no third-place selector for match '{match_id}'"
    )


def resolve_slot(
    slot: str,
    *,
    match_id: str,
    group_positions: dict[str, str],
    winners: dict[str, str],
    losers: dict[str, str],
    third_place_assignments: dict[str, str],
) -> str:
    """Resolve a single fixture slot token to a concrete participant reference.

    Parameters mirror the four token families. ``third_place_assignments`` maps
    a Round-of-32 ``match_id`` to the qualifying group whose third-placed team
    fills that slot, as fixed by the official mapping.
    """
    if not slot:
        raise ValueError(f"empty slot reference for match '{match_id}'")

    prefix = slot[0]

    if prefix in {"1", "2"}:
        if slot not in group_positions:
            raise ValueError(f"unknown group-position slot '{slot}'")
        return group_positions[slot]

    if prefix == "3":
        groups = slot[1:]
        if not groups or any(letter not in _GROUP_LETTERS for letter in groups):
            raise ValueError(f"malformed third-place slot '{slot}'")
        if match_id not in third_place_assignments:
            raise ValueError(
                f"no third-place assignment available for match '{match_id}'"
            )
        group = third_place_assignments[match_id]
        if group not in groups:
            raise ValueError(
                f"third-place assignment {match_id}->{group} is incompatible with "
                f"slot token '{slot}'"
            )
        key = f"3{group}"
        if key not in group_positions:
            raise ValueError(f"unknown third-place position slot '{key}'")
        return group_positions[key]

    if prefix in {"W", "L"}:
        try:
            number = int(slot[1:])
        except ValueError as exc:
            raise ValueError(f"malformed result slot '{slot}'") from exc
        source_match = _match_id_from_number(number)
        table = winners if prefix == "W" else losers
        if source_match not in table:
            raise ValueError(
                f"result slot '{slot}' references unresolved match '{source_match}'"
            )
        return table[source_match]

    raise ValueError(f"unsupported slot reference '{slot}' for match '{match_id}'")
