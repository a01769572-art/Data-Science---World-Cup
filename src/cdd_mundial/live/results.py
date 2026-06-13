"""Fail-closed loading of canonical 2026 results into a ``TournamentState``.

The official daily path is exactly::

    results_2026.csv -> LiveResultsSchema -> PlayedMatchResult rows
                     -> TournamentState.from_results(..., fixture=...)

This module is the single authoritative entrypoint for live results (D-01).
A scraper or any external helper may only *verify* the canonical CSV; it can
never silently rewrite it (D-04). If the CSV is incomplete for matches that
have already kicked off, the run fails by default and may only continue with an
explicit, traceable override (D-05).

The module is pure and reusable: it builds and returns a validated
``TournamentState`` and records any override/discrepancy details on the passed
``OverrideToken`` for later snapshot metadata. It contains no CLI orchestration.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from cdd_mundial.live.contracts import LiveResultsSchema
from cdd_mundial.simulation.state import PlayedMatchResult, TournamentState

CANONICAL_RESULTS_PATH = Path("data/external/results_2026.csv")

# Canonical column order for results_2026.csv. Only what TournamentState needs;
# operational metadata lives in separate artifacts (D-03).
LIVE_RESULTS_COLUMNS: tuple[str, ...] = (
    "match_id",
    "team_a",
    "team_b",
    "goals_a",
    "goals_b",
    "fair_play_a",
    "fair_play_b",
    "advanced_team",
)

_REQUIRED_COLUMNS: tuple[str, ...] = ("match_id", "team_a", "team_b", "goals_a", "goals_b")


class IncompleteResultsError(ValueError):
    """Raised when matches that already kicked off are absent from the canonical CSV.

    Fails the official run by default (D-05). May only be excused per match via
    an explicit :class:`OverrideToken`.
    """


class DiscrepancyError(ValueError):
    """Raised when scraper-assist data disagrees with the canonical CSV (D-04).

    The official run fails closed; the canonical CSV is never silently rewritten.
    """


@dataclass
class OverrideToken:
    """Explicit, traceable override for an official run (D-05, D-04).

    ``allow_missing`` lists match IDs that may be absent despite having kicked
    off; ``allow_discrepancies`` permits proceeding past scraper-assist
    mismatches while always keeping the canonical CSV value. The token records
    exactly what it excused so the snapshot metadata layer can persist a trace.
    """

    reason: str
    allow_missing: tuple[str, ...] = ()
    allow_discrepancies: bool = False
    missing_matches: list[str] = field(default_factory=list)
    discrepancies: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("OverrideToken requires a non-empty reason for traceability")
        self.allow_missing = tuple(self.allow_missing)


def _coerce_optional_int(value: object) -> int | None:
    """Map a pandas cell (possibly NaN/float) to an int or None for the contract."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value):
        return None
    return int(value)


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def load_live_results(path: Path = CANONICAL_RESULTS_PATH) -> tuple[PlayedMatchResult, ...]:
    """Read and validate the canonical results CSV into ``PlayedMatchResult`` rows.

    Validation is strict: missing required columns, extra metadata columns,
    duplicate ``match_id`` values, negative goals, and positive conduct scores
    all fail loudly via the pandera contract or the ``PlayedMatchResult``
    invariants. The CSV is never partially repaired.
    """
    frame = pd.read_csv(Path(path), keep_default_na=True)

    missing_columns = sorted(set(_REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"results CSV is missing required column(s): {missing_columns}")

    # Ensure optional columns exist before strict validation (canonical shape).
    for column in LIVE_RESULTS_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    validated = LiveResultsSchema.validate(frame[list(LIVE_RESULTS_COLUMNS)].copy())

    records: list[PlayedMatchResult] = []
    for row in validated.itertuples(index=False):
        records.append(
            PlayedMatchResult(
                match_id=str(row.match_id),
                team_a=str(row.team_a),
                team_b=str(row.team_b),
                goals_a=int(row.goals_a),
                goals_b=int(row.goals_b),
                fair_play_a=_coerce_optional_int(row.fair_play_a),
                fair_play_b=_coerce_optional_int(row.fair_play_b),
                advanced_team=_coerce_optional_str(row.advanced_team),
            )
        )
    return tuple(records)


def _check_completeness(
    records: Iterable[PlayedMatchResult],
    *,
    fixture: pd.DataFrame,
    as_of: str | None,
    override: OverrideToken | None,
) -> None:
    """Fail closed when an already-kicked-off match is absent from the results."""
    if as_of is None:
        return
    if "kickoff_utc" not in fixture.columns:
        raise ValueError("completeness check requires a 'kickoff_utc' fixture column")

    present = {record.match_id for record in records}
    due = fixture.loc[fixture["kickoff_utc"].notna() & (fixture["kickoff_utc"] <= as_of), "match_id"]
    missing = sorted(str(match_id) for match_id in due if str(match_id) not in present)
    if not missing:
        return

    excused = set(override.allow_missing) if override is not None else set()
    blocking = [match_id for match_id in missing if match_id not in excused]
    if blocking:
        raise IncompleteResultsError(
            "canonical results_2026.csv is incomplete for already-played match(es): "
            f"{blocking}; supply the results or an explicit override"
        )
    if override is not None:
        for match_id in missing:
            if match_id not in override.missing_matches:
                override.missing_matches.append(match_id)


def _check_scraper_assist(
    records: Iterable[PlayedMatchResult],
    *,
    scraper_assist: pd.DataFrame,
    override: OverrideToken | None,
) -> None:
    """Treat scraper-assist data as verification only; fail closed on mismatch (D-04)."""
    canonical = {record.match_id: record for record in records}
    assist = LiveResultsSchema.validate(scraper_assist[list(LIVE_RESULTS_COLUMNS)].copy())

    discrepancies: list[dict[str, object]] = []
    for row in assist.itertuples(index=False):
        match_id = str(row.match_id)
        record = canonical.get(match_id)
        if record is None:
            continue
        assist_a, assist_b = int(row.goals_a), int(row.goals_b)
        if (assist_a, assist_b) != (record.goals_a, record.goals_b):
            discrepancies.append(
                {
                    "match_id": match_id,
                    "canonical": (record.goals_a, record.goals_b),
                    "assist": (assist_a, assist_b),
                }
            )

    if not discrepancies:
        return

    allow = override is not None and override.allow_discrepancies
    if not allow:
        ids = sorted(str(item["match_id"]) for item in discrepancies)
        raise DiscrepancyError(
            "scraper-assist data disagrees with canonical results_2026.csv for "
            f"match(es): {ids}; canonical CSV is authoritative — correct it or "
            "pass an explicit override"
        )
    # Recorded for traceability; canonical scores remain unchanged.
    override.discrepancies.extend(discrepancies)


def build_live_state(
    path: Path = CANONICAL_RESULTS_PATH,
    *,
    fixture: pd.DataFrame,
    as_of: str | None = None,
    scraper_assist: pd.DataFrame | None = None,
    override: OverrideToken | None = None,
) -> TournamentState:
    """Build a fail-closed ``TournamentState`` from the canonical results CSV.

    Order of gates:

    1. Load + strict-validate the CSV into ``PlayedMatchResult`` rows.
    2. If ``scraper_assist`` is given, verify agreement (never override) — fail
       closed on mismatch unless an explicit override accepts the canonical
       value and records the discrepancy.
    3. If ``as_of`` is given, enforce completeness for already-kicked-off
       matches — fail closed unless excused per match by an override.
    4. Delegate to ``TournamentState.from_results(...)`` for fixture-backed
       validation (duplicate/out-of-fixture/unknown-team/participant checks).
    """
    records = load_live_results(path)

    if scraper_assist is not None:
        _check_scraper_assist(records, scraper_assist=scraper_assist, override=override)

    _check_completeness(records, fixture=fixture, as_of=as_of, override=override)

    return TournamentState.from_results(records, fixture=fixture)
