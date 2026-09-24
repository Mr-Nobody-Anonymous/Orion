"""Economic Intelligence and Macro Release Analysis.

Computes normalized macroeconomic surprises, market volatility reaction expectations,
and central bank policy stances.
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Sequence

from ...data.contracts import EconomicEvent


class MacroSurpriseDirection(str, Enum):
    BEAT = "BEAT"
    IN_LINE = "IN_LINE"
    MISS = "MISS"


class CentralBankStance(str, Enum):
    HAWKISH = "HAWKISH"
    NEUTRAL = "NEUTRAL"
    DOVISH = "DOVISH"


@dataclass(frozen=True, slots=True)
class MacroSurpriseAnalysis:
    event: EconomicEvent
    surprise: Decimal | None
    surprise_direction: MacroSurpriseDirection
    expected_volatility_impact: str  # "LOW", "MEDIUM", "HIGH"


class EconomicIntelligenceEngine:
    """Calculates macro surprise indicators and central bank policy stances."""

    @staticmethod
    def analyze_event(event: EconomicEvent, historical_stdev: Decimal | None = None) -> MacroSurpriseAnalysis:
        if event.actual is None or event.forecast is None:
            return MacroSurpriseAnalysis(
                event=event,
                surprise=None,
                surprise_direction=MacroSurpriseDirection.IN_LINE,
                expected_volatility_impact="LOW",
            )

        diff = event.actual - event.forecast
        stdev = historical_stdev if historical_stdev and historical_stdev > 0 else Decimal("1.0")
        z_surprise = diff / stdev

        if abs(z_surprise) < Decimal("0.2"):
            direction = MacroSurpriseDirection.IN_LINE
        elif z_surprise > 0:
            direction = MacroSurpriseDirection.BEAT
        else:
            direction = MacroSurpriseDirection.MISS

        # High-impact indicators
        high_impact_names = ("cpi", "gdp", "nonfarm payrolls", "fed interest rate", "fomc", "ecb")
        is_high = any(h in event.name.lower() for h in high_impact_names)
        vol_impact = "HIGH" if (is_high or abs(z_surprise) > Decimal("1.5")) else "MEDIUM"

        return MacroSurpriseAnalysis(
            event=event,
            surprise=diff,
            surprise_direction=direction,
            expected_volatility_impact=vol_impact,
        )

    @staticmethod
    def classify_central_bank_stance(rate_change_bps: int, forward_guidance_score: float) -> CentralBankStance:
        """Classifies stance from rate move (+25 bps) and NLP forward guidance sentiment score (-1 to +1)."""
        if rate_change_bps > 0 or forward_guidance_score > 0.3:
            return CentralBankStance.HAWKISH
        if rate_change_bps < 0 or forward_guidance_score < -0.3:
            return CentralBankStance.DOVISH
        return CentralBankStance.NEUTRAL
