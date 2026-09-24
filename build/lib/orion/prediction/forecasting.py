from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import mean, pstdev
from typing import Sequence

from ..domain import Asset, Prediction


class LinearTrendForecaster:
    """ORION-native statistical baseline retained for all local deployments."""

    name = "orion-linear-trend"

    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        if len(prices) < 3 or any(p <= 0 for p in prices):
            raise ValueError("at least three strictly positive prices are required")
        x_mean = (len(prices) - 1) / 2
        y_mean = mean(prices)
        denominator = sum((index - x_mean) ** 2 for index in range(len(prices)))
        slope = sum((index - x_mean) * (price - y_mean) for index, price in enumerate(prices)) / denominator
        steps = 5 if horizon.endswith("d") else 1
        expected = Decimal(str((slope * steps) / prices[-1]))
        volatility = pstdev([prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))])
        confidence = Decimal(str(max(0.05, min(0.95, 1 - volatility * 10))))
        bullish = Decimal("0.55") if expected >= 0 else Decimal("0.20")
        bearish = Decimal("0.20") if expected >= 0 else Decimal("0.55")
        return Prediction(asset, horizon, expected, bullish, Decimal("1") - bullish - bearish, bearish,
                          expected - Decimal(str(volatility * 2)), expected + Decimal(str(volatility * 2)), confidence, self.name)


@dataclass(frozen=True, slots=True)
class PredictionEnsemble:
    forecasters: tuple[LinearTrendForecaster, ...] = (LinearTrendForecaster(),)

    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        predictions = [model.predict(asset, prices, horizon) for model in self.forecasters]
        expected = sum((prediction.expected_return for prediction in predictions), Decimal("0")) / len(predictions)
        confidence = sum((prediction.confidence for prediction in predictions), Decimal("0")) / len(predictions)
        first = predictions[0]
        return Prediction(asset, horizon, expected, first.probability_bull, first.probability_neutral,
                          first.probability_bear, first.interval_low, first.interval_high, confidence, "ensemble")
