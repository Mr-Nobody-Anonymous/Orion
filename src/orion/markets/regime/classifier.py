"""Market Regime Engine.

Multi-asset regime detection: Bull/Bear, Volatility regime, and Risk-On/Risk-Off state.
Strictly in the Truth plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Sequence


class MarketTrendRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"


class VolatilityRegime(str, Enum):
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    CRISIS_VOLATILITY = "CRISIS_VOLATILITY"


class MacroSentimentRegime(str, Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class ComprehensiveRegimeSnapshot:
    trend_regime: MarketTrendRegime
    volatility_regime: VolatilityRegime
    macro_regime: MacroSentimentRegime
    annualized_volatility: float
    trend_slope_pct: float
    confidence: float
    recommended_leverage_multiplier: Decimal


class MarketRegimeEngine:
    """Classifies market states and adjusts recommended portfolio exposure leverage."""

    @staticmethod
    def classify_regime(
        daily_prices: Sequence[float],
        benchmark_returns: Sequence[float] | None = None,
        high_yield_spread_bps: float = 350.0,
    ) -> ComprehensiveRegimeSnapshot:
        if len(daily_prices) < 20:
            return ComprehensiveRegimeSnapshot(
                trend_regime=MarketTrendRegime.SIDEWAYS,
                volatility_regime=VolatilityRegime.NORMAL_VOLATILITY,
                macro_regime=MacroSentimentRegime.NEUTRAL,
                annualized_volatility=0.15,
                trend_slope_pct=0.0,
                confidence=0.5,
                recommended_leverage_multiplier=Decimal("1.0"),
            )

        # 1. Trend calculation (EMA / slope)
        p_curr = daily_prices[-1]
        p_20_prior = daily_prices[-20]
        trend_slope = (p_curr - p_20_prior) / p_20_prior

        if trend_slope > 0.05:
            trend = MarketTrendRegime.BULL
        elif trend_slope < -0.05:
            trend = MarketTrendRegime.BEAR
        else:
            trend = MarketTrendRegime.SIDEWAYS

        # 2. Volatility calculation
        returns = [(daily_prices[i] - daily_prices[i - 1]) / daily_prices[i - 1] for i in range(1, len(daily_prices))]
        n = len(returns)
        mean_r = sum(returns) / n
        var_r = sum((r - mean_r) ** 2 for r in returns) / max(1, n - 1)
        daily_vol = math.sqrt(var_r)
        ann_vol = daily_vol * math.sqrt(252)

        if ann_vol < 0.12:
            vol_regime = VolatilityRegime.LOW_VOLATILITY
            lev_mult = Decimal("1.2")
        elif ann_vol < 0.22:
            vol_regime = VolatilityRegime.NORMAL_VOLATILITY
            lev_mult = Decimal("1.0")
        elif ann_vol < 0.40:
            vol_regime = VolatilityRegime.HIGH_VOLATILITY
            lev_mult = Decimal("0.7")
        else:
            vol_regime = VolatilityRegime.CRISIS_VOLATILITY
            lev_mult = Decimal("0.3")

        # 3. Macro sentiment
        if high_yield_spread_bps < 320.0 and trend == MarketTrendRegime.BULL:
            macro = MacroSentimentRegime.RISK_ON
        elif high_yield_spread_bps > 500.0 or trend == MarketTrendRegime.BEAR:
            macro = MacroSentimentRegime.RISK_OFF
            lev_mult = min(lev_mult, Decimal("0.5"))
        else:
            macro = MacroSentimentRegime.NEUTRAL

        return ComprehensiveRegimeSnapshot(
            trend_regime=trend,
            volatility_regime=vol_regime,
            macro_regime=macro,
            annualized_volatility=round(ann_vol, 4),
            trend_slope_pct=round(trend_slope, 4),
            confidence=0.85,
            recommended_leverage_multiplier=lev_mult,
        )
