"""Tournament simulation: conditional state, FIFA 2026 rules, vectorized Monte Carlo."""

from cdd_mundial.simulation.engine import (
    SimulationResult,
    simulate_tournaments,
)
from cdd_mundial.simulation.knockout import (
    advance_probability,
    post_draw_advance_probability,
    sample_post_draw_advancers,
)
from cdd_mundial.simulation.outputs import (
    advancement_table,
    group_position_table,
)
from cdd_mundial.simulation.rules_fifa import (
    calculate_group_table,
    rank_best_thirds,
    rank_group,
)
from cdd_mundial.simulation.slots import (
    load_official_third_place_mapping,
    resolve_slot,
    resolve_third_place_assignments,
)
from cdd_mundial.simulation.state import (
    PlayedMatchResult,
    TournamentState,
    played_results_from_json,
)

__all__ = [
    "PlayedMatchResult",
    "SimulationResult",
    "TournamentState",
    "advance_probability",
    "advancement_table",
    "calculate_group_table",
    "group_position_table",
    "load_official_third_place_mapping",
    "rank_best_thirds",
    "rank_group",
    "played_results_from_json",
    "post_draw_advance_probability",
    "resolve_slot",
    "resolve_third_place_assignments",
    "sample_post_draw_advancers",
    "simulate_tournaments",
]
