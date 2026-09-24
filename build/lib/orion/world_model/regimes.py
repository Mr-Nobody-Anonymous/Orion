"""Market regime classification from price history.

A regime is an ESTIMATE, not a fact. Every classification carries a
confidence score and persists only when evidence accumulates; single-bar
flips are treated as noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from statistics import fmean
from typing import Sequence


class Regime(str, Enum):
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    RANGE = "range"
    VOLATILE = "volatile"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    regime: Regime
    confidence: float
    annualized_volatility: float
    trend_strength: float
    evidence_bars: int

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    def as_dict(self) -> dict[str, object]:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "annualized_volatility": self.annualized_volatility,
            "trend_strength": self.trend_strength,
            "evidence_bars": self.evidence_bars,
        }


def _returns(prices: Sequence[float]) -> list[float]:
    if any(p <= 0 for p in prices):
        raise ValueError("prices must be strictly positive")
    return [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]


def classify_regime(prices: Sequence[float], *, min_bars: int = 8) -> RegimeAssessment:
    """Threshold-based regime classification with explicit confidence.

    Classification logic (documented, deterministic):
      - annualized volatility > 80% with a >10% drawdown window -> CRISIS
      - volatility > 40% -> VOLATILE
      - |trend| (mean return / vol of the mean) >= 2 -> BULL/BEAR_TREND
      - otherwise RANGE; below min_bars -> UNKNOWN with zero confidence
    """
    if len(prices) < 3:
        raise ValueError("at least three prices are required")
    if any(p <= 0 for p in prices):
        raise ValueError("prices must be strictly positive")
    if len(prices) < min_bars:
        return RegimeAssessment(Regime.UNKNOWN, 0.0, 0.0, 0.0, len(prices))
    returns = _returns(prices)
    mean_return = fmean(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    daily_vol = sqrt(variance)
    annualized_vol = daily_vol * sqrt(252)
    trend_strength = 0.0 if daily_vol == 0 else (mean_return / daily_vol) * sqrt(len(returns))
    peak = prices[0]
    max_drawdown = 0.0
    for price in prices:
        peak = max(peak, price)
        max_drawdown = min(max_drawdown, price / peak - 1.0)
    if annualized_vol > 0.80 and max_drawdown < -0.10:
        regime, confidence = Regime.CRISIS, min(0.95, 0.6 + abs(max_drawdown))
    elif annualized_vol > 0.40:
        regime, confidence = Regime.VOLATILE, min(0.9, 0.5 + (annualized_vol - 0.40))
    elif trend_strength >= 2.0:
        regime, confidence = Regime.BULL_TREND, min(0.9, 0.4 + trend_strength / 10)
    elif trend_strength <= -2.0:
        regime, confidence = Regime.BEAR_TREND, min(0.9, 0.4 + abs(trend_strength) / 10)
    else:
        regime, confidence = Regime.RANGE, 0.5
    return RegimeAssessment(regime, min(confidence, 0.95), annualized_vol, trend_strength, len(prices))


class RegimeTracker:
    """Requires persistence before announcing a regime change."""

    def __init__(self, *, persistence: int = 3) -> None:
        if persistence < 1:
            raise ValueError("persistence must be at least one")
        self.persistence = persistence
        self.current: Regime = Regime.UNKNOWN
        self._pending: Regime | None = None
        self._pending_count = 0

    def update(self, assessment: RegimeAssessment) -> Regime:
        if assessment.confidence == 0.0:
            return self.current
        if assessment.regime is self.current:
            self._pending, self._pending_count = None, 0
            return self.current
        if assessment.regime is self._pending:
            self._pending_count += 1
        else:
            self._pending, self._pending_count = assessment.regime, 1
        if self._pending_count >= self.persistence:
            self.current = self._pending  # type: ignore[assignment]
            self._pending, self._pending_count = None, 0
        return self.current


__all__ = [
    "Regime",
    "RegimeAssessment",
    "RegimeTracker",
    "classify_regime",
]
