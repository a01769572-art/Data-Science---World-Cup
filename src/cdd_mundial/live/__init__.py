"""Live publication layer: canonical results ingestion and daily pipeline (Phase 4)."""

from cdd_mundial.live.calibration import (
    CANONICAL_LEDGER_PATH,
    append_ledger,
    build_ledger_rows,
    cumulative_metrics,
    derive_realized_outcomes,
    freeze_market_benchmark,
    publish_calibration,
    register_frozen_benchmark,
)
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
from cdd_mundial.live.ml_selection import (
    BASELINE_FAMILY,
    UPGRADE_FAMILY,
    DualPublication,
    PublicationDecision,
    build_dual_publication,
    decide_publication,
)
from cdd_mundial.live.pipeline import OFFICIAL_ORDER, run_official, verify_official
from cdd_mundial.live.predict import upcoming_match_predictions
from cdd_mundial.live.report import render_snapshot_report
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
    "BASELINE_FAMILY",
    "CANONICAL_LEDGER_PATH",
    "CANONICAL_RESULTS_PATH",
    "LIVE_RESULTS_COLUMNS",
    "OFFICIAL_ORDER",
    "UPGRADE_FAMILY",
    "CalibrationLedgerSchema",
    "DiscrepancyError",
    "DualPublication",
    "FrozenBenchmarkSchema",
    "IncompleteResultsError",
    "LiveResultsSchema",
    "OverrideToken",
    "PublicationDecision",
    "SnapshotWriter",
    "UpcomingPredictionsSchema",
    "append_ledger",
    "build_dual_publication",
    "build_ledger_rows",
    "build_live_state",
    "decide_publication",
    "compute_input_fingerprint",
    "cumulative_metrics",
    "derive_realized_outcomes",
    "freeze_market_benchmark",
    "load_live_results",
    "map_live_rows_to_canonical",
    "materialize_live_training",
    "publish_calibration",
    "register_frozen_benchmark",
    "render_snapshot_report",
    "run_official",
    "select_model_artifact",
    "upcoming_match_predictions",
    "verify_official",
]
