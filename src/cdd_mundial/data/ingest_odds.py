"""Capability probe and canonical benchmark construction for World Cup market odds."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from cdd_mundial.data.contracts import OddsSchema
from cdd_mundial.data.http import fetch_bytes
from cdd_mundial.data.identities import TeamResolver

PROVIDER = "the-odds-api"
BASE_URL = "https://api.the-odds-api.com/v4"
ODDS_SOURCE = "odds"
DRAW_OUTCOME = "Draw"
FIXTURE_PATH = Path("data/external/fixture_2026.csv")
ODDS_PARQUET_PATH = Path("data/processed/odds_2026.parquet")
RAW_ODDS_DIR = Path("data/raw/odds")
MANUAL_TEMPLATE_COLUMNS = (
    "provider",
    "bookmaker",
    "event_id",
    "match_id",
    "commence_time_utc",
    "provider_update_utc",
    "home_team",
    "away_team",
    "price_home",
    "price_draw",
    "price_away",
)
BENCHMARK_COLUMNS = (
    "provider",
    "bookmaker",
    "event_id",
    "match_id",
    "captured_at_utc",
    "commence_time_utc",
    "provider_update_utc",
    "home_team_id",
    "away_team_id",
    "market",
    "price_home",
    "price_draw",
    "price_away",
    "prob_home_raw",
    "prob_draw_raw",
    "prob_away_raw",
    "overround",
    "prob_home",
    "prob_draw",
    "prob_away",
)
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


class OddsValidationError(ValueError):
    """Raised when a market quote violates the canonical three-way benchmark contract."""


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


def demargin_decimal_odds(prices: Sequence[float]) -> list[float]:
    """Convert three decimal odds into probabilities via multiplicative normalization.

    Each implied probability is the inverse decimal price divided by the booksum, which
    removes the bookmaker margin proportionally across the three outcomes.
    """
    values = [float(price) for price in prices]
    if len(values) != 3:
        raise OddsValidationError(
            f"exactly three decimal prices are required, got {len(values)}"
        )
    for value in values:
        if not math.isfinite(value) or value <= 1.0:
            raise OddsValidationError(
                f"decimal prices must be finite and greater than 1.0, got {value!r}"
            )
    inverse = [1.0 / value for value in values]
    booksum = sum(inverse)
    return [probability / booksum for probability in inverse]


def _parse_utc(value: object, field: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp or fail with field context."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise OddsValidationError(f"invalid UTC timestamp in {field}: {value!r}") from None
    if parsed.tzinfo is None:
        raise OddsValidationError(f"timestamp in {field} must be timezone-aware: {value!r}")
    return parsed.astimezone(timezone.utc)


def _format_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_price(value: object, context: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise OddsValidationError(f"non-numeric decimal price in {context}: {value!r}") from None


def _load_fixture_index(fixture_path: Path) -> dict[frozenset[str], list[dict]]:
    """Index canonical fixture rows with assigned teams by their unordered team pair."""
    fixture = pd.read_csv(fixture_path, dtype=str, keep_default_na=False).replace("", None)
    index: dict[frozenset[str], list[dict]] = {}
    for row in fixture.to_dict("records"):
        home_id, away_id = row["home_team_id"], row["away_team_id"]
        if home_id is None or away_id is None:
            continue
        entry = {
            "match_id": row["match_id"],
            "home_team_id": home_id,
            "away_team_id": away_id,
            "kickoff": _parse_utc(row["kickoff_utc"], f"fixture {row['match_id']} kickoff_utc"),
        }
        index.setdefault(frozenset((home_id, away_id)), []).append(entry)
    return index


def _quotes_from_events(events: list[dict]) -> list[dict]:
    """Extract per-bookmaker three-way back quotes from provider event JSON.

    Markets other than ``h2h`` (lay, outrights, totals) are never consumed; a bookmaker
    entry that offers no ``h2h`` back market at all is rejected explicitly.
    """
    quotes: list[dict] = []
    for event in events:
        if not isinstance(event, dict):
            raise OddsValidationError("provider event payload entries must be JSON objects")
        event_id = str(event.get("id") or "")
        home_name = str(event.get("home_team") or "")
        away_name = str(event.get("away_team") or "")
        commence = event.get("commence_time")
        if not event_id or not home_name or not away_name or not commence:
            raise OddsValidationError(
                f"provider event is missing id, team names, or commence time: {event_id!r}"
            )
        expected = sorted([home_name, away_name, DRAW_OUTCOME])
        event_quotes: list[dict] = []
        for bookmaker in event.get("bookmakers") or []:
            bookmaker_key = str(bookmaker.get("key") or "unknown")
            context = f"event {event_id} bookmaker {bookmaker_key}"
            back_markets = [
                market
                for market in (bookmaker.get("markets") or [])
                if market.get("key") == "h2h"
            ]
            if not back_markets:
                raise OddsValidationError(
                    f"{context} offers no h2h back market; lay, outright, or other "
                    "market types are rejected"
                )
            for market in back_markets:
                outcomes = market.get("outcomes") or []
                names = [str(outcome.get("name", "")) for outcome in outcomes]
                if sorted(names) != expected:
                    raise OddsValidationError(
                        f"{context} does not quote an exact home/draw/away three-way "
                        f"market: {names}"
                    )
                update = market.get("last_update") or bookmaker.get("last_update")
                if not update:
                    raise OddsValidationError(
                        f"{context} h2h quote carries no provider update time"
                    )
                price_by_name = {
                    str(outcome["name"]): outcome.get("price") for outcome in outcomes
                }
                event_quotes.append(
                    {
                        "provider": PROVIDER,
                        "bookmaker": bookmaker_key,
                        "event_id": event_id,
                        "match_id": None,
                        "commence_time_utc": commence,
                        "provider_update_utc": update,
                        "home_name": home_name,
                        "away_name": away_name,
                        "price_home": price_by_name[home_name],
                        "price_draw": price_by_name[DRAW_OUTCOME],
                        "price_away": price_by_name[away_name],
                    }
                )
        if not event_quotes:
            raise OddsValidationError(f"event {event_id} has no bookmaker h2h quotes")
        quotes.extend(event_quotes)
    return quotes


def _quotes_from_manual_csv(manual_csv_path: Path) -> list[dict]:
    """Read manually authored quotes following the canonical fallback template."""
    frame = pd.read_csv(manual_csv_path, dtype=str, keep_default_na=False).replace("", None)
    missing = [column for column in MANUAL_TEMPLATE_COLUMNS if column not in frame.columns]
    if missing:
        raise OddsValidationError(f"manual odds CSV is missing required columns: {missing}")
    if frame.empty:
        raise OddsValidationError(f"manual odds CSV has no quote rows: {manual_csv_path}")
    required = tuple(
        column for column in MANUAL_TEMPLATE_COLUMNS if column != "provider_update_utc"
    )
    quotes: list[dict] = []
    for position, row in enumerate(frame.to_dict("records")):
        empty = [column for column in required if row[column] is None]
        if empty:
            raise OddsValidationError(
                f"manual odds CSV row {position + 2} is missing values: {empty}"
            )
        quotes.append(
            {
                "provider": row["provider"],
                "bookmaker": row["bookmaker"],
                "event_id": row["event_id"],
                "match_id": row["match_id"],
                "commence_time_utc": row["commence_time_utc"],
                "provider_update_utc": row["provider_update_utc"],
                "home_name": row["home_team"],
                "away_name": row["away_team"],
                "price_home": row["price_home"],
                "price_draw": row["price_draw"],
                "price_away": row["price_away"],
            }
        )
    return quotes


def build_odds_benchmark(
    events: list[dict] | None = None,
    *,
    manual_csv_path: Path | None = None,
    fixture_path: Path = FIXTURE_PATH,
    resolver: TeamResolver | None = None,
    captured_at_utc: datetime | None = None,
    output_path: Path | None = ODDS_PARQUET_PATH,
    commence_tolerance: timedelta = timedelta(hours=12),
    max_update_age: timedelta = timedelta(hours=24),
) -> pd.DataFrame:
    """Build the canonical de-margined three-way benchmark from provider JSON or manual CSV.

    Raw provider payloads must already live at the policy-approved ignored path
    (``data/raw/odds/``); this function only consumes decoded events and writes the
    derived, redistribution-safe benchmark parquet.
    """
    if (events is None) == (manual_csv_path is None):
        raise ValueError("provide exactly one of events or manual_csv_path")

    captured_at = (captured_at_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    active_resolver = resolver or TeamResolver.from_csv()
    fixture_index = _load_fixture_index(fixture_path)
    quotes = (
        _quotes_from_events(events)
        if events is not None
        else _quotes_from_manual_csv(manual_csv_path)  # type: ignore[arg-type]
    )

    rows: list[dict] = []
    for quote in quotes:
        context = f"event {quote['event_id']} bookmaker {quote['bookmaker']}"
        home_id = active_resolver.resolve(ODDS_SOURCE, quote["home_name"])
        away_id = active_resolver.resolve(ODDS_SOURCE, quote["away_name"])
        commence = _parse_utc(quote["commence_time_utc"], f"{context} commence time")

        candidates = fixture_index.get(frozenset((home_id, away_id)), [])
        linked = [
            candidate
            for candidate in candidates
            if abs(candidate["kickoff"] - commence) <= commence_tolerance
        ]
        if not linked:
            raise OddsValidationError(
                f"{context} ({home_id} vs {away_id} at {_format_utc(commence)}) does not "
                "match any canonical fixture row within the commence-time tolerance"
            )
        if len(linked) > 1:
            matched_ids = [candidate["match_id"] for candidate in linked]
            raise OddsValidationError(f"{context} ambiguously matches fixtures: {matched_ids}")
        fixture_row = linked[0]
        if quote["match_id"] is not None and quote["match_id"] != fixture_row["match_id"]:
            raise OddsValidationError(
                f"{context} declares match_id {quote['match_id']!r} but its teams and "
                f"commence time resolve to {fixture_row['match_id']!r}"
            )

        provider_update = quote["provider_update_utc"]
        if provider_update is not None:
            update_at = _parse_utc(provider_update, f"{context} provider update time")
            if captured_at - update_at > max_update_age:
                raise OddsValidationError(
                    f"{context} quote is stale: provider update {_format_utc(update_at)} "
                    f"is more than {max_update_age} before capture "
                    f"{_format_utc(captured_at)}"
                )
            provider_update = _format_utc(update_at)

        price_by_team_id = {
            home_id: _as_price(quote["price_home"], context),
            away_id: _as_price(quote["price_away"], context),
        }
        price_home = price_by_team_id[fixture_row["home_team_id"]]
        price_away = price_by_team_id[fixture_row["away_team_id"]]
        price_draw = _as_price(quote["price_draw"], context)

        prob_home, prob_draw, prob_away = demargin_decimal_odds(
            [price_home, price_draw, price_away]
        )
        raw_home, raw_draw, raw_away = (
            1.0 / price_home,
            1.0 / price_draw,
            1.0 / price_away,
        )
        rows.append(
            {
                "provider": quote["provider"],
                "bookmaker": quote["bookmaker"],
                "event_id": quote["event_id"],
                "match_id": fixture_row["match_id"],
                "captured_at_utc": _format_utc(captured_at),
                "commence_time_utc": _format_utc(commence),
                "provider_update_utc": provider_update,
                "home_team_id": fixture_row["home_team_id"],
                "away_team_id": fixture_row["away_team_id"],
                "market": "h2h",
                "price_home": price_home,
                "price_draw": price_draw,
                "price_away": price_away,
                "prob_home_raw": raw_home,
                "prob_draw_raw": raw_draw,
                "prob_away_raw": raw_away,
                "overround": raw_home + raw_draw + raw_away,
                "prob_home": prob_home,
                "prob_draw": prob_draw,
                "prob_away": prob_away,
            }
        )

    if not rows:
        raise OddsValidationError(
            "no valid three-way quotes were produced; refusing to write an empty benchmark"
        )

    frame = pd.DataFrame(rows, columns=list(BENCHMARK_COLUMNS))
    validated = OddsSchema.validate(frame)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        validated.to_parquet(output_path, index=False)
    return validated


def _latest_raw_odds_capture(raw_dir: Path) -> Path:
    """Return the newest captured provider payload under the policy-approved raw path."""
    captures = sorted(raw_dir.glob("*_odds_*.json"))
    if not captures:
        raise SourceUnavailableError(
            f"no captured odds payloads under {raw_dir}; run the authenticated probe "
            "capture first"
        )
    return captures[-1]


def _capture_time_from_name(path: Path) -> datetime | None:
    """Recover the capture timestamp from a ``YYYYmmddTHHMMSSZ_*`` capture filename."""
    stamp = path.name.split("_", 1)[0]
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the canonical de-margined World Cup odds benchmark."
    )
    parser.add_argument(
        "--raw-payload",
        type=Path,
        default=None,
        help="Captured provider odds JSON; defaults to the newest capture in data/raw/odds/.",
    )
    parser.add_argument(
        "--manual-csv",
        type=Path,
        default=None,
        help="Manual fallback CSV following data/external/odds_2026_template.csv.",
    )
    parser.add_argument("--output", type=Path, default=ODDS_PARQUET_PATH)
    args = parser.parse_args()

    if args.manual_csv is not None:
        frame = build_odds_benchmark(manual_csv_path=args.manual_csv, output_path=args.output)
        source = args.manual_csv.as_posix()
    else:
        payload_path = args.raw_payload or _latest_raw_odds_capture(RAW_ODDS_DIR)
        events = json.loads(payload_path.read_text(encoding="utf-8"))
        frame = build_odds_benchmark(
            events,
            output_path=args.output,
            captured_at_utc=_capture_time_from_name(payload_path),
        )
        source = payload_path.as_posix()

    print(
        json.dumps(
            {
                "source": source,
                "rows": int(len(frame)),
                "matches": int(frame["match_id"].nunique()),
                "bookmakers": int(frame["bookmaker"].nunique()),
                "max_overround": round(float(frame["overround"].max()), 6),
                "output": args.output.as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
