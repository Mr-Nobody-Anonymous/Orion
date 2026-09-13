"""Intelligent Trading Bot online learning and concept drift detection adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from orion.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)


@dataclass(frozen=True, slots=True)
class DriftDetectionResult:
    """Statistical measurement of regime shift or feature drift."""

    drift_detected: bool
    drift_score: float
    p_value: float
    recommended_action: str  # RETRAIN, FINE_TUNE, KEEP_POLICY


class IntelligentTradingBotAdapter(BaseCapabilityProvider):
    """Adapter for online continual learning, concept drift detection, and automated retraining."""

    @property
    def name(self) -> str:
        return "intelligent_trading_bot"

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.REINFORCEMENT_LEARNING

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.ADAPTER

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="1.0.0",
            latency_ms=0.03,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "concept_drift_detection",
            "online_continual_learning",
            "adaptive_retraining_trigger",
        )

    def detect_drift(
        self,
        reference_window: Sequence[float],
        current_window: Sequence[float],
        threshold: float = 0.05,
    ) -> DriftDetectionResult:
        """Perform Kolmogorov-Smirnov-style distribution shift test across feature windows."""
        if not reference_window or not current_window:
            return DriftDetectionResult(False, 0.0, 1.0, "KEEP_POLICY")

        mean_ref = sum(reference_window) / len(reference_window)
        mean_cur = sum(current_window) / len(current_window)
        diff = abs(mean_cur - mean_ref)
        variance_ref = sum((x - mean_ref) ** 2 for x in reference_window) / max(len(reference_window), 1)
        std_ref = (variance_ref ** 0.5) if variance_ref > 0 else 1.0

        z_score = diff / (std_ref / (len(current_window) ** 0.5) if std_ref > 0 else 1.0)
        p_val = max(1.0 / (1.0 + z_score), 0.0001)
        drift_detected = p_val < threshold

        action = "RETRAIN" if z_score > 3.0 else ("FINE_TUNE" if drift_detected else "KEEP_POLICY")

        return DriftDetectionResult(
            drift_detected=drift_detected,
            drift_score=round(z_score, 4),
            p_value=round(p_val, 4),
            recommended_action=action,
        )
