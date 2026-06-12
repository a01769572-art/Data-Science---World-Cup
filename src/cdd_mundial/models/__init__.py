"""Baseline structural models: dynamic Elo, Dixon-Coles, metrics, validation."""

from cdd_mundial.models.dixon_coles import DixonColesModel, predict_lambdas  # contrato D-09 (Phase 3)

__all__ = ["DixonColesModel", "predict_lambdas"]
