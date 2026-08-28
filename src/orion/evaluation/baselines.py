"""Standard baselines for the evaluation lab.

A *baseline* here is a callable ``predict(prices) -> expected_return``.
Every baseline is stdlib-only and deterministic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


def naive_return(prices: Sequence[float], horizon: int = 1) -> float:
    """Last close / close ``horizon`` bars ago minus one."""
    if len(prices) < horizon + 1:
        return 0.0
    return prices[-1] / prices[-1 - horizon] - 1.0


def momentum_baseline(prices: Sequence[float], lookback: int = 20) -> float:
    if len(prices) <= lookback:
        return 0.0
    return prices[-1] / prices[-1 - lookback] - 1.0


def mean_reversion_baseline(prices: Sequence[float], lookback: int = 20) -> float:
    """If the last price is above the rolling mean, predict a negative return."""
    if len(prices) <= lookback:
        return 0.0
    window = prices[-lookback:]
    mean = sum(window) / len(window)
    if mean == 0:
        return 0.0
    return -((prices[-1] / mean) - 1.0) * 0.1  # dampened


def random_baseline(prices: Sequence[float], horizon: int = 1, seed: int = 0) -> float:
    rng = random.Random(seed + len(prices))
    return rng.gauss(0.0, 0.01)


def ridge_baseline(prices: Sequence[float], lookback: int = 20) -> float:
    """A small linear regression on the trailing log-prices."""
    if len(prices) < lookback + 1:
        return 0.0
    xs = list(range(lookback))
    ys = [prices[-lookback + i] for i in range(lookback)]
    if any(y <= 0 for y in ys):
        return 0.0
    log_ys = [__import__("math").log(y) for y in ys]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(log_ys) / n
    num = sum((xs[i] - mean_x) * (log_ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0.0
    return slope  # per-step log return


BASELINE_REGISTRY: dict[str, callable] = {
    "naive": naive_return,
    "momentum": momentum_baseline,
    "mean_reversion": mean_reversion_baseline,
    "random": random_baseline,
    "ridge": ridge_baseline,
}


@dataclass(frozen=True, slots=True)
class BaselinePrediction:
    name: str
    expected_return: float
    horizon: int = 1
