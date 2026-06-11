from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from cdd_mundial.data.contracts import EloRatingsSchema
from cdd_mundial.data.http import fetch_bytes
from cdd_mundial.data.identities import TeamResolver, build_coverage_report
from cdd_mundial.data.ingest_elo import (
    TEAMS_URL,
    WORLD_URL,
    fetch_elo_snapshot,
)


FIXTURE_ROOT = Path("tests/fixtures/eloratings")


class FakeResponse:
    def __init__(
        self,
        content: bytes,
        status_code: int = 200,
        content_type: str = "text/tab-separated-values",
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)


class FakeSession:
    def __init__(self, results: list[object]) -> None:
        self.results = iter(results)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, tuple[float, float]]] = []

    def get(self, url: str, timeout: tuple[float, float]) -> FakeResponse:
        self.calls.append((url, timeout))
        result = next(self.results)
        if isinstance(result, BaseException):
            raise result
        return result


def test_fetch_bytes_sets_defaults_and_returns_payload(monkeypatch) -> None:
    session = FakeSession([FakeResponse(b"a\tb\n")])
    monkeypatch.setattr("cdd_mundial.data.http.requests.Session", lambda: session)

    assert fetch_bytes(WORLD_URL, backoff_seconds=0) == b"a\tb\n"
    assert session.calls == [(WORLD_URL, (5, 20))]
    assert session.headers["User-Agent"].startswith("CDD-MUNDIAL/1.0")


@pytest.mark.parametrize(
    "results",
    [
        [requests.Timeout(), FakeResponse(b"a\tb\n")],
        [FakeResponse(b"error", status_code=500), FakeResponse(b"a\tb\n")],
    ],
)
def test_fetch_bytes_retries_transient_failures(monkeypatch, results) -> None:
    session = FakeSession(results)
    monkeypatch.setattr("cdd_mundial.data.http.requests.Session", lambda: session)

    assert fetch_bytes(WORLD_URL, retries=1, backoff_seconds=0) == b"a\tb\n"
    assert len(session.calls) == 2


def test_fetch_bytes_rejects_html_for_tsv(monkeypatch) -> None:
    session = FakeSession([FakeResponse(b"<html>blocked</html>", content_type="text/html")])
    monkeypatch.setattr("cdd_mundial.data.http.requests.Session", lambda: session)

    with pytest.raises(ValueError, match="HTML response rejected"):
        fetch_bytes(WORLD_URL, backoff_seconds=0)


def _three_team_resolver() -> TeamResolver:
    resolver = TeamResolver.from_csv()
    team_ids = ["argentina", "mexico", "canada"]
    teams = resolver.teams[resolver.teams["team_id"].isin(team_ids)].copy()
    aliases = resolver.aliases[
        resolver.aliases["team_id"].isin(team_ids)
        & resolver.aliases["source"].eq("eloratings")
    ].copy()
    return TeamResolver(teams, aliases)


def test_fetch_elo_snapshot_maps_aliases_and_writes_provenance(
    test_workspace: Path,
    monkeypatch,
) -> None:
    payloads = {
        WORLD_URL: (FIXTURE_ROOT / "World.tsv").read_bytes(),
        TEAMS_URL: (FIXTURE_ROOT / "en.teams.tsv").read_bytes(),
    }
    monkeypatch.setattr(
        "cdd_mundial.data.ingest_elo.fetch_bytes",
        lambda url: payloads[url],
    )
    retrieved_at = datetime(2026, 6, 11, 18, tzinfo=timezone.utc)
    output_path = test_workspace / "data" / "processed" / "elo_current.parquet"

    built = fetch_elo_snapshot(
        raw_root=test_workspace / "data" / "raw" / "eloratings",
        metadata_root=test_workspace / "data" / "metadata",
        output_path=output_path,
        retrieved_at_utc=retrieved_at,
        resolver=_three_team_resolver(),
    )

    EloRatingsSchema.validate(pd.read_parquet(output_path))
    assert built["team_id"].tolist() == ["argentina", "canada", "mexico"]
    assert built["elo_rating"].tolist() == [2115.0, 1744.0, 1812.0]
    assert built["team_id"].is_unique
    assert built["rating_date_utc"].eq("2026-06-11T18:00:00Z").all()
    for filename in ("World.tsv", "en.teams.tsv"):
        manifest = test_workspace / "data" / "metadata" / f"{filename}.provenance.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["source"] == "eloratings"
        assert payload["retrieved_at_utc"] == "2026-06-11T18:00:00Z"


def test_world_rows_without_team_codes_are_ignored(test_workspace: Path, monkeypatch) -> None:
    world = (FIXTURE_ROOT / "World.tsv").read_bytes() + b"135\t135\t\t1303\n"
    monkeypatch.setattr(
        "cdd_mundial.data.ingest_elo.fetch_bytes",
        lambda url: world if url == WORLD_URL else (FIXTURE_ROOT / "en.teams.tsv").read_bytes(),
    )

    built = fetch_elo_snapshot(
        raw_root=test_workspace / "raw",
        metadata_root=test_workspace / "metadata",
        output_path=test_workspace / "elo.parquet",
        retrieved_at_utc=datetime(2026, 6, 11, tzinfo=timezone.utc),
        resolver=_three_team_resolver(),
    )

    assert len(built) == 3


def test_fetch_elo_snapshot_rejects_non_numeric_rating(test_workspace: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "cdd_mundial.data.ingest_elo.fetch_bytes",
        lambda url: (
            b"1\t1\tAR\tnot-a-rating\n"
            if url == WORLD_URL
            else (FIXTURE_ROOT / "en.teams.tsv").read_bytes()
        ),
    )

    with pytest.raises(ValueError, match="Unable to parse string"):
        fetch_elo_snapshot(
            raw_root=test_workspace / "raw",
            metadata_root=test_workspace / "metadata",
            output_path=test_workspace / "elo.parquet",
            retrieved_at_utc=datetime(2026, 6, 11, tzinfo=timezone.utc),
            resolver=_three_team_resolver(),
        )


def test_all_48_participants_have_reviewed_elo_aliases() -> None:
    resolver = TeamResolver.from_csv()
    participants = resolver.teams.loc[
        resolver.teams["is_world_cup_2026"], "team_id"
    ]
    report = build_coverage_report(participants, ["eloratings"], resolver)

    assert len(report) == 48
    assert report["resolved"].all()
