"""Standardized model evaluation and model cards (Phase 19).

Models are never judged on trading profit alone. Evaluation covers forecast
accuracy, calibration, uncertainty quality, generalization across regimes,
stability, and documented failure modes — all recorded on a versioned card.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from math import sqrt
from statistics import fmean
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class AccuracyReport:
    mean_absolute_error: float
    root_mean_squared_error: float
    directional_accuracy: float
    sample_size: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "mae": self.mean_absolute_error,
            "rmse": self.root_mean_squared_error,
            "directional_accuracy": self.directional_accuracy,
            "n": self.sample_size,
        }


def accuracy_report(predictions: Sequence[Decimal], actuals: Sequence[Decimal]) -> AccuracyReport:
    """Forecast accuracy: magnitude errors plus directional hit rate."""
    if not predictions or len(predictions) != len(actuals):
        raise ValueError("predictions and actuals must be non-empty and equal length")
    errors = [float(p - a) for p, a in zip(predictions, actuals)]
    mae = fmean(abs(error) for error in errors)
    rmse = sqrt(fmean(error * error for error in errors))
    hits = sum(1 for p, a in zip(predictions, actuals) if (p > 0) == (a > 0) and a != 0)
    return AccuracyReport(mae, rmse, hits / len(errors), len(errors))


def calibration_error(confidences: Sequence[float], successes: Sequence[bool]) -> float:
    """Mean absolute gap between stated confidence and realized hit rate."""
    if not confidences or len(confidences) != len(successes):
        raise ValueError("confidences and successes must be non-empty and equal length")
    if any(not 0 <= confidence <= 1 for confidence in confidences):
        raise ValueError("confidences must be within [0, 1]")
    realized = sum(1 for success in successes if success) / len(successes)
    stated = fmean(confidences)
    return abs(stated - realized)


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    regime: str
    mean_absolute_error: float
    sample_size: int


def regime_breakdown(regimes: Sequence[str], predictions: Sequence[Decimal],
                     actuals: Sequence[Decimal]) -> tuple[RegimePerformance, ...]:
    if not regimes or len(regimes) != len(predictions):
        raise ValueError("regimes, predictions, actuals must be equal length and non-empty")
    buckets: dict[str, list[tuple[Decimal, Decimal]]] = {}
    for regime, prediction, actual in zip(regimes, predictions, actuals):
        buckets.setdefault(regime, []).append((prediction, actual))
    return tuple(
        RegimePerformance(regime, fmean(abs(float(p - a)) for p, a in pairs), len(pairs))
        for regime, pairs in sorted(buckets.items())
    )


@dataclass(frozen=True, slots=True)
class ModelCard:
    """Versioned evaluation card. Immutable once created."""

    model_name: str
    model_version: str
    dataset_version: str
    accuracy: AccuracyReport
    calibration_error: float
    regime_performance: tuple[RegimePerformance, ...]
    failure_modes: tuple[str, ...]
    resource_usage: Mapping[str, float]
    latency_ms_p50: float
    overall_status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": f"{self.model_name}:{self.model_version}",
            "dataset": self.dataset_version,
            "accuracy": self.accuracy.as_dict(),
            "calibration_error": self.calibration_error,
            "regimes": [{"regime": r.regime, "mae": r.mean_absolute_error, "n": r.sample_size}
                        for r in self.regime_performance],
            "failure_modes": list(self.failure_modes),
            "resources": dict(self.resource_usage),
            "latency_ms_p50": self.latency_ms_p50,
            "status": self.overall_status,
        }


class ModelEvaluator:
    """Produces model cards from prediction records under a fixed policy."""

    def __init__(self, *, max_calibration_error: float = 0.25, max_mae: float = 0.05) -> None:
        if not 0 < max_calibration_error < 1:
            raise ValueError("max_calibration_error must be within (0, 1)")
        if max_mae <= 0:
            raise ValueError("max_mae must be positive")
        self.max_calibration_error = max_calibration_error
        self.max_mae = max_mae

    def evaluate(
        self,
        model_name: str,
        model_version: str,
        dataset_version: str,
        predictions: Sequence[Decimal],
        actuals: Sequence[Decimal],
        confidences: Sequence[float],
        regimes: Sequence[str],
        *,
        failure_modes: Sequence[str] = (),
        latency_ms_p50: float = 0.0,
        resource_usage: Mapping[str, float] | None = None,
    ) -> ModelCard:
        report = accuracy_report(predictions, actuals)
        calibration = calibration_error(confidences, [p * a > 0 for p, a in zip(predictions, actuals)])
        regimes_report = regime_breakdown(regimes, predictions, actuals)
        worst_regime_mae = max((r.mean_absolute_error for r in regimes_report), default=0.0)
        status = "APPROVED_FOR_EVALUATION" if (
            report.mean_absolute_error <= self.max_mae
            and calibration <= self.max_calibration_error
        ) else "NEEDS_IMPROVEMENT"
        if worst_regime_mae > self.max_mae * 2:
            status = "NEEDS_IMPROVEMENT"
        return ModelCard(
            model_name, model_version, dataset_version, report, calibration, regimes_report,
            tuple(failure_modes), dict(resource_usage or {}), latency_ms_p50, status,
        )
