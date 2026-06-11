"""Capability probe and canonical benchmark construction for World Cup market odds."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timezone

from cdd_mundial.data.http import fetch_bytes

PROVIDER = "the-odds-api"
BASE_URL = "https://api.the-odds-api.com/v4"
_REDACTED = "***REDACTED***"
_EXCLUDED_COMPETITION_TERMS = (
    "women",
    "qualif",
    "club",
    "u17",
    "u-17",
    "u20",
    "u-20",
    "u21",
    "u-21",
    "youth",
)


class SourceUnavailableError(RuntimeError):
    """Raised when no probed provider can supply valid three-way World Cup odds."""


def redact_secret(text: str, secret: str | None) -> str:
    """Remove every occurrence of a secret value from human-readable text."""
    if not secret:
        return text
    return text.replace(secret, _REDACTED)


def _require_api_key() -> str:
    """Read the provider key from the environment only; never from files or arguments."""
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    if not api_key:
        raise SourceUnavailableError(
            "ODDS_API_KEY is not set in the environment; load it from the ignored local "
            ".env before probing the odds provider"
        )
    return api_key


def _fetch_json(url: str, api_key: str, fetch: Callable[[str], bytes]) -> object:
    """Fetch and decode JSON, redacting the key from any failure detail."""
    try:
        payload = fetch(url)
    except Exception as error:  # noqa: BLE001 - every failure detail must be redacted
        message = redact_secret(f"{type(error).__name__}: {error}", api_key)
        raise SourceUnavailableError(f"odds provider request failed: {message}") from None
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SourceUnavailableError(
            f"odds provider returned a non-JSON response: {redact_secret(url, api_key)}"
        ) from None


def _select_world_cup_sport(sports: list[dict]) -> dict:
    """Locate exactly one active men's World Cup soccer sport with non-outright markets."""
    candidates = []
    for sport in sports:
        if not isinstance(sport, dict):
            continue
        searchable = f"{sport.get('title', '')} {sport.get('key', '')}".lower()
        if (
            sport.get("group") == "Soccer"
            and sport.get("active") is True
            and not sport.get("has_outrights", False)
            and "world cup" in str(sport.get("title", "")).lower()
            and not any(term in searchable for term in _EXCLUDED_COMPETITION_TERMS)
        ):
            candidates.append(sport)

    if not candidates:
        raise SourceUnavailableError(
            "no active three-way FIFA World Cup soccer competition is exposed by the "
            "provider sports endpoint"
        )
    if len(candidates) > 1:
        keys = sorted(str(candidate.get("key")) for candidate in candidates)
        raise SourceUnavailableError(f"ambiguous World Cup sport keys returned: {keys}")
    return candidates[0]


def _event_has_three_way_market(event: dict) -> bool:
    """Accept only an exact home/draw/away three-outcome ``h2h`` market."""
    home_team = str(event.get("home_team", ""))
    away_team = str(event.get("away_team", ""))
    if not home_team or not away_team:
        return False
    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            outcomes = market.get("outcomes") or []
            names = [str(outcome.get("name", "")) for outcome in outcomes]
            if len(outcomes) == 3 and {home_team, away_team, "Draw"} == set(names):
                return True
    return False


def probe_odds_provider(
    *,
    base_url: str = BASE_URL,
    regions: str = "eu",
    fetch: Callable[[str], bytes] = fetch_bytes,
    probed_at_utc: datetime | None = None,
) -> dict:
    """Verify the provider exposes World Cup 2026 three-way odds before any ingestion.

    The API key is read exclusively from the ``ODDS_API_KEY`` environment variable and
    never appears in the returned metadata or in raised error messages.
    """
    api_key = _require_api_key()
    probed_at = (probed_at_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)

    sports_url = f"{base_url}/sports?apiKey={api_key}"
    sports = _fetch_json(sports_url, api_key, fetch)
    if not isinstance(sports, list):
        raise SourceUnavailableError("provider sports endpoint did not return a JSON list")

    sport = _select_world_cup_sport(sports)
    sport_key = str(sport["key"])

    odds_url = (
        f"{base_url}/sports/{sport_key}/odds"
        f"?apiKey={api_key}&regions={regions}&markets=h2h&oddsFormat=decimal"
    )
    events = _fetch_json(odds_url, api_key, fetch)
    if not isinstance(events, list) or not events:
        raise SourceUnavailableError(
            f"provider returned no h2h events for sport key {sport_key!r}"
        )

    three_way_events = sum(
        1 for event in events if isinstance(event, dict) and _event_has_three_way_market(event)
    )
    if three_way_events == 0:
        raise SourceUnavailableError(
            f"sport {sport_key!r} returned events but no exact home/draw/away "
            "three-outcome h2h market; two-way or outright quotes are rejected"
        )

    return {
        "provider": PROVIDER,
        "sports_endpoint": f"{base_url}/sports",
        "sport_key": sport_key,
        "sport_title": str(sport.get("title", "")),
        "market": "h2h",
        "event_count": len(events),
        "three_way_event_count": three_way_events,
        "probed_at_utc": probed_at.isoformat().replace("+00:00", "Z"),
    }
