"""Capability probe, provider policy, and three-way benchmark gates for odds ingestion."""

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cdd_mundial.data.identities import TeamResolver, UnknownTeamError
from cdd_mundial.data.ingest_odds import (
    MANUAL_TEMPLATE_COLUMNS,
    OddsValidationError,
    SourceUnavailableError,
    build_odds_benchmark,
    demargin_decimal_odds,
    probe_odds_provider,
)

FIXTURES = Path("tests/fixtures/odds")
POLICY_PATH = Path("data/metadata/odds_provider_policy.json")
TEMPLATE_PATH = Path("data/external/odds_2026_template.csv")
TEST_API_KEY = "TEST-ODDS-KEY-1234567890"
CAPTURED_AT = datetime(2026, 6, 11, 23, 0, tzinfo=timezone.utc)
REQUIRED_POLICY_FIELDS = (
    "provider",
    "sports_endpoint",
    "sport_key",
    "terms_url",
    "license_or_terms_summary",
    "raw_storage",
    "derived_storage",
    "probed_at_utc",
    "decision",
)


def _sports_payload() -> bytes:
    return (FIXTURES / "sports.json").read_bytes()


def _three_way_odds_payload() -> bytes:
    return json.dumps(
        [
            {
                "id": "evt-mex-rsa",
                "sport_key": "soccer_fifa_world_cup",
                "commence_time": "2026-06-11T19:00:00Z",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "last_update": "2026-06-11T12:00:00Z",
                        "markets": [
                            {
                                "key": "h2h",
                                "last_update": "2026-06-11T12:00:00Z",
                                "outcomes": [
                                    {"name": "Mexico", "price": 1.95},
                                    {"name": "Draw", "price": 3.4},
                                    {"name": "South Africa", "price": 4.4},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    ).encode("utf-8")


def _two_way_odds_payload() -> bytes:
    return json.dumps(
        [
            {
                "id": "evt-two-way",
                "sport_key": "soccer_fifa_world_cup",
                "commence_time": "2026-06-11T19:00:00Z",
                "home_team": "Mexico",
                "away_team": "South Africa",
                "bookmakers": [
                    {
                        "key": "pinnacle",
                        "title": "Pinnacle",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Mexico", "price": 1.4},
                                    {"name": "South Africa", "price": 2.9},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    ).encode("utf-8")


def _fetch_for(sports_payload: bytes, odds_payload: bytes):
    def fetch(url: str) -> bytes:
        assert f"apiKey={TEST_API_KEY}" in url
        if "/sports?" in url:
            return sports_payload
        return odds_payload

    return fetch


def test_probe_locates_active_world_cup_sport_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODDS_API_KEY", TEST_API_KEY)

    result = probe_odds_provider(fetch=_fetch_for(_sports_payload(), _three_way_odds_payload()))

    assert result["provider"] == "the-odds-api"
    assert result["sport_key"] == "soccer_fifa_world_cup"
    assert result["market"] == "h2h"
    assert result["three_way_event_count"] == 1
    assert result["probed_at_utc"].endswith("Z")


def test_probe_result_never_contains_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODDS_API_KEY", TEST_API_KEY)

    result = probe_odds_provider(fetch=_fetch_for(_sports_payload(), _three_way_odds_payload()))

    assert TEST_API_KEY not in json.dumps(result)


def test_probe_requires_environment_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODDS_API_KEY", raising=False)

    def fail_fetch(url: str) -> bytes:
        raise AssertionError("no request may be issued without a configured key")

    with pytest.raises(SourceUnavailableError, match="ODDS_API_KEY"):
        probe_odds_provider(fetch=fail_fetch)


def test_probe_rejects_missing_world_cup_competition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODDS_API_KEY", TEST_API_KEY)
    sports_without_world_cup = json.dumps(
        [
            {
                "key": "soccer_epl",
                "group": "Soccer",
                "title": "EPL",
                "active": True,
                "has_outrights": False,
            },
            {
                "key": "soccer_fifa_world_cup_winner",
                "group": "Soccer",
                "title": "FIFA World Cup Winner",
                "active": True,
                "has_outrights": True,
            },
        ]
    ).encode("utf-8")

    with pytest.raises(SourceUnavailableError, match="World Cup"):
        probe_odds_provider(fetch=_fetch_for(sports_without_world_cup, _three_way_odds_payload()))


def test_probe_rejects_two_way_market(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODDS_API_KEY", TEST_API_KEY)

    with pytest.raises(SourceUnavailableError, match="three-outcome"):
        probe_odds_provider(fetch=_fetch_for(_sports_payload(), _two_way_odds_payload()))


def test_probe_error_redacts_secret_from_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ODDS_API_KEY", TEST_API_KEY)

    def failing_fetch(url: str) -> bytes:
        raise RuntimeError(f"401 Client Error for url {url}")

    with pytest.raises(SourceUnavailableError) as exc_info:
        probe_odds_provider(fetch=failing_fetch)

    assert TEST_API_KEY not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_policy_file_records_provider_terms_and_storage() -> None:
    policy_text = POLICY_PATH.read_text(encoding="utf-8")
    policy = json.loads(policy_text)

    for field in REQUIRED_POLICY_FIELDS:
        assert field in policy, f"missing policy field: {field}"
    assert policy["decision"].strip()
    assert policy["raw_storage"] in {"ignored", "committed"}
    assert policy["terms_url"].startswith("https://")
    assert policy["probed_at_utc"].endswith("Z")
    assert TEST_API_KEY not in policy_text
    assert "apiKey=" not in policy_text.replace("without apiKey", "")


def test_policy_raw_odds_path_is_gitignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/raw/odds/" in gitignore


@pytest.fixture(scope="module")
def resolver() -> TeamResolver:
    return TeamResolver.from_csv()


def _benchmark_events() -> list[dict]:
    return json.loads((FIXTURES / "odds.json").read_text(encoding="utf-8"))


def test_demargin_returns_normalized_probabilities() -> None:
    probabilities = demargin_decimal_odds([2.0, 3.0, 4.0])

    booksum = 1 / 2.0 + 1 / 3.0 + 1 / 4.0
    expected = [(1 / 2.0) / booksum, (1 / 3.0) / booksum, (1 / 4.0) / booksum]
    assert probabilities == pytest.approx(expected)
    assert abs(sum(probabilities) - 1.0) <= 1e-9


@pytest.mark.parametrize(
    "prices",
    [
        [1.0, 3.0, 4.0],
        [0.0, 3.0, 4.0],
        [-2.0, 3.0, 4.0],
        [math.inf, 3.0, 4.0],
        [math.nan, 3.0, 4.0],
        [2.0, 3.0],
        [2.0, 3.0, 4.0, 5.0],
    ],
)
def test_demargin_rejects_invalid_prices(prices: list[float]) -> None:
    with pytest.raises(OddsValidationError):
        demargin_decimal_odds(prices)


def test_benchmark_links_three_way_quotes_to_canonical_fixture(
    resolver: TeamResolver, test_workspace: Path
) -> None:
    output_path = test_workspace / "odds_2026.parquet"

    frame = build_odds_benchmark(
        _benchmark_events(),
        resolver=resolver,
        captured_at_utc=CAPTURED_AT,
        output_path=output_path,
    )

    assert output_path.exists()
    assert len(frame) == 3
    assert set(frame["match_id"]) == {"WC26-002", "WC26-003"}
    assert frame["match_id"].notna().all()
    assert frame["home_team_id"].notna().all()
    assert frame["away_team_id"].notna().all()
    assert (frame["market"] == "h2h").all()
    assert frame["provider_update_utc"].str.endswith("Z").all()

    korea = frame[frame["match_id"] == "WC26-002"]
    assert set(korea["home_team_id"]) == {"south-korea"}
    assert set(korea["away_team_id"]) == {"czechia"}
    pinnacle = korea[korea["bookmaker"] == "pinnacle"].iloc[0]
    assert pinnacle["price_home"] == pytest.approx(2.69)
    assert pinnacle["price_away"] == pytest.approx(3.06)
    assert pinnacle["price_draw"] == pytest.approx(3.1)

    lay_prices = {3.2, 2.75, 3.25}
    quoted = set(frame["price_home"]) | set(frame["price_draw"]) | set(frame["price_away"])
    assert not lay_prices & quoted, "exchange lay prices must never enter the benchmark"


def test_benchmark_probabilities_sum_to_one_with_positive_margin(
    resolver: TeamResolver,
) -> None:
    frame = build_odds_benchmark(
        _benchmark_events(),
        resolver=resolver,
        captured_at_utc=CAPTURED_AT,
        output_path=None,
    )

    probability_sum = frame["prob_home"] + frame["prob_draw"] + frame["prob_away"]
    assert ((probability_sum - 1.0).abs() <= 1e-9).all()
    raw_sum = frame["prob_home_raw"] + frame["prob_draw_raw"] + frame["prob_away_raw"]
    assert (frame["overround"] == raw_sum).all()
    assert (frame["overround"] > 1.0).all(), "bookmaker booksum should carry a margin"


def test_benchmark_rejects_two_way_market(resolver: TeamResolver) -> None:
    events = _benchmark_events()
    market = events[0]["bookmakers"][0]["markets"][0]
    market["outcomes"] = market["outcomes"][:2]

    with pytest.raises(OddsValidationError, match="three-way"):
        build_odds_benchmark(
            events, resolver=resolver, captured_at_utc=CAPTURED_AT, output_path=None
        )


def test_benchmark_rejects_duplicate_draw_outcomes(resolver: TeamResolver) -> None:
    events = _benchmark_events()
    market = events[0]["bookmakers"][0]["markets"][0]
    market["outcomes"] = [
        {"name": "Czech Republic", "price": 3.06},
        {"name": "Draw", "price": 3.1},
        {"name": "Draw", "price": 3.2},
    ]

    with pytest.raises(OddsValidationError, match="three-way"):
        build_odds_benchmark(
            events, resolver=resolver, captured_at_utc=CAPTURED_AT, output_path=None
        )


def test_benchmark_rejects_bookmaker_without_back_market(resolver: TeamResolver) -> None:
    events = _benchmark_events()
    bookmaker = events[0]["bookmakers"][1]
    bookmaker["markets"] = [
        market for market in bookmaker["markets"] if market["key"] == "h2h_lay"
    ]

    with pytest.raises(OddsValidationError, match="no h2h back market"):
        build_odds_benchmark(
            events, resolver=resolver, captured_at_utc=CAPTURED_AT, output_path=None
        )


def test_benchmark_rejects_unmatched_fixture_pairing(resolver: TeamResolver) -> None:
    events = copy.deepcopy(_benchmark_events()[:1])
    event = events[0]
    event["home_team"] = "Mexico"
    event["away_team"] = "Brazil"
    event["bookmakers"][0]["markets"][0]["outcomes"] = [
        {"name": "Mexico", "price": 3.4},
        {"name": "Brazil", "price": 2.1},
        {"name": "Draw", "price": 3.3},
    ]
    event["bookmakers"] = event["bookmakers"][:1]

    with pytest.raises(OddsValidationError, match="fixture"):
        build_odds_benchmark(
            events, resolver=resolver, captured_at_utc=CAPTURED_AT, output_path=None
        )


def test_benchmark_rejects_unknown_provider_team_name(resolver: TeamResolver) -> None:
    events = copy.deepcopy(_benchmark_events()[:1])
    event = events[0]
    event["home_team"] = "Czechoslovakia XI"
    event["bookmakers"] = event["bookmakers"][:1]
    event["bookmakers"][0]["markets"][0]["outcomes"][0]["name"] = "Czechoslovakia XI"

    with pytest.raises(UnknownTeamError):
        build_odds_benchmark(
            events, resolver=resolver, captured_at_utc=CAPTURED_AT, output_path=None
        )


def test_benchmark_rejects_stale_quotes(resolver: TeamResolver) -> None:
    events = copy.deepcopy(_benchmark_events()[:1])
    bookmaker = events[0]["bookmakers"][0]
    bookmaker["markets"][0]["last_update"] = "2026-06-09T22:00:00Z"
    events[0]["bookmakers"] = [bookmaker]

    with pytest.raises(OddsValidationError, match="stale"):
        build_odds_benchmark(
            events, resolver=resolver, captured_at_utc=CAPTURED_AT, output_path=None
        )


def test_manual_template_has_canonical_contract() -> None:
    header = TEMPLATE_PATH.read_text(encoding="utf-8").splitlines()[0]

    assert header.startswith("provider,bookmaker,event_id,match_id")
    assert tuple(header.split(",")) == MANUAL_TEMPLATE_COLUMNS


def test_benchmark_accepts_manual_csv_fallback(
    resolver: TeamResolver, test_workspace: Path
) -> None:
    manual_path = test_workspace / "manual_odds.csv"
    header = ",".join(MANUAL_TEMPLATE_COLUMNS)
    row = (
        "manual,authored,evt-manual-1,WC26-001,2026-06-11T19:00:00Z,2026-06-11T18:00:00Z,"
        "South Africa,Mexico,4.4,3.4,1.95"
    )
    manual_path.write_text(f"{header}\n{row}\n", encoding="utf-8")
    output_path = test_workspace / "manual_odds.parquet"

    frame = build_odds_benchmark(
        manual_csv_path=manual_path,
        resolver=resolver,
        captured_at_utc=datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc),
        output_path=output_path,
    )

    assert output_path.exists()
    row_out = frame.iloc[0]
    assert row_out["match_id"] == "WC26-001"
    assert row_out["home_team_id"] == "mexico"
    assert row_out["away_team_id"] == "south-africa"
    assert row_out["price_home"] == pytest.approx(1.95)
    assert row_out["price_away"] == pytest.approx(4.4)
    total = row_out["prob_home"] + row_out["prob_draw"] + row_out["prob_away"]
    assert abs(total - 1.0) <= 1e-9


def test_benchmark_rejects_mismatched_manual_match_id(
    resolver: TeamResolver, test_workspace: Path
) -> None:
    manual_path = test_workspace / "manual_odds.csv"
    header = ",".join(MANUAL_TEMPLATE_COLUMNS)
    row = (
        "manual,authored,evt-manual-2,WC26-002,2026-06-11T19:00:00Z,2026-06-11T18:00:00Z,"
        "Mexico,South Africa,1.95,3.4,4.4"
    )
    manual_path.write_text(f"{header}\n{row}\n", encoding="utf-8")

    with pytest.raises(OddsValidationError, match="declares match_id"):
        build_odds_benchmark(
            manual_csv_path=manual_path,
            resolver=resolver,
            captured_at_utc=datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc),
            output_path=None,
        )
