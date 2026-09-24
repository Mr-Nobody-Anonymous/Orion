"""ORION Model Risk Monitor.

Detects model degradation, feature drift, distribution shift,
prediction calibration failure, and live/backtest divergence.
Implements automatic model demotion when performance degrades.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ModelHealthCheck:
    """Health check result for a single model."""

    model_id: str
    model_version: str
    status: str  # HEALTHY, DEGRADED, CRITICAL, RETIRED
    live_sharpe: Decimal
    expected_sharpe: Decimal
    sharpe_ratio: Decimal  # live / expected
    prediction_accuracy: Decimal
    calibration_error: Decimal
    feature_drift_score: Decimal  # 0 = stable, 1 = drifted
    distribution_shift_score: Decimal
    live_backtest_divergence: Decimal
    reasons: tuple[str, ...]
    recommended_action: str


@dataclass
class ModelPerformanceRecord:
    """Track ongoing model performance for drift detection."""

    model_id: str
    model_version: str
    predictions: list[float] = field(default_factory=list)
    actuals: list[float] = field(default_factory=list)
    timestamps: list[datetime] = field(default_factory=list)
    backtest_sharpe: Decimal = Decimal("0")
    max_records: int = 1000

    def add_observation(self, prediction: float, actual: float) -> None:
        """Add a prediction-actual pair."""
        self.predictions.append(prediction)
        self.actuals.append(actual)
        self.timestamps.append(datetime.now(timezone.utc))
        # Sliding window
        if len(self.predictions) > self.max_records:
            self.predictions = self.predictions[-self.max_records:]
            self.actuals = self.actuals[-self.max_records:]
            self.timestamps = self.timestamps[-self.max_records:]


class ModelRiskMonitor:
    """Monitors model health and triggers demotion when degradation is detected.

    A model should automatically be demoted when:
    - Performance degradation (live Sharpe << backtest Sharpe)
    - Feature drift detected
    - Distribution shift in predictions
    - Prediction calibration failure
    - Risk contribution increases
    - Live/backtest divergence exceeds threshold
    - Transaction cost explosion
    - Drawdown breach
    """

    def __init__(
        self,
        min_sharpe_ratio: Decimal = Decimal("0.50"),  # live/expected
        max_calibration_error: Decimal = Decimal("0.15"),
        max_drift_score: Decimal = Decimal("0.30"),
        max_divergence: Decimal = Decimal("0.50"),
        min_observations: int = 30,
    ) -> None:
        self.min_sharpe_ratio = min_sharpe_ratio
        self.max_calibration_error = max_calibration_error
        self.max_drift_score = max_drift_score
        self.max_divergence = max_divergence
        self.min_observations = min_observations
        self._records: dict[str, ModelPerformanceRecord] = {}

    def register_model(
        self,
        model_id: str,
        model_version: str,
        backtest_sharpe: Decimal = Decimal("0"),
    ) -> None:
        """Register a model for monitoring."""
        self._records[model_id] = ModelPerformanceRecord(
            model_id=model_id,
            model_version=model_version,
            backtest_sharpe=backtest_sharpe,
        )

    def record_prediction(
        self, model_id: str, prediction: float, actual: float,
    ) -> None:
        """Record a prediction-actual pair for a model."""
        if model_id in self._records:
            self._records[model_id].add_observation(prediction, actual)

    def check_health(self, model_id: str) -> ModelHealthCheck:
        """Run a comprehensive health check on a model."""
        record = self._records.get(model_id)
        if record is None:
            return ModelHealthCheck(
                model_id=model_id, model_version="unknown",
                status="UNKNOWN", live_sharpe=Decimal("0"),
                expected_sharpe=Decimal("0"), sharpe_ratio=Decimal("0"),
                prediction_accuracy=Decimal("0"), calibration_error=Decimal("1"),
                feature_drift_score=Decimal("1"), distribution_shift_score=Decimal("1"),
                live_backtest_divergence=Decimal("1"),
                reasons=("Model not registered for monitoring",),
                recommended_action="REGISTER",
            )

        reasons: list[str] = []
        n = len(record.predictions)

        if n < self.min_observations:
            return ModelHealthCheck(
                model_id=model_id, model_version=record.model_version,
                status="INSUFFICIENT_DATA", live_sharpe=Decimal("0"),
                expected_sharpe=record.backtest_sharpe, sharpe_ratio=Decimal("0"),
                prediction_accuracy=Decimal("0"), calibration_error=Decimal("0"),
                feature_drift_score=Decimal("0"), distribution_shift_score=Decimal("0"),
                live_backtest_divergence=Decimal("0"),
                reasons=(f"Only {n}/{self.min_observations} observations",),
                recommended_action="WAIT",
            )

        # 1. Prediction accuracy (direction correctness)
        correct = sum(
            1 for p, a in zip(record.predictions, record.actuals)
            if (p > 0 and a > 0) or (p < 0 and a < 0) or (p == 0 and a == 0)
        )
        accuracy = Decimal(str(correct / n))

        # 2. Live Sharpe estimate
        errors = [a - p for p, a in zip(record.predictions, record.actuals)]
        mean_ret = sum(record.actuals) / n
        var_ret = sum((r - mean_ret) ** 2 for r in record.actuals) / max(1, n - 1)
        stdev = math.sqrt(var_ret) if var_ret > 0 else 0.001
        live_sharpe = Decimal(str(mean_ret / stdev * math.sqrt(252)))
        expected_sharpe = record.backtest_sharpe

        sharpe_ratio = (
            live_sharpe / expected_sharpe
            if expected_sharpe > 0 else Decimal("0")
        )

        # 3. Calibration error (mean absolute error)
        mae = sum(abs(p - a) for p, a in zip(record.predictions, record.actuals)) / n
        cal_error = Decimal(str(mae))

        # 4. Feature drift: compare prediction distributions (first half vs second half)
        half = n // 2
        if half > 5:
            first_half = record.predictions[:half]
            second_half = record.predictions[half:]
            drift = abs(
                (sum(second_half) / len(second_half))
                - (sum(first_half) / len(first_half))
            )
            drift_score = Decimal(str(min(1.0, drift * 10)))
        else:
            drift_score = Decimal("0")

        # 5. Distribution shift
        pred_std_first = math.sqrt(
            sum((p - sum(record.predictions[:half]) / max(1, half)) ** 2 for p in record.predictions[:half])
            / max(1, half)
        ) if half > 2 else 0.01
        pred_std_second = math.sqrt(
            sum((p - sum(record.predictions[half:]) / max(1, len(record.predictions[half:]))) ** 2 for p in record.predictions[half:])
            / max(1, len(record.predictions[half:]))
        ) if half > 2 else 0.01
        shift = abs(pred_std_second - pred_std_first) / max(pred_std_first, 0.001)
        shift_score = Decimal(str(min(1.0, shift)))

        # 6. Live/backtest divergence
        divergence = abs(Decimal("1") - sharpe_ratio) if expected_sharpe > 0 else Decimal("1")

        # Determine status
        status = "HEALTHY"
        action = "MAINTAIN"

        if sharpe_ratio < self.min_sharpe_ratio:
            reasons.append(f"Live Sharpe ratio {sharpe_ratio:.2f} below threshold {self.min_sharpe_ratio}")
            status = "DEGRADED"
            action = "REDUCE_ALLOCATION_50PCT"

        if cal_error > self.max_calibration_error:
            reasons.append(f"Calibration error {cal_error:.4f} exceeds {self.max_calibration_error}")
            status = "DEGRADED"

        if drift_score > self.max_drift_score:
            reasons.append(f"Feature drift score {drift_score:.2f} exceeds {self.max_drift_score}")
            if status != "CRITICAL":
                status = "DEGRADED"

        if divergence > self.max_divergence:
            reasons.append(f"Live/backtest divergence {divergence:.2f} exceeds {self.max_divergence}")
            status = "CRITICAL"
            action = "SUSPEND_AND_INVESTIGATE"

        if accuracy < Decimal("0.45"):
            reasons.append(f"Accuracy {accuracy:.1%} below random baseline")
            status = "CRITICAL"
            action = "RETIRE"

        if not reasons:
            reasons.append("All health checks passed")

        return ModelHealthCheck(
            model_id=model_id,
            model_version=record.model_version,
            status=status,
            live_sharpe=live_sharpe.quantize(Decimal("0.01")),
            expected_sharpe=expected_sharpe,
            sharpe_ratio=sharpe_ratio.quantize(Decimal("0.01")),
            prediction_accuracy=accuracy.quantize(Decimal("0.01")),
            calibration_error=cal_error.quantize(Decimal("0.0001")),
            feature_drift_score=drift_score.quantize(Decimal("0.01")),
            distribution_shift_score=shift_score.quantize(Decimal("0.01")),
            live_backtest_divergence=divergence.quantize(Decimal("0.01")),
            reasons=tuple(reasons),
            recommended_action=action,
        )

    def check_all(self) -> list[ModelHealthCheck]:
        """Run health checks on all registered models."""
        return [self.check_health(mid) for mid in self._records]
