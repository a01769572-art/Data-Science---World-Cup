"""Performance gates for the vectorized tournament engine (SIM-02).

The 10,000-tournament run is a hard gate: it must finish under 60 seconds with
warm imports excluded from timing. The 100,000-tournament run is measured and
reported but does not block the phase if the 10k gate passes.

Both tests are marked ``performance`` so the per-task quick suite excludes them
while the phase gate includes them.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.simulation.engine import simulate_tournaments
from cdd_mundial.simulation.state import TournamentState

FIXTURE_PATH = Path("data/external/fixture_2026.csv")


def _flat_predictor(team_a: str, team_b: str, ctx: dict) -> tuple[float, float]:
    return 1.3, 1.3


@pytest.fixture(scope="module")
def warm_fixture() -> "object":
    fixture = load_fixture_2026(FIXTURE_PATH)
    # Warm the engine once so imports/compilation are excluded from timing.
    simulate_tournaments(
        fixture=fixture,
        state=TournamentState(played={}),
        predict_lambdas=_flat_predictor,
        n_sims=8,
        seed=0,
    )
    return fixture


@pytest.mark.performance
def test_10000_tournaments_under_60_seconds(warm_fixture) -> None:
    fixture = warm_fixture
    durations = []
    for run in range(3):
        start = time.perf_counter()
        simulate_tournaments(
            fixture=fixture,
            state=TournamentState(played={}),
            predict_lambdas=_flat_predictor,
            n_sims=10_000,
            seed=run,
        )
        elapsed = time.perf_counter() - start
        durations.append(elapsed)
        assert elapsed < 75.0, f"run {run} exceeded the 75 s ceiling: {elapsed:.2f} s"
    durations.sort()
    median = durations[1]
    assert median < 60.0, f"median 10k runtime {median:.2f} s must be under 60 s"


@pytest.mark.performance
def test_100000_tournament_target_report(warm_fixture, capsys) -> None:
    fixture = warm_fixture
    start = time.perf_counter()
    simulate_tournaments(
        fixture=fixture,
        state=TournamentState(played={}),
        predict_lambdas=_flat_predictor,
        n_sims=100_000,
        seed=123,
    )
    elapsed = time.perf_counter() - start
    with capsys.disabled():
        print(f"\n[100k target] 100,000 tournaments elapsed {elapsed:.2f} s")
    # The 100k run is a measured target; it never blocks the phase here.
    assert elapsed > 0.0
