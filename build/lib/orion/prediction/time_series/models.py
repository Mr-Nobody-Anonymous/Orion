"""Pure-stdlib time-series forecasters used as ensemble members.

ORION keeps a deterministic, dependency-free set of statistical forecasters
that are always available, regardless of installed ML libraries. Heavier
deep-learning models live behind optional adapters and are not on the
critical path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, pstdev
from typing import Sequence

from ...data.contracts import Asset, Prediction


@dataclass(frozen=True, slots=True)
class TimeSeriesSpec:
    name: str
    horizon: str = "5d"


def _volatility(prices: Sequence[float]) -> float:
    if len(prices) < 2:
        return 0.0
    returns = [
        prices[i] / prices[i - 1] - 1
        for i in range(1, len(prices))
        if prices[i - 1] > 0
    ]
    return pstdev(returns) if len(returns) > 1 else 0.0


class MeanReversionForecaster:
    """Mean reversion: deviation from rolling mean drives the expected return."""

    name = "orion-mean-reversion"

    def __init__(self, window: int = 20) -> None:
        if window < 3:
            raise ValueError("window must be at least 3")
        self.window = window

    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        if len(prices) < 3 or prices[-1] <= 0:
            raise ValueError("at least three positive prices are required")
        window = min(self.window, len(prices))
        rolling_mean = mean(prices[-window:])
        last = prices[-1]
        deviation = (rolling_mean - last) / last
        expected = Decimal(str(max(-0.2, min(0.2, deviation * 0.5))))
        vol = _volatility(prices)
        confidence = Decimal(str(max(0.05, min(0.9, 0.8 - vol * 5))))
        bullish = Decimal("0.55") if deviation > 0 else Decimal("0.30")
        bearish = Decimal("0.30") if deviation > 0 else Decimal("0.55")
        return Prediction(
            asset=asset,
            horizon=horizon,
            expected_return=expected,
            probability_bull=bullish,
            probability_neutral=Decimal("1") - bullish - bearish,
            probability_bear=bearish,
            interval_low=expected - Decimal(str(vol * 2)),
            interval_high=expected + Decimal(str(vol * 2)),
            confidence=confidence,
            model_name=self.name,
        )


class VolatilityForecaster:
    """Returns the expected *volatility* (not direction) over the horizon."""

    name = "orion-volatility"

    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        if len(prices) < 3 or prices[-1] <= 0:
            raise ValueError("at least three positive prices are required")
        vol = _volatility(prices)
        expected = Decimal("0")
        confidence = Decimal(str(max(0.1, min(0.95, 1 - vol * 4))))
        return Prediction(
            asset=asset,
            horizon=horizon,
            expected_return=expected,
            probability_bull=Decimal("0.40"),
            probability_neutral=Decimal("0.20"),
            probability_bear=Decimal("0.40"),
            interval_low=Decimal(str(-2 * vol)),
            interval_high=Decimal(str(2 * vol)),
            confidence=confidence,
            model_name=self.name,
        )


class MomentumForecaster:
    """Pure trend-following baseline."""

    name = "orion-momentum"

    def __init__(self, lookback: int = 5) -> None:
        if lookback < 2:
            raise ValueError("lookback must be at least 2")
        self.lookback = lookback

    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        if len(prices) <= self.lookback or prices[-1] <= 0:
            raise ValueError("not enough history for the requested lookback")
        change = prices[-1] / prices[-1 - self.lookback] - 1
        vol = _volatility(prices)
        expected = Decimal(str(max(-0.3, min(0.3, change * 0.5))))
        confidence = Decimal(str(max(0.05, min(0.95, 1 - vol * 4))))
        bullish = Decimal("0.6") if change > 0 else Decimal("0.25")
        bearish = Decimal("0.25") if change > 0 else Decimal("0.6")
        return Prediction(
            asset=asset,
            horizon=horizon,
            expected_return=expected,
            probability_bull=bullish,
            probability_neutral=Decimal("1") - bullish - bearish,
            probability_bear=bearish,
            interval_low=expected - Decimal(str(vol * 2)),
            interval_high=expected + Decimal(str(vol * 2)),
            confidence=confidence,
            model_name=self.name,
        )



class ExponentiallyWeightedForecaster:
    """EWMA-weighted linear trend."""

    name = "orion-ewma-trend"

    def __init__(self, alpha: float = 0.3) -> None:
        if not 0 < alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        self.alpha = alpha

    def predict(self, asset, prices, horizon: str = "5d"):
        from decimal import Decimal
        from statistics import pstdev
        if len(prices) < 3 or prices[-1] <= 0:
            raise ValueError("at least three positive prices are required")
        weight = 1.0
        weighted_sum = 0.0
        total_weight = 0.0
        for price in reversed(prices):
            weighted_sum += price * weight
            total_weight += weight
            weight *= 1 - self.alpha
        smoothed = weighted_sum / total_weight
        expected_change = (smoothed - prices[-1]) / prices[-1]
        returns = [
            prices[i] / prices[i - 1] - 1
            for i in range(1, len(prices))
            if prices[i - 1] > 0
        ]
        vol = pstdev(returns) if len(returns) > 1 else 0.0
        expected = Decimal(str(max(-0.3, min(0.3, expected_change * 0.5))))
        confidence = Decimal(str(max(0.1, min(0.9, 1 - vol * 5))))
        bullish = Decimal("0.55") if expected_change > 0 else Decimal("0.30")
        bearish = Decimal("0.30") if expected_change > 0 else Decimal("0.55")
        from orion.data.contracts import Prediction
        return Prediction(
            asset=asset,
            horizon=horizon,
            expected_return=expected,
            probability_bull=bullish,
            probability_neutral=Decimal("1") - bullish - bearish,
            probability_bear=bearish,
            interval_low=expected - Decimal(str(vol * 2)),
            interval_high=expected + Decimal(str(vol * 2)),
            confidence=confidence,
            model_name=self.name,
        )


def build_default_timeseries_ensemble():
    return (MomentumForecaster(), MeanReversionForecaster(), ExponentiallyWeightedForecaster())


def stdlib_root_mean_square_error(predicted, actual):
    from math import sqrt
    if len(predicted) != len(actual) or not predicted:
        raise ValueError("sequences must be equal and non-empty")
    return sqrt(sum((p - a) ** 2 for p, a in zip(predicted, actual)) / len(predicted))
