"""Machine-learning forecaster: deterministic online ridge regression.

A real, trainable, dependency-free learning model on the prediction path.
It learns a linear mapping from lagged returns to forward return via
deterministic gradient descent, supports save/restore of weights (model
versioning), and reports honest out-of-sample metrics. This is the baseline
that heavyweight libraries (QLib LightGBM, Kronos, TSlib) must beat before
they can be promoted through the governance gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from ...data.contracts import Asset, Prediction

__all__ = ["MLRidgeForecaster"]


def _features(prices: Sequence[float], index: int, lags: int) -> list[float] | None:
    """Lagged return features ending at `index`; None when history is short."""
    if index < lags + 1:
        return None
    feats: list[float] = []
    for lag in range(1, lags + 1):
        prev, curr = prices[index - lag], prices[index - lag - 1]
        if prev <= 0 or curr <= 0:
            return None
        feats.append(curr / prev - 1)
    # volatility feature over the lag window
    window = prices[index - lags: index + 1]
    if any(p <= 0 for p in window):
        return None
    returns = [window[i] / window[i - 1] - 1 for i in range(1, len(window))]
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    feats.append(var ** 0.5)
    return feats


class MLRidgeForecaster:
    """Linear ridge model over lagged returns, trained by gradient descent.

    Weights persist via to_state/from_state so a trained model is a real,
    versioned artifact. `fit` returns train/validation errors so callers can
    judge generalization rather than memorization.
    """

    def __init__(self, *, lags: int = 5, learning_rate: float = 0.02,
                 epochs: int = 300, l2: float = 0.01) -> None:
        if lags < 2:
            raise ValueError("lags must be at least 2")
        if learning_rate <= 0 or epochs < 1 or l2 < 0:
            raise ValueError("invalid hyperparameters")
        self.lags = lags
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.l2 = l2
        self.name = "orion-ml-ridge"
        self.weights: list[float] | None = None
        self.bias = 0.0

    # ---------------------------------------------------------------- data
    def _dataset(self, prices: Sequence[float]) -> tuple[list[list[float]], list[float]] | None:
        xs: list[list[float]] = []
        ys: list[float] = []
        for index in range(len(prices) - 1):
            feats = _features(prices, index, self.lags)
            if feats is None:
                continue
            target = prices[index + 1] / prices[index] - 1
            xs.append(feats)
            ys.append(target)
        if not xs:
            return None
        return xs, ys

    # ---------------------------------------------------------------- training
    def fit(self, prices: Sequence[float], *, validation_fraction: float = 0.25) -> dict[str, float]:
        if len(prices) < self.lags + 3:
            raise ValueError("not enough price history to train")
        dataset = self._dataset(prices)
        if dataset is None:
            raise ValueError("no valid training examples could be built")
        xs, ys = dataset
        split = int(len(xs) * (1 - validation_fraction))
        if split < 1 or split >= len(xs):
            split = max(1, len(xs) - 1)
        train_x, train_y = xs[:split], ys[:split]
        val_x, val_y = xs[split:], ys[split:]

        dim = len(train_x[0])
        self.weights = [0.0] * dim
        self.bias = 0.0
        n = len(train_x)
        for _ in range(self.epochs):
            grad_w = [0.0] * dim
            grad_b = 0.0
            for x_row, y in zip(train_x, train_y):
                pred = self.bias + sum(w * f for w, f in zip(self.weights, x_row))
                error = pred - y
                for j in range(dim):
                    grad_w[j] += error * x_row[j]
                grad_b += error
            for j in range(dim):
                grad_w[j] = grad_w[j] / n + self.l2 * self.weights[j]
            grad_b /= n
            for j in range(dim):
                self.weights[j] -= self.learning_rate * grad_w[j]
            self.bias -= self.learning_rate * grad_b

        def mse(xx, yy):
            if not yy:
                return float("nan")
            return sum(
                (self.bias + sum(w * f for w, f in zip(self.weights or (), x)) - y) ** 2
                for x, y in zip(xx, yy)
            ) / len(yy)

        return {
            "train_mse": mse(train_x, train_y),
            "validation_mse": mse(val_x, val_y),
            "train_examples": float(len(train_x)),
            "validation_examples": float(len(val_x)),
        }

    # ---------------------------------------------------------------- inference
    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        if self.weights is None:
            raise ValueError("model is not trained; call fit() first")
        feats = _features(prices, len(prices) - 1, self.lags)
        if feats is None or any(p <= 0 for p in prices):
            raise ValueError("at least three strictly positive prices are required")
        expected_change = self.bias + sum(w * f for w, f in zip(self.weights, feats))
        expected_change = max(-0.3, min(0.3, expected_change * 5))  # scale horizon
        vol = feats[-1]  # the volatility feature
        confidence = max(0.1, min(0.9, 0.85 - vol * 4))
        bullish = Decimal("0.55") if expected_change > 0 else Decimal("0.30")
        bearish = Decimal("0.30") if expected_change > 0 else Decimal("0.55")
        return Prediction(
            asset=asset,
            horizon=horizon,
            expected_return=Decimal(str(round(expected_change, 6))),
            probability_bull=bullish,
            probability_neutral=Decimal("1") - bullish - bearish,
            probability_bear=bearish,
            interval_low=Decimal(str(round(expected_change - 2 * vol, 6))),
            interval_high=Decimal(str(round(expected_change + 2 * vol, 6))),
            confidence=Decimal(str(round(confidence, 4))),
            model_name=self.name,
        )

    # ---------------------------------------------------------------- persistence
    def to_state(self) -> dict[str, object]:
        return {
            "name": self.name,
            "lags": self.lags,
            "weights": list(self.weights or []),
            "bias": self.bias,
        }

    def from_state(self, state: dict[str, object]) -> None:
        weights = state.get("weights")
        if state.get("lags") != self.lags or not isinstance(weights, list) or len(weights) != self.lags + 1:
            raise ValueError("state is incompatible with this model's configuration")
        self.weights = [float(w) for w in weights]
        self.bias = float(state.get("bias", 0.0))
