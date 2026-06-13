"""Tournament simulation: conditional state, FIFA 2026 rules, vectorized Monte Carlo."""

from cdd_mundial.simulation.knockout import (
    advance_probability,
    post_draw_advance_probability,
    sample_post_draw_advancers,
)
from cdd_mundial.simulation.state import (
    PlayedMatchResult,
    TournamentState,
    played_results_from_json,
)

__all__ = [
    "PlayedMatchResult",
    "TournamentState",
    "advance_probability",
    "played_results_from_json",
    "post_draw_advance_probability",
    "sample_post_draw_advancers",
]
