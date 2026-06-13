"""Live publication layer: canonical results ingestion and daily pipeline (Phase 4)."""

from cdd_mundial.live.contracts import (
    CalibrationLedgerSchema,
    FrozenBenchmarkSchema,
    LiveResultsSchema,
    UpcomingPredictionsSchema,
)
from cdd_mundial.live.materialization import (
    compute_input_fingerprint,
    map_live_rows_to_canonical,
    materialize_live_training,
    select_model_artifact,
)
from cdd_mundial.live.pipeline import OFFICIAL_ORDER, run_official, verify_official
from cdd_mundial.live.predict import upcoming_match_predictions
from cdd_mundial.live.results import (
    CANONICAL_RESULTS_PATH,
    LIVE_RESULTS_COLUMNS,
    DiscrepancyError,
    IncompleteResultsError,
    OverrideToken,
    build_live_state,
    load_live_results,
)
from cdd_mundial.live.snapshots import SnapshotWriter

__all__ = [
    "CANONICAL_RESULTS_PATH",
    "LIVE_RESULTS_COLUMNS",
    "OFFICIAL_ORDER",
    "CalibrationLedgerSchema",
    "DiscrepancyError",
    "FrozenBenchmarkSchema",
    "IncompleteResultsError",
    "LiveResultsSchema",
    "OverrideToken",
    "SnapshotWriter",
    "UpcomingPredictionsSchema",
    "build_live_state",
    "compute_input_fingerprint",
    "load_live_results",
    "map_live_rows_to_canonical",
    "materialize_live_training",
    "run_official",
    "select_model_artifact",
    "upcoming_match_predictions",
    "verify_official",
]
