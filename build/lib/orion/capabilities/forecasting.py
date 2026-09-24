"""Forecasting capability contract and data structures."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class ForecastRequest:
    """Request to forecast a price time-series."""

    symbol: str
    prices: Sequence[float]
    horizon_steps: int = 1
    features: dict[str, Sequence[float]] | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """Standardized output of a temporal forecasting provider."""

    provider_name: str
    symbol: str
    predicted_return: float
    probability_up: float
    confidence: float
    lower_bound: float
    upper_bound: float
    horizon_steps: int
    features_used: tuple[str, ...] = ()
    engine_metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "symbol": self.symbol,
            "predicted_return": self.predicted_return,
            "probability_up": self.probability_up,
            "confidence": self.confidence,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "horizon_steps": self.horizon_steps,
            "features_used": list(self.features_used),
            "engine_metadata": self.engine_metadata,
        }


class ForecastingProvider(BaseCapabilityProvider):
    """Abstract interface for temporal and candlestick forecasting engines."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.FORECASTING

    @abstractmethod
    def forecast(self, request: ForecastRequest) -> ForecastResult:
        """Generate a temporal forecast given historical price series."""
