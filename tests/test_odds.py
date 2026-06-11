"""Capability probe, provider policy, and secret-handling gates for odds ingestion."""

import json
from pathlib import Path

import pytest

from cdd_mundial.data.ingest_odds import SourceUnavailableError, probe_odds_provider

FIXTURES = Path("tests/fixtures/odds")
POLICY_PATH = Path("data/metadata/odds_provider_policy.json")
TEST_API_KEY = "TEST-ODDS-KEY-1234567890"
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
