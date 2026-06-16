"""Baseline structural models: dynamic Elo, Dixon-Coles, metrics, validation."""

from cdd_mundial.models.dixon_coles import DixonColesModel, predict_lambdas  # contrato D-09 (Phase 3)
from cdd_mundial.models.ml_features import (  # contrato ML-01 (Phase 5)
    ML_FEATURE_COLUMNS,
    MIN_PRIOR_MATCHES,
    build_ml_dataset,
)

__all__ = [
    "DixonColesModel",
    "predict_lambdas",
    "ML_FEATURE_COLUMNS",
    "MIN_PRIOR_MATCHES",
    "build_ml_dataset",
]
