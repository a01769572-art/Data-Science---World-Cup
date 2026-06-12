"""Reviewed tournament-to-K-factor classification for the World Football Elo update."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

K_CATEGORIES: dict[str, int] = {
    "wc": 60,
    "continental": 50,
    "qualifier_major": 40,
    "other": 30,
    "friendly": 20,
}


class UnknownTournamentError(LookupError):
    """Raised when a tournament string has no reviewed K-factor assignment."""


class TournamentKTable:
    """Resolve exact tournament strings to reviewed WFE K-factors or fail loudly."""

    def __init__(self, table: pd.DataFrame) -> None:
        required_columns = {"tournament", "k_category", "k_factor"}
        missing = required_columns - set(table.columns)
        if missing:
            raise ValueError(f"K-factor table is missing required columns: {sorted(missing)}")

        unknown_categories = sorted(set(table["k_category"]) - set(K_CATEGORIES))
        if unknown_categories:
            raise ValueError(f"K-factor table has unknown categories: {unknown_categories}")

        expected = table["k_category"].map(K_CATEGORIES)
        mismatched = table[table["k_factor"].astype(int) != expected]
        if not mismatched.empty:
            offenders = mismatched[["tournament", "k_category", "k_factor"]].to_dict("records")
            raise ValueError(f"K-factor values disagree with their category: {offenders}")

        duplicated = table[table["tournament"].duplicated()]["tournament"].tolist()
        if duplicated:
            raise ValueError(f"K-factor table has duplicate tournament strings: {duplicated}")

        self.table = table.reset_index(drop=True)
        self._k_by_tournament = dict(
            zip(self.table["tournament"], self.table["k_factor"].astype(int))
        )

    @classmethod
    def from_csv(
        cls,
        path: Path = Path("data/external/tournament_k_factors.csv"),
    ) -> TournamentKTable:
        """Load and validate the reviewed tournament K-factor registry."""
        return cls(pd.read_csv(path, dtype={"tournament": str, "k_category": str}))

    def k_factor(self, tournament: str) -> int:
        """Return the reviewed K-factor by exact string match or fail loudly."""
        try:
            return self._k_by_tournament[tournament]
        except KeyError:
            raise UnknownTournamentError(f"unknown tournament: {tournament!r}") from None
