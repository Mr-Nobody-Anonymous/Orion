"""Online Continual Learning and Concept Drift Monitoring.

Monitors live prediction error decay, evaluates Champion vs. Challenger models in shadow mode,
and triggers automated retraining signals.
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class OnlinePerformanceSnapshot:
    model_name: str
    sample_count: int
    rolling_mse: float
    rolling_directional_accuracy: float
    is_degraded: bool
    retraining_recommended: bool


class OnlineContinualLearner:
    """Tracks live model performance against actual market outcomes and detects concept drift."""

    def __init__(
        self,
        model_name: str,
        window_size: int = 50,
        max_acceptable_mse: float = 0.05,
        min_acceptable_hit_rate: float = 0.52,
    ) -> None:
        self.model_name = model_name
        self.window_size = window_size
        self.max_acceptable_mse = max_acceptable_mse
        self.min_acceptable_hit_rate = min_acceptable_hit_rate
        self._history: list[tuple[float, float]] = []  # (predicted_return, actual_return)

    def record_outcome(self, predicted_return: float, actual_return: float) -> None:
        self._history.append((predicted_return, actual_return))
        if len(self._history) > self.window_size * 2:
            self._history = self._history[-self.window_size :]

    def evaluate_live_drift(self) -> OnlinePerformanceSnapshot:
        if len(self._history) < 10:
            return OnlinePerformanceSnapshot(
                model_name=self.model_name,
                sample_count=len(self._history),
                rolling_mse=0.0,
                rolling_directional_accuracy=1.0,
                is_degraded=False,
                retraining_recommended=False,
            )

        recent = self._history[-self.window_size :]
        n = len(recent)
        mse = sum((p - a) ** 2 for p, a in recent) / n
        hits = sum(1 for p, a in recent if (p >= 0 and a >= 0) or (p < 0 and a < 0))
        hit_rate = hits / n

        is_degraded = (mse > self.max_acceptable_mse) or (hit_rate < self.min_acceptable_hit_rate)
        retrain = is_degraded and (n >= 20)

        return OnlinePerformanceSnapshot(
            model_name=self.model_name,
            sample_count=n,
            rolling_mse=round(mse, 6),
            rolling_directional_accuracy=round(hit_rate, 4),
            is_degraded=is_degraded,
            retraining_recommended=retrain,
        )
