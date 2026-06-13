"""Tournament simulation: conditional state, FIFA 2026 rules, vectorized Monte Carlo."""

from cdd_mundial.simulation.state import (
    PlayedMatchResult,
    TournamentState,
    played_results_from_json,
)

__all__ = ["PlayedMatchResult", "TournamentState", "played_results_from_json"]
