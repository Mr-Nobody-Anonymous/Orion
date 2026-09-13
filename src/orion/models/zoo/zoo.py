"""Institutional Machine Learning Model Zoo.

Standardized wrappers for Gradient Boosted Trees, Sequence Neural Networks,
and Bayesian Ensemble models.
Lives in the Foundation plane (under models).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence


class ModelFamily(str, Enum):
    GRADIENT_BOOSTED_TREES = "gbt"
    TEMPORAL_TRANSFORMER = "transformer"
    LSTM_RECURRENT = "lstm"
    LINEAR_RIDGE = "ridge"
    BAYESIAN_ENSEMBLE = "ensemble"


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    model_name: str
    expected_return: float
    directional_probability_up: float
    confidence: float
    features_used: tuple[str, ...] = ()


class ModelZooEngine:
    """Ensemble prediction and performance metrics evaluator."""

    @staticmethod
    def calculate_information_coefficient(
        predictions: Sequence[float],
        realized_returns: Sequence[float],
    ) -> float:
        """Computes Pearson Information Coefficient (IC) between predictions and realized returns."""
        n = len(predictions)
        if n < 5 or n != len(realized_returns):
            return 0.0

        mean_p = sum(predictions) / n
        mean_r = sum(realized_returns) / n

        var_p = sum((p - mean_p) ** 2 for p in predictions)
        var_r = sum((r - mean_r) ** 2 for r in realized_returns)
        cov = sum((p - mean_p) * (r - mean_r) for p, r in zip(predictions, realized_returns))

        denom = math.sqrt(var_p * var_r)
        return cov / denom if denom > 0 else 0.0

    @staticmethod
    def calculate_directional_accuracy(
        predictions: Sequence[float],
        realized_returns: Sequence[float],
    ) -> float:
        """Hit rate (% of times sign(pred) == sign(realized))."""
        if not predictions or len(predictions) != len(realized_returns):
            return 0.0
        hits = sum(1 for p, r in zip(predictions, realized_returns) if (p >= 0 and r >= 0) or (p < 0 and r < 0))
        return hits / len(predictions)

    @staticmethod
    def ensemble_predictions(
        model_predictions: Sequence[ModelPrediction],
        model_weights: Mapping[str, float] | None = None,
    ) -> ModelPrediction:
        """Combines multiple model forecasts using confidence or user weights."""
        if not model_predictions:
            raise ValueError("No predictions to ensemble")

        tot_w = 0.0
        ens_ret = 0.0
        ens_prob = 0.0
        ens_conf = 0.0

        for pred in model_predictions:
            w = (model_weights or {}).get(pred.model_name, pred.confidence)
            tot_w += w
            ens_ret += pred.expected_return * w
            ens_prob += pred.directional_probability_up * w
            ens_conf += pred.confidence * w

        scale = 1.0 / tot_w if tot_w > 0 else 1.0 / len(model_predictions)
        return ModelPrediction(
            model_name="ENSEMBLE",
            expected_return=round(ens_ret * scale, 6),
            directional_probability_up=round(ens_prob * scale, 4),
            confidence=round(ens_conf * scale, 4),
        )
