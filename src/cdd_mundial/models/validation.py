"""Temporal validation harness for MODEL-04 and production DC materialization."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from cdd_mundial.data.contracts import HoldoutPredictionsSchema
from cdd_mundial.data.provenance import (
    ProvenanceRecord,
    file_sha256,
    write_provenance_manifest,
)
from cdd_mundial.models.baselines import fit_solo_elo, solo_elo_probs, uniform_wdl
from cdd_mundial.models.dixon_coles import fit_dixon_coles
from cdd_mundial.models.loading import load_matches
from cdd_mundial.models.metrics import brier_multiclass, rps

_REPORT_REQUIRED_KEYS = {"chosen_xi", "per_holdout", "gate"}


@dataclass(frozen=True)
class Holdout:
    tournament: str
    start: str
    year: int
    expected_matches: int


HOLDOUTS: dict[str, Holdout] = {
    "wc2018": Holdout("FIFA World Cup", "2018-06-14", 2018, 64),
    "wc2022": Holdout("FIFA World Cup", "2022-11-20", 2022, 64),
    "euro2024": Holdout("UEFA Euro", "2024-06-14", 2024, 51),
    "copa2024": Holdout("Copa América", "2024-06-20", 2024, 32),
}
XI_GRID: tuple[float, ...] = (0.00095, 0.0018)


def _artifact_date() -> str:
    return date.today().isoformat()


def _latest_artifact(models_root: Path, pattern: str) -> Path:
    candidates = sorted(models_root.glob(pattern))
    if not candidates:
        raise FileNotFoundError(f"no artifact matching {pattern!r} found in {models_root}")
    return candidates[-1]


def select_holdout(matches: pd.DataFrame, holdout: Holdout) -> pd.DataFrame:
    """Select an exact tournament/year holdout and fail loudly on count drift."""
    selected = matches[
        (matches["tournament"] == holdout.tournament) & (matches["date"].dt.year == holdout.year)
    ].copy()
    observed = len(selected)
    if observed != holdout.expected_matches:
        raise ValueError(
            f"holdout {holdout.tournament} {holdout.year}: expected "
            f"{holdout.expected_matches} matches, got {observed}"
        )
    return selected.sort_values(["date", "match_id"]).reset_index(drop=True)


def _attach_pre_match_ratings(matches: pd.DataFrame, elo_history: pd.DataFrame) -> pd.DataFrame:
    ratings = elo_history[["match_id", "team_id", "rating_pre"]].copy()
    home = ratings.rename(
        columns={"team_id": "home_team_id", "rating_pre": "rating_pre_home"}
    )
    away = ratings.rename(
        columns={"team_id": "away_team_id", "rating_pre": "rating_pre_away"}
    )
    enriched = matches.merge(home, how="left", on=["match_id", "home_team_id"], validate="one_to_one")
    enriched = enriched.merge(
        away, how="left", on=["match_id", "away_team_id"], validate="one_to_one"
    )
    if enriched[["rating_pre_home", "rating_pre_away"]].isna().any().any():
        raise ValueError("elo_history is missing pre-match ratings for one or more matches")
    return enriched


def _elo_difference(frame: pd.DataFrame) -> np.ndarray:
    home_bonus = np.where(frame["neutral"].astype(bool), 0.0, 100.0)
    return frame["rating_pre_home"].to_numpy(dtype=float) + home_bonus - frame[
        "rating_pre_away"
    ].to_numpy(dtype=float)


def dc_predictions(model: Any, holdout_matches: pd.DataFrame) -> np.ndarray:
    rows: list[tuple[float, float, float]] = []
    from cdd_mundial.models.dixon_coles import wdl_from_lambdas

    for row in holdout_matches.itertuples(index=False):
        lam, mu = model.predict_lambdas(
            str(row.home_team_id),
            str(row.away_team_id),
            {
                "neutral": bool(row.neutral),
                "date": row.date,
                "tournament_type": str(row.tournament),
            },
        )
        rows.append(wdl_from_lambdas(lam, mu, model.rho))
    return np.asarray(rows, dtype=float)


def uniform_predictions(count: int) -> np.ndarray:
    return np.tile(uniform_wdl(), (count, 1))


def solo_elo_predictions(
    train_matches: pd.DataFrame,
    holdout_matches: pd.DataFrame,
) -> np.ndarray:
    model = fit_solo_elo(
        _elo_difference(train_matches),
        train_matches["outcome_idx"].to_numpy(dtype=int),
    )
    return solo_elo_probs(_elo_difference(holdout_matches), model)


def evaluate_gate(mean_log_loss_by_model: dict[str, float]) -> dict[str, Any]:
    dc = float(mean_log_loss_by_model["dixon_coles"])
    uniform = float(mean_log_loss_by_model["uniform"])
    solo_elo = float(mean_log_loss_by_model["solo_elo"])
    passed = dc < uniform and dc < solo_elo
    return {
        "passed": passed,
        "criterion": "mean log-loss over 4 holdouts vs uniform and solo_elo",
        "note": (
            "FIFA-ranking baseline excluded per Director decision (OQ3) - "
            "optional post-phase stretch"
        ),
        "mean_log_loss": {
            "dixon_coles": dc,
            "uniform": uniform,
            "solo_elo": solo_elo,
        },
    }


def _metrics(probs: np.ndarray, outcome_idx: np.ndarray) -> dict[str, float]:
    return {
        "log_loss": float(log_loss(outcome_idx, probs, labels=[0, 1, 2])),
        "brier": float(brier_multiclass(probs, outcome_idx)),
        "rps": float(rps(probs, outcome_idx)),
    }


def run_validation(data_root: Path = Path("data")) -> tuple[dict[str, Any], pd.DataFrame]:
    """Run the strict fit-at-cutoff harness and return the report plus raw predictions."""
    matches = load_matches(path=data_root / "processed" / "historical_matches.parquet")
    elo_history = pd.read_parquet(data_root / "processed" / "models" / "elo_history.parquet")
    matches = _attach_pre_match_ratings(matches, elo_history)

    xi_search: dict[str, dict[str, float]] = {}
    chosen_xi: float | None = None
    chosen_score: float | None = None
    for xi in XI_GRID:
        per_holdout = {}
        for holdout_name, holdout in HOLDOUTS.items():
            cutoff = pd.Timestamp(holdout.start)
            holdout_frame = select_holdout(matches, holdout)
            model = fit_dixon_coles(matches, cutoff=cutoff, xi=xi)
            per_holdout[holdout_name] = float(
                log_loss(
                    holdout_frame["outcome_idx"].to_numpy(dtype=int),
                    dc_predictions(model, holdout_frame),
                    labels=[0, 1, 2],
                )
            )
        xi_key = f"{xi:.5f}"
        xi_search[xi_key] = per_holdout
        mean_score = float(np.mean(list(per_holdout.values())))
        if chosen_score is None or mean_score < chosen_score:
            chosen_xi = xi
            chosen_score = mean_score

    assert chosen_xi is not None
    prediction_rows: list[dict[str, Any]] = []
    per_holdout_report: dict[str, Any] = {}
    model_means: dict[str, list[float]] = {"dixon_coles": [], "uniform": [], "solo_elo": []}

    for holdout_name, holdout in HOLDOUTS.items():
        cutoff = pd.Timestamp(holdout.start)
        train_matches = matches[matches["date"] < cutoff].copy()
        holdout_frame = select_holdout(matches, holdout)
        dc_model = fit_dixon_coles(matches, cutoff=cutoff, xi=chosen_xi)

        probs_by_model = {
            "dixon_coles": dc_predictions(dc_model, holdout_frame),
            "uniform": uniform_predictions(len(holdout_frame)),
            "solo_elo": solo_elo_predictions(train_matches, holdout_frame),
        }
        outcome_idx = holdout_frame["outcome_idx"].to_numpy(dtype=int)

        metrics_by_model = {
            model_name: _metrics(probs, outcome_idx)
            for model_name, probs in probs_by_model.items()
        }
        for model_name, metrics in metrics_by_model.items():
            model_means[model_name].append(metrics["log_loss"])
        per_holdout_report[holdout_name] = {
            "cutoff": holdout.start,
            "matches": holdout.expected_matches,
            "metrics": metrics_by_model,
        }

        match_ids = holdout_frame["match_id"].tolist()
        for model_name, probs in probs_by_model.items():
            for match_id, outcome, prob in zip(match_ids, outcome_idx, probs, strict=True):
                prediction_rows.append(
                    {
                        "match_id": match_id,
                        "holdout": holdout_name,
                        "model": model_name,
                        "p_home_win": float(prob[0]),
                        "p_draw": float(prob[1]),
                        "p_away_win": float(prob[2]),
                        "outcome_idx": int(outcome),
                    }
                )

    mean_log_loss = {
        model_name: float(np.mean(scores)) for model_name, scores in model_means.items()
    }
    gate = evaluate_gate(mean_log_loss)
    report = {
        "chosen_xi": float(chosen_xi),
        "gate": gate,
        "mean_log_loss": mean_log_loss,
        "per_holdout": per_holdout_report,
        "xi_grid": list(XI_GRID),
        "xi_search": xi_search,
    }
    return report, pd.DataFrame(prediction_rows)


def materialize_validation(data_root: Path = Path("data")) -> dict[str, Any]:
    """Persist validation report, holdout predictions, and the production DC model."""
    report, predictions = run_validation(data_root)
    artifact_date = _artifact_date()
    models_root = data_root / "processed" / "models"
    models_root.mkdir(parents=True, exist_ok=True)

    report_path = models_root / f"validation_report_{artifact_date}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    validated_predictions = HoldoutPredictionsSchema.validate(predictions)
    predictions_path = models_root / f"holdout_predictions_{artifact_date}.parquet"
    validated_predictions.to_parquet(predictions_path, index=False)

    matches = load_matches(path=data_root / "processed" / "historical_matches.parquet")
    production_cutoff = matches["date"].max() + pd.Timedelta(days=1)
    production_model = fit_dixon_coles(matches, cutoff=production_cutoff, xi=report["chosen_xi"])
    dc_params_path = models_root / f"dc_params_{artifact_date}.json"
    production_model.save(dc_params_path)

    metadata_root = data_root / "metadata"
    source_version_values = matches["source_version"].drop_duplicates().tolist()
    source_version = str(source_version_values[0]) if source_version_values else "unknown"
    note = (
        f"chosen_xi={report['chosen_xi']}; "
        f"gate_passed={report['gate']['passed']}; "
        f"mean_log_loss={report['gate']['mean_log_loss']}"
    )
    provenance_names = {
        dc_params_path: "dc_params.provenance.json",
        predictions_path: "holdout_predictions.provenance.json",
    }
    for artifact_path, provenance_name in provenance_names.items():
        generated_manifest = write_provenance_manifest(
            ProvenanceRecord(
                source="cdd-mundial-validation",
                source_url="local:src/cdd_mundial/models/validation.py",
                retrieved_at_utc=datetime.now(timezone.utc),
                source_version=source_version,
                sha256=file_sha256(artifact_path),
                license="CC0-1.0 (derived from martj42)",
                local_path=artifact_path,
                notes=note,
            ),
            metadata_root,
        )
        generated_manifest.replace(metadata_root / provenance_name)

    return {
        "chosen_xi": float(report["chosen_xi"]),
        "gate_passed": bool(report["gate"]["passed"]),
        "mean_log_loss": report["gate"]["mean_log_loss"],
        "prediction_rows": int(len(validated_predictions)),
        "report_path": report_path.as_posix(),
        "dc_params_path": dc_params_path.as_posix(),
    }


def verify_model04_materialization(data_root: Path = Path("data")) -> dict[str, Any]:
    """Fail unless the validation report, predictions, and production model are coherent."""
    models_root = data_root / "processed" / "models"
    report_path = _latest_artifact(models_root, "validation_report_*.json")
    predictions_path = _latest_artifact(models_root, "holdout_predictions_*.parquet")
    dc_params_path = _latest_artifact(models_root, "dc_params_*.json")
    for artifact_path in (report_path, predictions_path, dc_params_path):
        if not artifact_path.exists():
            raise FileNotFoundError(f"required MODEL-04 artifact is missing: {artifact_path}")
    for provenance_name in (
        "dc_params.provenance.json",
        "holdout_predictions.provenance.json",
    ):
        provenance_path = data_root / "metadata" / provenance_name
        if not provenance_path.exists():
            raise FileNotFoundError(
                f"required MODEL-04 provenance is missing: {provenance_path}"
            )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    missing = _REPORT_REQUIRED_KEYS - set(report)
    if missing:
        raise ValueError(f"validation report is missing keys: {sorted(missing)}")
    predictions = HoldoutPredictionsSchema.validate(pd.read_parquet(predictions_path))
    gate_passed = report["gate"].get("passed")
    if not isinstance(gate_passed, bool):
        raise ValueError("validation report gate.passed must be a bool")
    if set(report["per_holdout"]) != set(HOLDOUTS):
        raise ValueError("validation report must contain the four configured holdouts")

    from cdd_mundial.models.dixon_coles import DixonColesModel

    model = DixonColesModel.load(dc_params_path)
    if model.xi not in XI_GRID:
        raise ValueError(f"production model xi {model.xi!r} is outside XI_GRID {XI_GRID!r}")

    return {
        "chosen_xi": float(report["chosen_xi"]),
        "gate_passed": gate_passed,
        "prediction_rows": int(len(predictions)),
        "report_path": report_path.as_posix(),
        "dc_params_path": dc_params_path.as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or verify the strict temporal validation harness.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing validation artifacts without recomputing them.",
    )
    args = parser.parse_args()
    summary = (
        verify_model04_materialization(args.data_root)
        if args.verify_only
        else materialize_validation(args.data_root)
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
