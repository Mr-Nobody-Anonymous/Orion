"""Descriptive statistics and distribution diagnostics for ORION.

These are the deterministic, dependency-free statistical primitives used by
forecast evaluation, regime detection, and backtest reporting. They are always
available regardless of installed scientific libraries.
"""

from __future__ import annotations

from math import erf, sqrt
from statistics import fmean, pstdev
from typing import Sequence

__all__ = [
    "mean_std",
    "percentile",
    "skewness",
    "excess_kurtosis",
    "normal_cdf",
    "jarque_bera",
    "correlation",
    "rolling_mean",
    "rolling_volatility",
    "max_drawdown",
    "hit_rate",
    "confidence_interval",
]


def mean_std(values: Sequence[float]) -> tuple[float, float]:
    """Return (mean, population standard deviation) of a non-empty sequence."""
    if not values:
        raise ValueError("at least one value is required")
    if len(values) == 1:
        return float(values[0]), 0.0
    return fmean(values), pstdev(values)


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of pre-sorted values (q in [0, 100])."""
    if not sorted_values:
        raise ValueError("at least one value is required")
    if not 0 <= q <= 100:
        raise ValueError("q must be within [0, 100]")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * q / 100.0
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return float(sorted_values[low] * (1 - frac) + sorted_values[high] * frac)


def skewness(values: Sequence[float]) -> float:
    """Fisher-Pearson sample skewness. 0 for symmetric distributions."""
    if len(values) < 3:
        return 0.0
    mu, sigma = mean_std(values)
    if sigma == 0:
        return 0.0
    n = len(values)
    m3 = sum((v - mu) ** 3 for v in values) / n
    return m3 / sigma**3


def excess_kurtosis(values: Sequence[float]) -> float:
    """Excess kurtosis (0 for a normal distribution; fat tails are positive)."""
    if len(values) < 4:
        return 0.0
    mu, sigma = mean_std(values)
    if sigma == 0:
        return 0.0
    n = len(values)
    m4 = sum((v - mu) ** 4 for v in values) / n
    return m4 / sigma**4 - 3.0


def normal_cdf(x: float) -> float:
    """Standard normal CDF via erf."""
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def jarque_bera(values: Sequence[float]) -> tuple[float, float]:
    """Jarque-Bera normality statistic and approximate p-value.

    Returns (statistic, p_value). Large statistic / small p-value indicates
    the sample is unlikely to be normal — used by ORION to decide whether
    Gaussian tail assumptions are defensible.
    """
    if len(values) < 4:
        return 0.0, 1.0
    n = len(values)
    s = skewness(values)
    k = excess_kurtosis(values)
    statistic = (n / 6.0) * (s * s + 0.25 * k * k)
    # chi-square with 2 dof survival function: exp(-x/2)
    p_value = pow(2.718281828459045, -statistic / 2.0) if statistic > 0 else 1.0
    return statistic, min(1.0, max(0.0, p_value))


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation of two equal-length sequences."""
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("sequences must be equal length and at least 2")
    mx, sx = mean_std(xs)
    my, sy = mean_std(ys)
    if sx == 0 or sy == 0:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
    return cov / (sx * sy)


def rolling_mean(values: Sequence[float], window: int) -> list[float]:
    if window < 1 or len(values) < window:
        raise ValueError("window must be >= 1 and <= len(values)")
    return [fmean(values[i : i + window]) for i in range(len(values) - window + 1)]


def rolling_volatility(values: Sequence[float], window: int) -> list[float]:
    if window < 2 or len(values) < window:
        raise ValueError("window must be >= 2 and <= len(values)")
    return [pstdev(values[i : i + window]) for i in range(len(values) - window + 1)]


def max_drawdown(values: Sequence[float]) -> float:
    """Maximum peak-to-trough decline as a negative fraction."""
    if not values:
        raise ValueError("at least one value is required")
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def hit_rate(predictions: Sequence[float], actuals: Sequence[float]) -> float:
    """Fraction of predictions whose sign matches the actual outcome's sign."""
    if len(predictions) != len(actuals) or not predictions:
        raise ValueError("equal-length non-empty sequences required")
    hits = sum(
        1
        for p, a in zip(predictions, actuals)
        if (p > 0 and a > 0) or (p < 0 and a < 0)
    )
    return hits / len(predictions)


def confidence_interval(values: Sequence[float], level: float = 0.95) -> tuple[float, float]:
    """Gaussian confidence interval for the mean of `values`.

    Only defensible when jarque_bera does not reject normality; callers should
    check that before treating the interval as a fact.
    """
    if len(values) < 2:
        raise ValueError("at least two values are required")
    if not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    mu, sigma = mean_std(values)
    z = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}[round(level, 2)]
    half = z * sigma / sqrt(len(values))
    return mu - half, mu + half
