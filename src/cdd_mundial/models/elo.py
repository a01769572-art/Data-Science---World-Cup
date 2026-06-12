"""Custom World Football Elo recomputed sequentially over the full match history."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cdd_mundial.data.contracts import EloHistorySchema, EloRatingsSchema
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    file_sha256,
    write_provenance_manifest,
)
from cdd_mundial.models.loading import load_matches
from cdd_mundial.models.tournaments import TournamentKTable

INITIAL_RATING = 1000.0
HOME_BONUS = 100.0

_HISTORY_COLUMNS = [
    "match_id",
    "date",
    "team_id",
    "opponent_id",
    "rating_pre",
    "rating_post",
    "k_factor",
]


def expected_score(elo_a: float, elo_b: float, home_bonus_a: float) -> float:
    """Return We for team A under the WFE logistic curve, with A's home bonus inside dr."""
    dr = (elo_a + home_bonus_a) - elo_b
    return 1.0 / (10 ** (-dr / 400.0) + 1.0)


def margin_factor(goal_diff: int, elo_winner: float, elo_loser: float) -> float:
    """Margin-of-victory multiplier: FiveThirtyEight NFL Elo variant, adapted with a draw branch.

    Attribution: ``log(|gd|+1) * 2.2 / ((elo_winner - elo_loser) * 0.001 + 2.2)`` is the
    FiveThirtyEight MOV multiplier (NOT the eloratings.net discrete G table). Draws return
    1.0 explicitly: the raw formula would give log(1)=0 and freeze ratings on ~23% of
    historical matches (pitfall 1).
    """
    if goal_diff == 0:  # empate: factor 1.0 — la formula 538 daria 0 y congelaria 23% de partidos
        return 1.0
    autocorr = 2.2 / ((elo_winner - elo_loser) * 0.001 + 2.2)
    return np.log(abs(goal_diff) + 1.0) * autocorr


def elo_update(
    elo_a: float,
    elo_b: float,
    score_a: int,
    score_b: int,
    k: float,
    home_bonus_a: float,
    drew_after_et: bool = False,
) -> tuple[float, float]:
    """Return post-match ratings for (A, B); shootout/extra-time decisions count as draws.

    ``drew_after_et=True`` (shootout or extra time, D-05 + WFE) forces ``w_a=0.5`` with
    goal difference 0 and margin factor 1.0, regardless of the recorded FT+ET score.
    """
    if drew_after_et:
        w_a, gd = 0.5, 0
    else:
        w_a = 1.0 if score_a > score_b else (0.5 if score_a == score_b else 0.0)
        gd = abs(score_a - score_b)
    we_a = expected_score(elo_a, elo_b, home_bonus_a)
    if gd == 0:
        g = 1.0
    elif w_a == 1.0:
        g = margin_factor(gd, elo_a, elo_b)
    else:
        g = margin_factor(gd, elo_b, elo_a)
    delta = k * g * (w_a - we_a)
    return elo_a + delta, elo_b - delta


def recompute_elo(matches: pd.DataFrame, k_table: TournamentKTable) -> pd.DataFrame:
    """Sequentially recompute Elo from INITIAL_RATING over ``load_matches`` output.

    The +100 home bonus applies to ``home_team_id`` whenever ``neutral`` is False across
    the WHOLE history (Director decision on OQ1, WFE reconciliation); the MEX/USA/CAN
    restriction from D-02 applies only to 2026 prediction, not to this recomputation.
    Returns a long-format frame with two rows per match (home and away perspectives).
    """
    ratings: dict[str, float] = {}
    rows: list[tuple[str, str, str, str, float, float, int]] = []
    for row in matches.itertuples(index=False):
        home = str(row.home_team_id)
        away = str(row.away_team_id)
        elo_home = ratings.get(home, INITIAL_RATING)
        elo_away = ratings.get(away, INITIAL_RATING)
        home_bonus_a = HOME_BONUS if not row.neutral else 0.0
        drew_after_et = bool(row.result_after_extra_time) or pd.notna(
            row.shootout_winner_team_id
        )
        k = k_table.k_factor(str(row.tournament))
        new_home, new_away = elo_update(
            elo_home,
            elo_away,
            int(row.home_score),
            int(row.away_score),
            float(k),
            home_bonus_a,
            drew_after_et=drew_after_et,
        )
        date_str = row.date.strftime("%Y-%m-%d")
        rows.append((str(row.match_id), date_str, home, away, elo_home, new_home, k))
        rows.append((str(row.match_id), date_str, away, home, elo_away, new_away, k))
        ratings[home] = new_home
        ratings[away] = new_away
    return pd.DataFrame(rows, columns=_HISTORY_COLUMNS)


def ratings_asof(history: pd.DataFrame, date: pd.Timestamp) -> dict[str, float]:
    """Return the latest rating_post strictly BEFORE ``date`` per team; default 1000.0."""
    match_dates = pd.to_datetime(history["date"], errors="raise")
    prior = history.loc[match_dates < date]
    latest = prior.sort_values("date", kind="stable").groupby("team_id")["rating_post"].last()
    return defaultdict(lambda: INITIAL_RATING, latest.to_dict())


def snapshot_ratings(history: pd.DataFrame, source_version: str) -> pd.DataFrame:
    """Return the current EloRatingsSchema snapshot: last rating_post per team."""
    ordered = history.sort_values("date", kind="stable")
    latest = ordered.groupby("team_id", as_index=False)["rating_post"].last()
    snapshot = pd.DataFrame(
        {
            "team_id": latest["team_id"],
            "elo_rating": latest["rating_post"].astype(float),
        }
    )
    snapshot["rank"] = (
        snapshot["elo_rating"].rank(method="dense", ascending=False).astype(int)
    )
    max_date = str(ordered["date"].max())
    snapshot["rating_date_utc"] = f"{max_date}T00:00:00Z"
    snapshot["source"] = "cdd-mundial-recompute"
    snapshot["source_version"] = source_version
    return snapshot.sort_values("rank", kind="stable").reset_index(drop=True)


def _write_artifact_provenance(
    artifact_path: Path,
    source_version: str,
    input_path: Path,
    metadata_root: Path,
) -> None:
    write_provenance_manifest(
        ProvenanceRecord(
            source="cdd-mundial-elo-recompute",
            source_url="local:src/cdd_mundial/models/elo.py",
            retrieved_at_utc=datetime.now(timezone.utc),
            source_version=source_version,
            sha256=file_sha256(artifact_path),
            license="CC0-1.0 (derived from martj42)",
            local_path=artifact_path,
            notes=(
                "Recomputed WFE-style Elo from historical_matches.parquet "
                f"sha256={file_sha256(input_path)}"
            ),
        ),
        metadata_root,
    )


def materialize_elo(data_root: Path = Path("data")) -> dict[str, float | int | str]:
    """Recompute, validate, and serialize the Elo history and snapshot with provenance."""
    input_path = data_root / "processed" / "historical_matches.parquet"
    matches = load_matches(path=input_path)
    versions = matches["source_version"].drop_duplicates().tolist()
    if len(versions) != 1:
        raise ValueError(f"historical parquet must contain one source version: {versions}")
    source_version = str(versions[0])

    history = recompute_elo(matches, TournamentKTable.from_csv())
    validated_history = EloHistorySchema.validate(history)
    models_root = data_root / "processed" / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    history_path = models_root / "elo_history.parquet"
    validated_history.to_parquet(history_path, index=False)

    snapshot = EloRatingsSchema.validate(snapshot_ratings(validated_history, source_version))
    ratings_path = models_root / "elo_ratings.parquet"
    snapshot.to_parquet(ratings_path, index=False)

    metadata_root = data_root / "metadata"
    for artifact_path in (history_path, ratings_path):
        _write_artifact_provenance(artifact_path, source_version, input_path, metadata_root)

    top = snapshot.iloc[0]
    return {
        "matches": int(validated_history["match_id"].nunique()),
        "teams": int(snapshot["team_id"].nunique()),
        "top_team": str(top["team_id"]),
        "top_rating": float(top["elo_rating"]),
    }


def verify_elo_materialization(data_root: Path = Path("data")) -> dict[str, float | int | str]:
    """Fail unless both Elo artifacts exist, validate, and cover enough teams."""
    models_root = data_root / "processed" / "models"
    history_path = models_root / "elo_history.parquet"
    ratings_path = models_root / "elo_ratings.parquet"
    for path in (history_path, ratings_path):
        if not path.exists():
            raise FileNotFoundError(f"required MODEL-01 artifact is missing: {path}")

    history = EloHistorySchema.validate(pd.read_parquet(history_path))
    snapshot = EloRatingsSchema.validate(pd.read_parquet(ratings_path))
    team_count = int(snapshot["team_id"].nunique())
    if team_count < 300:
        raise ValueError(f"Elo snapshot covers too few teams: {team_count} < 300")

    top = snapshot.sort_values("rank", kind="stable").iloc[0]
    return {
        "matches": int(history["match_id"].nunique()),
        "teams": team_count,
        "top_team": str(top["team_id"]),
        "top_rating": float(top["elo_rating"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize and verify the recomputed Elo.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing artifacts without recomputing.",
    )
    args = parser.parse_args()
    summary = (
        verify_elo_materialization(args.data_root)
        if args.verify_only
        else materialize_elo(args.data_root)
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
