"""End-to-end Phase 1 acceptance gates.

Covers every Phase 1 requirement with evidence derived from artifacts, never prose:

- DATA-01 historical match base (martj42, parquet + provenance)
- DATA-02 canonical 48-team identity table with full per-source coverage
- DATA-03 current Elo ratings snapshot covering every participant
- DATA-04 frozen official 2026 fixture (104 matches, 72 group games)
- DATA-05 de-margined market odds benchmark
- DOC-01 mandatory didactic notebook structure
- DOC-03 portfolio README and a public repo free of secrets and restricted data

When a generated artifact is intentionally absent (fixture-only CI on a fresh
clone, ``data/processed/`` is gitignored), the corresponding parser is validated
against the committed test fixtures instead, so the gate never silently passes.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

import test_notebooks as notebook_gates
from cdd_mundial.data.contracts import (
    EloRatingsSchema,
    HistoricalMatchesSchema,
    OddsSchema,
)
from cdd_mundial.data.identities import TeamResolver, build_coverage_report
from cdd_mundial.data.ingest_elo import TEAMS_URL, WORLD_URL, fetch_elo_snapshot
from cdd_mundial.data.ingest_fixture import load_fixture_2026
from cdd_mundial.data.ingest_martj42 import build_historical_matches
from cdd_mundial.data.ingest_odds import build_odds_benchmark

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
METADATA = ROOT / "data" / "metadata"
FIXTURES = ROOT / "tests" / "fixtures"
README = ROOT / "README.md"

ALL_SOURCES = ["martj42", "eloratings", "fifa", "fixture", "odds"]
ODDS_FIXTURE_CAPTURED_AT = datetime(2026, 6, 11, 23, 0, tzinfo=timezone.utc)

REQUIRED_README_SECTIONS = (
    "## Que es este proyecto",
    "## Estado del torneo y alcance",
    "## Arquitectura",
    "## Instalacion",
    "## Reproducibilidad",
    "## Data Sources and Licensing",
    "## Convenciones de resultados",
    "## Validacion",
    "## Roadmap",
)


@pytest.fixture(scope="module")
def resolver() -> TeamResolver:
    return TeamResolver.from_csv()


@pytest.fixture(scope="module")
def participants(resolver: TeamResolver) -> pd.Series:
    return resolver.teams.loc[resolver.teams["is_world_cup_2026"], "team_id"]


def _tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def test_data01_historical_match_base_is_valid(test_workspace: Path) -> None:
    """DATA-01: unified historical base in parquet with strict schema and provenance."""
    parquet_path = PROCESSED / "historical_matches.parquet"
    if parquet_path.exists():
        frame = HistoricalMatchesSchema.validate(pd.read_parquet(parquet_path))
        assert len(frame) >= 49_000, "materialized history lost rows"
        assert set(frame["source"]) == {"martj42"}
        manifest = METADATA / "historical_matches.parquet.provenance.json"
        assert manifest.exists(), "DATA-01 parquet must carry a provenance manifest"
        assert json.loads(manifest.read_text(encoding="utf-8"))["sha256"]
    else:
        # Fixture-only CI fallback: the builder must still produce schema-valid output.
        frame = build_historical_matches(
            FIXTURES / "martj42" / "results.csv",
            FIXTURES / "martj42" / "shootouts.csv",
            output_path=test_workspace / "historical_matches.parquet",
            source_version="ci-fixture",
        )
        assert not frame.empty
    assert frame["match_id"].is_unique
    # martj42 semantics: shootout winners are stored separately and always imply
    # a result reached after extra time; scores themselves are never modified.
    shootout_rows = frame["shootout_winner_team_id"].notna()
    assert shootout_rows.any(), "the dataset must retain shootout outcomes"
    assert frame.loc[shootout_rows, "result_after_extra_time"].all()


def test_data02_48_canonical_teams_resolve_in_every_source(
    resolver: TeamResolver,
    participants: pd.Series,
) -> None:
    """DATA-02: master team table covers all 48 participants in all five sources."""
    assert len(participants) == 48
    assert participants.is_unique
    report = build_coverage_report(participants, ALL_SOURCES, resolver)
    assert len(report) == 48 * len(ALL_SOURCES)
    unresolved = report.loc[~report["resolved"], ["team_id", "source"]]
    assert unresolved.empty, f"unresolved identity coverage:\n{unresolved.to_string(index=False)}"


def test_data03_current_elo_snapshot_covers_all_participants(
    participants: pd.Series,
    test_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    resolver: TeamResolver,
) -> None:
    """DATA-03: current eloratings.net snapshot resolves a rating for every participant.

    The custom Elo recomputation from the 49k-match history is the first Phase 2
    deliverable; this gate proves the ingested current snapshot is complete.
    """
    parquet_path = PROCESSED / "elo_current.parquet"
    if parquet_path.exists():
        frame = EloRatingsSchema.validate(pd.read_parquet(parquet_path))
        assert set(frame["team_id"]) == set(participants)
        assert len(frame) == 48
    else:
        # Fixture-only CI fallback: parse the committed TSV fixtures end to end.
        payloads = {
            WORLD_URL: (FIXTURES / "eloratings" / "World.tsv").read_bytes(),
            TEAMS_URL: (FIXTURES / "eloratings" / "en.teams.tsv").read_bytes(),
        }
        monkeypatch.setattr(
            "cdd_mundial.data.ingest_elo.fetch_bytes",
            lambda url: payloads[url],
        )
        subset_ids = ["argentina", "mexico", "canada"]
        subset = TeamResolver(
            resolver.teams[resolver.teams["team_id"].isin(subset_ids)].copy(),
            resolver.aliases[
                resolver.aliases["team_id"].isin(subset_ids)
                & resolver.aliases["source"].eq("eloratings")
            ].copy(),
        )
        frame = fetch_elo_snapshot(
            raw_root=test_workspace / "raw",
            metadata_root=test_workspace / "metadata",
            output_path=test_workspace / "elo_current.parquet",
            retrieved_at_utc=datetime(2026, 6, 11, tzinfo=timezone.utc),
            resolver=subset,
        )
        assert set(frame["team_id"]) == set(subset_ids)
    assert frame["team_id"].is_unique
    assert (frame["elo_rating"] > 0).all()


def test_data04_frozen_fixture_has_official_structure() -> None:
    """DATA-04: the committed fixture passes the full 2026 tournament contract."""
    fixture = load_fixture_2026(ROOT / "data" / "external" / "fixture_2026.csv")
    assert len(fixture) == 104
    group_matches = fixture[fixture["stage"] == "group"]
    assert len(group_matches) == 72
    assert sorted(group_matches["group"].unique()) == list("ABCDEFGHIJKL")
    assert group_matches[["home_team_id", "away_team_id"]].notna().all().all()


def test_data05_odds_benchmark_probabilities_are_demargined() -> None:
    """DATA-05: at least one valid three-way benchmark row with probabilities summing to 1."""
    parquet_path = PROCESSED / "odds_2026.parquet"
    if parquet_path.exists():
        frame = OddsSchema.validate(pd.read_parquet(parquet_path))
    else:
        # Fixture-only CI fallback: build from the committed provider payload fixture.
        events = json.loads((FIXTURES / "odds" / "odds.json").read_text(encoding="utf-8"))
        frame = build_odds_benchmark(
            events,
            fixture_path=ROOT / "data" / "external" / "fixture_2026.csv",
            captured_at_utc=ODDS_FIXTURE_CAPTURED_AT,
            output_path=None,
        )
    assert len(frame) >= 1
    assert (frame["market"] == "h2h").all()
    probability_sums = frame[["prob_home", "prob_draw", "prob_away"]].sum(axis=1)
    assert (probability_sums - 1.0).abs().max() <= 1e-9
    assert (frame["overround"] >= 1.0).all(), "raw implied probabilities must include margin"
    assert frame["match_id"].notna().all()


def test_doc01_phase1_notebook_enforces_didactic_structure() -> None:
    """DOC-01: markdown(What and why) -> code -> markdown(Interpretation) throughout."""
    notebook = notebook_gates.read_notebook(notebook_gates.PHASE1_NOTEBOOK)
    notebook_gates.assert_didactic_structure(notebook, notebook_gates.PHASE1_NOTEBOOK.name)
    code = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "code")
    assert "cdd_mundial.data" in code, "the notebook must import production functions"


def test_doc03_readme_documents_provenance_licensing_and_setup() -> None:
    """DOC-03: portfolio README explains setup, reproducibility, sources, and caveats."""
    text = README.read_text(encoding="utf-8")
    for section in REQUIRED_README_SECTIONS:
        assert section in text, f"README is missing required section {section!r}"
    assert "incluyen tiempo extra y excluyen los penales" in text
    assert "shootout_winner_team_id" in text
    assert "data/metadata" in text
    assert "SHA-256" in text
    assert "CC0" in text
    assert "data/raw/odds" in text
    assert "odds_provider_policy.json" in text
    assert "python -m pytest -q" in text
    assert "pip install -e" in text
    assert "3.11" in text and "3.12" in text
    assert "asesoría de apuestas" in text


def test_doc03_no_secrets_or_restricted_data_are_tracked() -> None:
    """DOC-03: the public repository contains no secrets and no prohibited raw data."""
    tracked = _tracked_files()
    assert ".env" not in tracked, "the local secrets file must never be committed"
    forbidden_prefixes = (
        "data/raw/odds/",
        "data/raw/eloratings/",
        "data/raw/restricted/",
        "data/processed/",
    )
    # D-18 (Phase 4): the canonical append-only live calibration ledger is
    # authoritative state that MUST be versioned for reproducibility, and is
    # explicitly re-included in .gitignore. It is small, generated-but-canonical,
    # carries no secrets or licensed raw data, and is required for every forecast
    # to be regenerable from versioned code — so it is the one sanctioned
    # exception to the blanket data/processed/ ban. The exemption is a single
    # explicit file path, keeping the gate intact for all other generated data.
    sanctioned_versioned_data = frozenset(
        {"data/processed/live/calibration/calibration_matches.parquet"}
    )
    offenders = [
        path
        for path in tracked
        if path.startswith(forbidden_prefixes)
        and path not in sanctioned_versioned_data
    ]
    assert not offenders, f"restricted or generated data is tracked: {offenders}"

    contents = {
        path: (ROOT / path).read_text(encoding="utf-8", errors="replace")
        for path in tracked
        if (ROOT / path).is_file()
    }
    for path, text in contents.items():
        for pattern in notebook_gates.SECRET_PATTERNS:
            assert pattern.search(text) is None, (
                f"{path}: tracked content matches secret pattern {pattern.pattern!r}"
            )

    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            value = line.split("=", 1)[1].strip().strip("\"'")
            if len(value) < 8:
                continue
            leaks = [path for path, text in contents.items() if value in text]
            assert not leaks, f"a local .env secret value appears in tracked files: {leaks}"
