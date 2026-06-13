"""Thin conditional tournament state: played results only (SIM-03, D-01, D-02).

`TournamentState` stores exactly the matches that have already been played,
keyed by fixture ``match_id``. It never persists derived standings, cached
group tables, or resolved future bracket participants — those are recomputed
downstream from fixture plus fixed results, which keeps the vectorized engine
free of stale derived state.

Naming follows the frozen Phase 2 contract: ``team_a`` / ``team_b``, with host
advantage living only in ``ctx`` (D-02), never in column names.

Fair-play values are observed Article 13 conduct scores (deductions: yellow -1,
indirect red -3, direct red -4, yellow + direct red -5). They enter the state
as explicit recorded inputs for already played matches; Phase 3 never simulates
future card processes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from cdd_mundial.data.identities import UnknownTeamError

_REQUIRED_RESULT_KEYS = ("match_id", "team_a", "team_b", "goals_a", "goals_b")
_OPTIONAL_RESULT_KEYS = ("fair_play_a", "fair_play_b", "advanced_team")
_REQUIRED_FIXTURE_COLUMNS = ("match_id", "stage", "home_team_id", "away_team_id")


def _as_goals(value: object, side: str) -> int:
    """Validate one goal count: a non-negative integer (bools are rejected)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"goals_{side} must be an integer, got {value!r}")
    if value < 0:
        raise ValueError(f"goals_{side} must be >= 0, got {value!r}")
    return value


def _as_conduct_score(value: object, side: str) -> int | None:
    """Validate one optional Article 13 conduct score (deductions are <= 0)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"fair_play_{side} must be an integer deduction or None, got {value!r}")
    if value > 0:
        raise ValueError(
            f"fair_play_{side} must be <= 0 (Art. 13 conduct scores are deductions), got {value!r}"
        )
    return value


@dataclass(frozen=True)
class PlayedMatchResult:
    """One played match with team_a/team_b semantics and optional observed tie-break data.

    ``advanced_team`` records which side advanced when a knockout match was
    drawn after 90 minutes (decided by extra time / penalties in reality).
    It is recorded state, never resolved bracket logic.
    """

    match_id: str
    team_a: str
    team_b: str
    goals_a: int
    goals_b: int
    fair_play_a: int | None = None
    fair_play_b: int | None = None
    advanced_team: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.match_id, str) or not self.match_id:
            raise ValueError(f"match_id must be a non-empty string, got {self.match_id!r}")
        for side, team in (("a", self.team_a), ("b", self.team_b)):
            if not isinstance(team, str) or not team:
                raise ValueError(f"team_{side} must be a non-empty string, got {team!r}")
        if self.team_a == self.team_b:
            raise ValueError(f"team_a and team_b must be distinct, both are {self.team_a!r}")
        _as_goals(self.goals_a, "a")
        _as_goals(self.goals_b, "b")
        _as_conduct_score(self.fair_play_a, "a")
        _as_conduct_score(self.fair_play_b, "b")

        if self.advanced_team is not None:
            if self.advanced_team not in (self.team_a, self.team_b):
                raise ValueError(
                    f"advanced_team must be one of the participants "
                    f"({self.team_a!r}, {self.team_b!r}), got {self.advanced_team!r}"
                )
            if self.goals_a != self.goals_b:
                winner = self.team_a if self.goals_a > self.goals_b else self.team_b
                if self.advanced_team != winner:
                    raise ValueError(
                        f"advanced_team {self.advanced_team!r} contradicts the decided "
                        f"score {self.goals_a}-{self.goals_b} (winner {winner!r})"
                    )


@dataclass(frozen=True)
class TournamentState:
    """Played results only, keyed by ``match_id`` and normalized deterministically."""

    played: Mapping[str, PlayedMatchResult]

    def __post_init__(self) -> None:
        for match_id, record in self.played.items():
            if match_id != record.match_id:
                raise ValueError(
                    f"played key {match_id!r} does not match record match_id {record.match_id!r}"
                )

    @classmethod
    def from_results(
        cls,
        results: Iterable[PlayedMatchResult],
        *,
        fixture: pd.DataFrame,
    ) -> TournamentState:
        """Validate played results against the fixture and build a normalized state.

        Rejects (fail-loud, T-03-04): duplicate ``match_id`` values, match IDs
        absent from the fixture, team slugs unknown to the fixture's canonical
        participants, participants that conflict with resolved fixture rows,
        ``advanced_team`` on group matches, and drawn knockout results without
        a recorded advancing team.
        """
        missing_columns = sorted(set(_REQUIRED_FIXTURE_COLUMNS) - set(fixture.columns))
        if missing_columns:
            raise ValueError(f"fixture is missing required columns: {missing_columns}")

        stage_by_match = dict(zip(fixture["match_id"], fixture["stage"]))
        participants_by_match: dict[str, frozenset[str]] = {}
        for row in fixture.itertuples(index=False):
            home, away = row.home_team_id, row.away_team_id
            if pd.notna(home) and pd.notna(away):
                participants_by_match[row.match_id] = frozenset((str(home), str(away)))
        known_teams = frozenset().union(*participants_by_match.values()) if participants_by_match else frozenset()

        played: dict[str, PlayedMatchResult] = {}
        for record in results:
            if record.match_id in played:
                raise ValueError(f"duplicate played result for match_id {record.match_id!r}")
            if record.match_id not in stage_by_match:
                raise ValueError(f"match_id {record.match_id!r} is not in the fixture")

            unknown = sorted(
                team for team in (record.team_a, record.team_b) if team not in known_teams
            )
            if unknown:
                raise UnknownTeamError(
                    f"played result {record.match_id!r} references unknown team slug(s): {unknown!r}"
                )

            expected = participants_by_match.get(record.match_id)
            if expected is not None and {record.team_a, record.team_b} != set(expected):
                raise ValueError(
                    f"played result {record.match_id!r} conflicts with fixture participants: "
                    f"expected {sorted(expected)!r}, got "
                    f"{sorted((record.team_a, record.team_b))!r}"
                )

            stage = stage_by_match[record.match_id]
            if stage == "group" and record.advanced_team is not None:
                raise ValueError(
                    f"group match {record.match_id!r} cannot carry advanced_team "
                    f"({record.advanced_team!r}); group results never advance a side directly"
                )
            if stage != "group" and record.goals_a == record.goals_b and record.advanced_team is None:
                raise ValueError(
                    f"drawn knockout match {record.match_id!r} requires advanced_team: "
                    "exactly one side must advance after a 90-minute draw"
                )
            played[record.match_id] = record

        return cls(played={match_id: played[match_id] for match_id in sorted(played)})


def played_results_from_json(path: Path) -> tuple[PlayedMatchResult, ...]:
    """Parse a conditioned-results JSON document into validated played records.

    The document must contain a ``results`` list whose entries use only the
    contract keys (``match_id``, ``team_a``, ``team_b``, ``goals_a``,
    ``goals_b`` plus optional ``fair_play_a``, ``fair_play_b``,
    ``advanced_team``). Unknown keys fail loudly to prevent silent drift.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "results" not in payload:
        raise ValueError(f"conditioned results document must contain a 'results' list: {path}")

    allowed = set(_REQUIRED_RESULT_KEYS) | set(_OPTIONAL_RESULT_KEYS)
    records: list[PlayedMatchResult] = []
    for entry in payload["results"]:
        unknown_keys = sorted(set(entry) - allowed)
        if unknown_keys:
            raise ValueError(
                f"played result entry has unknown key(s) {unknown_keys!r}; allowed: {sorted(allowed)!r}"
            )
        missing_keys = sorted(set(_REQUIRED_RESULT_KEYS) - set(entry))
        if missing_keys:
            raise ValueError(f"played result entry is missing required key(s) {missing_keys!r}")
        records.append(PlayedMatchResult(**entry))
    return tuple(records)
