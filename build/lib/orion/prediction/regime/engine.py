"""ORION Market Regime Classification Engine.

Classifies the current market state into one or more regimes:
  trend, mean-reverting, high-volatility, low-volatility,
  risk-on, risk-off, inflationary, deflationary,
  liquidity-expansion, liquidity-contraction, credit-stress.

Regime classification drives strategy weight adaptation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence


class RegimeType:
    """Market regime labels."""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    MEAN_REVERTING = "mean_reverting"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    INFLATIONARY = "inflationary"
    DEFLATIONARY = "deflationary"
    LIQUIDITY_EXPANSION = "liquidity_expansion"
    LIQUIDITY_CONTRACTION = "liquidity_contraction"
    CREDIT_STRESS = "credit_stress"
    NORMAL = "normal"


@dataclass(frozen=True, slots=True)
class RegimeClassification:
    """Classification result for the current market regime."""

    primary_regime: str
    secondary_regimes: tuple[str, ...]
    confidence: Decimal
    volatility_regime: str  # high_volatility or low_volatility
    trend_regime: str  # trend_up, trend_down, or mean_reverting
    risk_regime: str  # risk_on or risk_off
    regime_age_bars: int  # how long the current regime has persisted
    transition_probability: Decimal  # estimated prob of regime change
    indicators: Mapping[str, Decimal]


@dataclass(frozen=True, slots=True)
class RegimeStrategyWeights:
    """Strategy weight recommendations for the current regime."""

    regime: str
    momentum: Decimal
    mean_reversion: Decimal
    value: Decimal
    quality: Decimal
    trend_following: Decimal
    defensive: Decimal
    cash: Decimal


class MarketRegimeEngine:
    """Market regime classification engine.

    Uses a combination of statistical indicators to classify regimes:
    - Volatility: rolling std vs. long-term median
    - Trend: price vs. moving averages, ADX-like strength
    - Mean reversion: autocorrelation of returns
    - Risk: cross-asset correlation, flight-to-quality signals
    """

    # Regime → strategy weight recommendations
    STRATEGY_WEIGHTS: dict[str, RegimeStrategyWeights] = {
        RegimeType.TREND_UP: RegimeStrategyWeights(
            regime=RegimeType.TREND_UP,
            momentum=Decimal("0.30"), mean_reversion=Decimal("0.05"),
            value=Decimal("0.15"), quality=Decimal("0.15"),
            trend_following=Decimal("0.25"), defensive=Decimal("0.05"),
            cash=Decimal("0.05"),
        ),
        RegimeType.TREND_DOWN: RegimeStrategyWeights(
            regime=RegimeType.TREND_DOWN,
            momentum=Decimal("0.10"), mean_reversion=Decimal("0.10"),
            value=Decimal("0.20"), quality=Decimal("0.25"),
            trend_following=Decimal("0.10"), defensive=Decimal("0.15"),
            cash=Decimal("0.10"),
        ),
        RegimeType.HIGH_VOLATILITY: RegimeStrategyWeights(
            regime=RegimeType.HIGH_VOLATILITY,
            momentum=Decimal("0.10"), mean_reversion=Decimal("0.05"),
            value=Decimal("0.15"), quality=Decimal("0.35"),
            trend_following=Decimal("0.10"), defensive=Decimal("0.10"),
            cash=Decimal("0.15"),
        ),
        RegimeType.LOW_VOLATILITY: RegimeStrategyWeights(
            regime=RegimeType.LOW_VOLATILITY,
            momentum=Decimal("0.25"), mean_reversion=Decimal("0.15"),
            value=Decimal("0.15"), quality=Decimal("0.10"),
            trend_following=Decimal("0.20"), defensive=Decimal("0.05"),
            cash=Decimal("0.10"),
        ),
        RegimeType.RISK_OFF: RegimeStrategyWeights(
            regime=RegimeType.RISK_OFF,
            momentum=Decimal("0.10"), mean_reversion=Decimal("0.05"),
            value=Decimal("0.15"), quality=Decimal("0.35"),
            trend_following=Decimal("0.10"), defensive=Decimal("0.10"),
            cash=Decimal("0.15"),
        ),
        RegimeType.RISK_ON: RegimeStrategyWeights(
            regime=RegimeType.RISK_ON,
            momentum=Decimal("0.30"), mean_reversion=Decimal("0.10"),
            value=Decimal("0.15"), quality=Decimal("0.10"),
            trend_following=Decimal("0.25"), defensive=Decimal("0.05"),
            cash=Decimal("0.05"),
        ),
        RegimeType.MEAN_REVERTING: RegimeStrategyWeights(
            regime=RegimeType.MEAN_REVERTING,
            momentum=Decimal("0.05"), mean_reversion=Decimal("0.35"),
            value=Decimal("0.20"), quality=Decimal("0.15"),
            trend_following=Decimal("0.05"), defensive=Decimal("0.10"),
            cash=Decimal("0.10"),
        ),
        RegimeType.NORMAL: RegimeStrategyWeights(
            regime=RegimeType.NORMAL,
            momentum=Decimal("0.20"), mean_reversion=Decimal("0.15"),
            value=Decimal("0.15"), quality=Decimal("0.15"),
            trend_following=Decimal("0.15"), defensive=Decimal("0.10"),
            cash=Decimal("0.10"),
        ),
    }

    def __init__(
        self,
        vol_lookback: int = 20,
        trend_lookback: int = 50,
        long_vol_lookback: int = 252,
    ) -> None:
        self.vol_lookback = vol_lookback
        self.trend_lookback = trend_lookback
        self.long_vol_lookback = long_vol_lookback

    def classify(
        self,
        prices: Sequence[float],
        volumes: Sequence[float] | None = None,
        vix: float | None = None,
        credit_spread: float | None = None,
    ) -> RegimeClassification:
        """Classify the current market regime from price data.

        Args:
            prices: Historical price series (most recent at end).
            volumes: Optional volume series.
            vix: Current VIX level (if available).
            credit_spread: High-yield credit spread (if available).
        """
        n = len(prices)
        if n < 10:
            return RegimeClassification(
                primary_regime=RegimeType.NORMAL,
                secondary_regimes=(),
                confidence=Decimal("0.3"),
                volatility_regime=RegimeType.LOW_VOLATILITY,
                trend_regime=RegimeType.MEAN_REVERTING,
                risk_regime=RegimeType.RISK_ON,
                regime_age_bars=0,
                transition_probability=Decimal("0.5"),
                indicators={},
            )

        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, n) if prices[i - 1] != 0]

        # ── Volatility regime ──
        short_vol = self._rolling_vol(returns, min(self.vol_lookback, len(returns)))
        long_vol = self._rolling_vol(returns, min(self.long_vol_lookback, len(returns)))
        vol_ratio = short_vol / max(long_vol, 0.0001)

        if vol_ratio > 1.5 or (vix is not None and vix > 25):
            vol_regime = RegimeType.HIGH_VOLATILITY
        elif vol_ratio < 0.7 or (vix is not None and vix < 15):
            vol_regime = RegimeType.LOW_VOLATILITY
        else:
            vol_regime = RegimeType.NORMAL

        # ── Trend regime ──
        lookback = min(self.trend_lookback, n)
        if lookback > 5:
            sma = sum(prices[-lookback:]) / lookback
            price_vs_sma = (prices[-1] - sma) / max(sma, 0.001)

            # Trend strength (simplified ADX analog)
            up_moves = sum(1 for i in range(-lookback, 0) if i + n >= 1 and prices[i] > prices[i - 1])
            trend_strength = abs(up_moves / lookback - 0.5) * 2
        else:
            price_vs_sma = 0.0
            trend_strength = 0.0

        if trend_strength > 0.3 and price_vs_sma > 0.02:
            trend_regime = RegimeType.TREND_UP
        elif trend_strength > 0.3 and price_vs_sma < -0.02:
            trend_regime = RegimeType.TREND_DOWN
        else:
            trend_regime = RegimeType.MEAN_REVERTING

        # ── Autocorrelation (mean-reversion detection) ──
        if len(returns) > 10:
            mean_r = sum(returns) / len(returns)
            autocovar = sum(
                (returns[i] - mean_r) * (returns[i - 1] - mean_r)
                for i in range(1, len(returns))
            ) / (len(returns) - 1)
            variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
            autocorr = autocovar / max(variance, 1e-10)
        else:
            autocorr = 0.0

        if autocorr < -0.1:
            trend_regime = RegimeType.MEAN_REVERTING

        # ── Risk regime ──
        if credit_spread is not None and credit_spread > 5.0:
            risk_regime = RegimeType.RISK_OFF
        elif vol_regime == RegimeType.HIGH_VOLATILITY and trend_regime == RegimeType.TREND_DOWN:
            risk_regime = RegimeType.RISK_OFF
        elif vol_regime == RegimeType.LOW_VOLATILITY and trend_regime == RegimeType.TREND_UP:
            risk_regime = RegimeType.RISK_ON
        else:
            risk_regime = RegimeType.RISK_ON if trend_regime == RegimeType.TREND_UP else RegimeType.RISK_OFF

        # ── Primary regime (highest signal) ──
        secondary: list[str] = []
        if vol_regime == RegimeType.HIGH_VOLATILITY:
            primary = RegimeType.HIGH_VOLATILITY
            secondary = [trend_regime, risk_regime]
        elif trend_regime in (RegimeType.TREND_UP, RegimeType.TREND_DOWN):
            primary = trend_regime
            secondary = [vol_regime, risk_regime]
        elif trend_regime == RegimeType.MEAN_REVERTING:
            primary = RegimeType.MEAN_REVERTING
            secondary = [vol_regime, risk_regime]
        else:
            primary = RegimeType.NORMAL
            secondary = [vol_regime, trend_regime, risk_regime]

        # ── Confidence ──
        confidence = max(
            Decimal(str(round(trend_strength * 0.5 + min(abs(vol_ratio - 1), 1) * 0.5, 2))),
            Decimal("0.3"),
        )
        confidence = min(confidence, Decimal("0.95"))

        # ── Regime age (how many bars the regime has been stable) ──
        regime_age = self._estimate_regime_age(returns, vol_ratio, price_vs_sma)

        # ── Transition probability ──
        # Higher when regime is old and indicators are ambiguous
        transition = max(
            Decimal("0.05"),
            Decimal("1") - confidence - Decimal(str(min(regime_age / 100, 0.3))),
        )

        indicators = {
            "short_vol": Decimal(str(round(short_vol, 6))),
            "long_vol": Decimal(str(round(long_vol, 6))),
            "vol_ratio": Decimal(str(round(vol_ratio, 4))),
            "price_vs_sma": Decimal(str(round(price_vs_sma, 4))),
            "trend_strength": Decimal(str(round(trend_strength, 4))),
            "autocorrelation": Decimal(str(round(autocorr, 4))),
        }

        if vix is not None:
            indicators["vix"] = Decimal(str(round(vix, 2)))
        if credit_spread is not None:
            indicators["credit_spread"] = Decimal(str(round(credit_spread, 2)))

        return RegimeClassification(
            primary_regime=primary,
            secondary_regimes=tuple(secondary),
            confidence=confidence,
            volatility_regime=vol_regime,
            trend_regime=trend_regime,
            risk_regime=risk_regime,
            regime_age_bars=regime_age,
            transition_probability=transition,
            indicators=indicators,
        )

    def get_strategy_weights(self, regime: str) -> RegimeStrategyWeights:
        """Get recommended strategy weights for a given regime."""
        return self.STRATEGY_WEIGHTS.get(regime, self.STRATEGY_WEIGHTS[RegimeType.NORMAL])

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _rolling_vol(returns: Sequence[float], window: int) -> float:
        """Calculate rolling volatility (annualized std dev)."""
        if len(returns) < 2 or window < 2:
            return 0.0
        subset = returns[-window:]
        mean = sum(subset) / len(subset)
        var = sum((r - mean) ** 2 for r in subset) / (len(subset) - 1)
        return math.sqrt(var) * math.sqrt(252)

    @staticmethod
    def _estimate_regime_age(
        returns: Sequence[float], vol_ratio: float, price_vs_sma: float,
    ) -> int:
        """Estimate how many bars the current regime has persisted."""
        # Simple heuristic: count consecutive bars with same sign of return
        if not returns:
            return 0
        current_sign = 1 if returns[-1] >= 0 else -1
        age = 0
        for r in reversed(returns):
            if (r >= 0 and current_sign == 1) or (r < 0 and current_sign == -1):
                age += 1
            else:
                break
        return age
