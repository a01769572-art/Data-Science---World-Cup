"""Baseline structural models: dynamic Elo, Dixon-Coles, metrics, validation."""

from cdd_mundial.models.dixon_coles import DixonColesModel, predict_lambdas  # contrato D-09 (Phase 3)
from cdd_mundial.models.ml_features import (  # contrato ML-01 (Phase 5)
    ML_FEATURE_COLUMNS,
    MIN_PRIOR_MATCHES,
    build_ml_dataset,
)
from cdd_mundial.models.ml_xgboost import MulticlassXGBoost  # contrato ML-02 (Phase 5)
from cdd_mundial.models.ml_calibration import (  # contrato ML-04 (Phase 5)
    MulticlassCalibrator,
    select_best_calibration,
)
from cdd_mundial.models.ml_validation import (  # contrato ML-03 (Phase 5)
    evaluate_ml_gate,
    run_ml_comparison,
)

__all__ = [
    "DixonColesModel",
    "predict_lambdas",
    "ML_FEATURE_COLUMNS",
    "MIN_PRIOR_MATCHES",
    "build_ml_dataset",
    "MulticlassXGBoost",
    "MulticlassCalibrator",
    "select_best_calibration",
    "evaluate_ml_gate",
    "run_ml_comparison",
]
