"""Uncertainty quantification for predictions.

The module separates *aleatoric* (data) uncertainty from *epistemic* (model)
uncertainty using a transparent, stdlib-only decomposition that any ensemble
member can contribute to.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, pstdev
from typing import Sequence


@dataclass(frozen=True, slots=True)
class UncertaintyEstimate:
    point_estimate: float
    aleatoric_uncertainty: float
    epistemic_uncertainty: float
    predictive_interval_low: float
    predictive_interval_high: float
    coverage: float

    @property
    def total(self) -> float:
        return sqrt(self.aleatoric_uncertainty ** 2 + self.epistemic_uncertainty ** 2)

    def as_dict(self) -> dict[str, float]:
        return {
            "point_estimate": self.point_estimate,
            "aleatoric_uncertainty": self.aleatoric_uncertainty,
            "epistemic_uncertainty": self.epistemic_uncertainty,
            "total_uncertainty": self.total,
            "predictive_interval_low": self.predictive_interval_low,
            "predictive_interval_high": self.predictive_interval_high,
            "coverage": self.coverage,
        }


def estimate_from_ensemble(
    predictions: Sequence[float],
    *,
    coverage: float = 0.95,
) -> UncertaintyEstimate:
    """Decompose ensemble predictions into aleatoric + epistemic uncertainty.

    Aleatoric uncertainty is the average within-model variance (here proxied
    by the average absolute deviation from each model's own predicted mean).
    Epistemic uncertainty is the disagreement across models. A real system
    with per-model variance estimates would replace the proxy.
    """
    if not predictions:
        raise ValueError("predictions must be non-empty")
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between 0 and 1")
    point = mean(predictions)
    variance = pstdev(predictions) if len(predictions) > 1 else 0.0
    epistemic = float(variance)
    # Aleatoric proxy: assume an irreducible noise floor proportional to mean
    # absolute deviation across the ensemble.
    aleatoric = float(mean(abs(p - point) for p in predictions))
    z = 1.96 if abs(coverage - 0.95) < 1e-9 else 2.0
    total = sqrt(epistemic ** 2 + aleatoric ** 2)
    return UncertaintyEstimate(
        point_estimate=float(point),
        aleatoric_uncertainty=aleatoric,
        epistemic_uncertainty=epistemic,
        predictive_interval_low=point - z * total,
        predictive_interval_high=point + z * total,
        coverage=coverage,
    )


def prediction_from_decimal(predictions: Sequence[Decimal], *, coverage: float = 0.95) -> UncertaintyEstimate:
    return estimate_from_ensemble([float(p) for p in predictions], coverage=coverage)
