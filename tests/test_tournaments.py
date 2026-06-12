from pathlib import Path

import pandas as pd
import pytest

from cdd_mundial.models.tournaments import TournamentKTable, UnknownTournamentError


def test_world_cup_maps_to_k_60() -> None:
    table = TournamentKTable.from_csv()

    assert table.k_factor("FIFA World Cup") == 60


def test_friendly_maps_to_k_20() -> None:
    table = TournamentKTable.from_csv()

    assert table.k_factor("Friendly") == 20


def test_world_cup_qualification_maps_to_k_40() -> None:
    table = TournamentKTable.from_csv()

    assert table.k_factor("FIFA World Cup qualification") == 40


def test_copa_america_exact_utf8_string_maps_to_k_50() -> None:
    table = TournamentKTable.from_csv()

    assert table.k_factor("Copa América") == 50


def test_unknown_tournament_fails_loudly() -> None:
    table = TournamentKTable.from_csv()

    with pytest.raises(UnknownTournamentError, match="unknown tournament"):
        table.k_factor("Atlantis Invitational")


@pytest.mark.data_acceptance
def test_every_real_tournament_string_resolves_to_a_k_factor() -> None:
    tournaments = pd.read_parquet(
        Path("data/processed/historical_matches.parquet")
    )["tournament"].unique()
    table = TournamentKTable.from_csv()

    for tournament in tournaments:
        assert table.k_factor(tournament) in {20, 30, 40, 50, 60}
