"""Market regime detection.

Regime detection is observational only. It never overrides the deterministic
risk engine. The output is an explicit, evidence-bound label with a
confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean, pstdev
from typing import Sequence


class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    RANGE = "range"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    regime: MarketRegime
    confidence: float
    average_return: float
    volatility: float
    trend_strength: float
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    def as_dict(self) -> dict[str, object]:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "average_return": self.average_return,
            "volatility": self.volatility,
            "trend_strength": self.trend_strength,
            "evidence": list(self.evidence),
        }


class RegimeDetector:
    """Pure-stdlib regime classifier with explainable thresholds."""

    def __init__(self, *, vol_high: float = 0.04, vol_low: float = 0.01, trend_threshold: float = 0.005) -> None:
        if not 0 < vol_low < vol_high:
            raise ValueError("vol_low must be positive and less than vol_high")
        self.vol_high = vol_high
        self.vol_low = vol_low
        self.trend_threshold = trend_threshold

    def detect(self, prices: Sequence[float]) -> RegimeAssessment:
        if len(prices) < 3 or any(p <= 0 for p in prices):
            return RegimeAssessment(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                average_return=0.0,
                volatility=0.0,
                trend_strength=0.0,
                evidence=("insufficient or non-positive prices",),
            )
        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
        avg = mean(returns)
        vol = pstdev(returns) if len(returns) > 1 else 0.0
        # Trend strength: cumulative log-return / volatility (a Sharpe-like ratio)
        cumulative = sum(returns)
        trend_strength = cumulative / max(vol, 1e-9)

        evidence: list[str] = []
        if vol >= self.vol_high:
            evidence.append(f"volatility {vol:.4f} >= {self.vol_high}")
            regime = MarketRegime.VOLATILE
            confidence = min(0.95, 0.5 + vol)
        elif abs(avg) < self.trend_threshold and vol < self.vol_low:
            evidence.append(f"|avg_return| {abs(avg):.4f} < {self.trend_threshold} and vol {vol:.4f} < {self.vol_low}")
            regime = MarketRegime.RANGE
            confidence = min(0.95, 0.6 + (1 - vol * 50) * 0.3)
        elif avg > 0:
            evidence.append(f"avg_return {avg:.4f} > 0")
            regime = MarketRegime.BULL
            confidence = min(0.95, 0.5 + abs(trend_strength) * 0.1)
        else:
            evidence.append(f"avg_return {avg:.4f} < 0")
            regime = MarketRegime.BEAR
            confidence = min(0.95, 0.5 + abs(trend_strength) * 0.1)

        return RegimeAssessment(
            regime=regime,
            confidence=float(max(0.05, min(0.95, confidence))),
            average_return=avg,
            volatility=vol,
            trend_strength=trend_strength,
            evidence=tuple(evidence),
        )
