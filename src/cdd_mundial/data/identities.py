"""Deterministic, source-keyed football team identity resolution."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path

import pandas as pd

from cdd_mundial.data.contracts import TeamAliasesSchema, TeamsSchema


class UnknownTeamError(LookupError):
    """Raised when no reviewed alias resolves a source team name."""


class AmbiguousTeamError(LookupError):
    """Raised when multiple reviewed aliases are valid for one lookup."""


def _as_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


class TeamResolver:
    """Resolve exact source names to immutable canonical team IDs."""

    def __init__(self, teams: pd.DataFrame, aliases: pd.DataFrame) -> None:
        self.teams = TeamsSchema.validate(teams.copy())
        self.aliases = TeamAliasesSchema.validate(aliases.copy())

        unknown_ids = sorted(set(self.aliases["team_id"]) - set(self.teams["team_id"]))
        if unknown_ids:
            raise ValueError(f"alias rows reference unknown team IDs: {unknown_ids}")

    @classmethod
    def from_csv(
        cls,
        teams_path: Path = Path("data/external/teams.csv"),
        aliases_path: Path = Path("data/external/team_aliases.csv"),
    ) -> TeamResolver:
        """Load and validate the reviewed identity registry."""
        return cls(
            pd.read_csv(teams_path, dtype=str, keep_default_na=False).replace("", None),
            pd.read_csv(aliases_path, dtype=str, keep_default_na=False).replace("", None),
        )

    def _matches(
        self,
        source: str,
        source_name: str,
        on_date: str | date | None = None,
    ) -> pd.DataFrame:
        matches = self.aliases[
            (self.aliases["source"] == source) & (self.aliases["source_name"] == source_name)
        ]
        if on_date is None:
            return matches

        target = _as_date(on_date)
        valid_from = matches["valid_from"].map(_as_date)
        valid_to = matches["valid_to"].map(
            lambda value: date.max if pd.isna(value) else _as_date(value)
        )
        return matches[(valid_from <= target) & (target <= valid_to)]

    def resolve(
        self,
        source: str,
        source_name: str,
        on_date: str | date | None = None,
    ) -> str:
        """Return the exact canonical ID or fail loudly."""
        matches = self._matches(source, source_name, on_date)
        if matches.empty:
            suffix = f" on {on_date}" if on_date is not None else ""
            raise UnknownTeamError(f"unknown team alias: {source!r}/{source_name!r}{suffix}")
        if len(matches) > 1:
            raise AmbiguousTeamError(
                f"ambiguous team alias: {source!r}/{source_name!r} matched {len(matches)} rows"
            )
        return str(matches.iloc[0]["team_id"])


def build_coverage_report(
    required_team_ids: Iterable[str],
    sources: Iterable[str],
    resolver: TeamResolver | None = None,
) -> pd.DataFrame:
    """Return one explicit coverage row for every required team/source pair."""
    active_resolver = resolver or TeamResolver.from_csv()
    known_ids = set(active_resolver.teams["team_id"])
    rows: list[dict[str, object]] = []

    for team_id in required_team_ids:
        if team_id not in known_ids:
            raise UnknownTeamError(f"unknown canonical team ID: {team_id!r}")
        for source in sources:
            aliases = active_resolver.aliases[
                (active_resolver.aliases["team_id"] == team_id)
                & (active_resolver.aliases["source"] == source)
            ]
            if len(aliases) == 1:
                rows.append(
                    {
                        "team_id": team_id,
                        "source": source,
                        "resolved": True,
                        "source_name": aliases.iloc[0]["source_name"],
                        "reason": "reviewed alias",
                    }
                )
            elif aliases.empty:
                rows.append(
                    {
                        "team_id": team_id,
                        "source": source,
                        "resolved": False,
                        "source_name": None,
                        "reason": "missing reviewed alias",
                    }
                )
            else:
                rows.append(
                    {
                        "team_id": team_id,
                        "source": source,
                        "resolved": False,
                        "source_name": None,
                        "reason": "multiple reviewed aliases",
                    }
                )

    return pd.DataFrame(
        rows,
        columns=["team_id", "source", "resolved", "source_name", "reason"],
    )
