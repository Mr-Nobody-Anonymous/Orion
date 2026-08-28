"""Pure-Python statistical primitives for ORION.

Everything here is deterministic and dependency-free. Numerical routines are
exact closed-form or bisection-based; there is no sampling unless a seed is
supplied by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, erfc, exp, log, pi, sqrt
from statistics import fmean
from typing import Sequence


def normal_pdf(x: float, *, mean: float = 0.0, std: float = 1.0) -> float:
    if std <= 0:
        raise ValueError("std must be positive")
    z = (x - mean) / std
    return exp(-0.5 * z * z) / (std * sqrt(2 * pi))


def normal_cdf(x: float, *, mean: float = 0.0, std: float = 1.0) -> float:
    if std <= 0:
        raise ValueError("std must be positive")
    return 0.5 * (1.0 + erf((x - mean) / (std * sqrt(2.0))))


def normal_sf(x: float, *, mean: float = 0.0, std: float = 1.0) -> float:
    """Survival function 1 - CDF, computed with erfc for tail accuracy."""
    if std <= 0:
        raise ValueError("std must be positive")
    return 0.5 * erfc((x - mean) / (std * sqrt(2.0)))


def normal_quantile(probability: float, *, mean: float = 0.0, std: float = 1.0,
                    tolerance: float = 1e-10) -> float:
    """Inverse CDF via bisection; exact to `tolerance` for the standard domain."""
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be strictly between 0 and 1")
    low, high = mean - 40.0 * std, mean + 40.0 * std
    while high - low > tolerance:
        mid = (low + high) / 2.0
        if normal_cdf(mid, mean=mean, std=std) < probability:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def sample_skewness(values: Sequence[float]) -> float:
    if len(values) < 3:
        raise ValueError("skewness requires at least three values")
    mean = fmean(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    if variance == 0:
        return 0.0
    third = sum((v - mean) ** 3 for v in values) / len(values)
    return third / variance ** 1.5


def sample_kurtosis(values: Sequence[float]) -> float:
    """Excess kurtosis (0 for a normal distribution)."""
    if len(values) < 4:
        raise ValueError("kurtosis requires at least four values")
    mean = fmean(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    if variance == 0:
        return 0.0
    fourth = sum((v - mean) ** 4 for v in values) / len(values)
    return fourth / variance ** 2 - 3.0


def jarque_bera(values: Sequence[float]) -> tuple[float, float]:
    """Jarque-Bera normality statistic and its chi-squared(2) p-value."""
    n = len(values)
    if n < 4:
        raise ValueError("jarque_bera requires at least four values")
    skew = sample_skewness(values)
    kurt = sample_kurtosis(values)
    statistic = n / 6.0 * (skew ** 2 + kurt ** 2 / 4.0)
    p_value = exp(-statistic / 2.0)  # survival function of chi2(2) is exp(-x/2)
    return statistic, p_value


@dataclass(frozen=True, slots=True)
class RegressionResult:
    slope: float
    intercept: float
    r_squared: float
    residual_std: float
    n: int

    def predict(self, x: float) -> float:
        return self.intercept + self.slope * x


@dataclass(frozen=True, slots=True)
class TTestResult:
    t_statistic: float
    degrees_of_freedom: float
    one_sided_p_value: float
    mean_difference: float


def linear_regression(x: Sequence[float], y: Sequence[float]) -> RegressionResult:
    """Ordinary least squares with R-squared and residual standard deviation."""
    if len(x) != len(y):
        raise ValueError("x and y must have equal length")
    if len(x) < 3:
        raise ValueError("linear regression requires at least three observations")
    mean_x, mean_y = fmean(x), fmean(y)
    sxx = sum((xi - mean_x) ** 2 for xi in x)
    if sxx == 0:
        raise ValueError("x must have non-zero variance")
    sxy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    residual_std = sqrt(ss_res / (len(x) - 2)) if len(x) > 2 else 0.0
    return RegressionResult(slope, intercept, max(0.0, r_squared), residual_std, len(x))


def welch_t_test(a: Sequence[float], b: Sequence[float]) -> TTestResult:
    """Welch's unequal-variance t-test (one-sided p-value, hypothesis a > b).

    The p-value uses the normal approximation to the t-distribution, which is
    adequate for the sample sizes ORION evaluates; it is an approximation and
    is reported as such.
    """
    if len(a) < 2 or len(b) < 2:
        raise ValueError("each sample requires at least two observations")
    mean_a, mean_b = fmean(a), fmean(b)
    var_a = sum((v - mean_a) ** 2 for v in a) / (len(a) - 1)
    var_b = sum((v - mean_b) ** 2 for v in b) / (len(b) - 1)
    se_sq = var_a / len(a) + var_b / len(b)
    if se_sq == 0:
        raise ValueError("both samples have zero variance")
    t_stat = (mean_a - mean_b) / sqrt(se_sq)
    numerator = se_sq ** 2
    denominator = (var_a / len(a)) ** 2 / (len(a) - 1) + (var_b / len(b)) ** 2 / (len(b) - 1)
    dof = numerator / denominator if denominator > 0 else float(len(a) + len(b) - 2)
    return TTestResult(t_stat, dof, normal_sf(t_stat), mean_a - mean_b)


def autocorrelation(values: Sequence[float], lag: int) -> float:
    if lag < 1:
        raise ValueError("lag must be at least one")
    if len(values) <= lag:
        raise ValueError("series too short for the requested lag")
    mean = fmean(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    if variance == 0:
        return 0.0
    covariance = sum(
        (values[i] - mean) * (values[i + lag] - mean) for i in range(len(values) - lag)
    ) / (len(values) - lag)
    return covariance / variance


def ljung_box(values: Sequence[float], *, max_lag: int = 5) -> tuple[float, float]:
    """Ljung-Box portmanteau statistic with a Wilson-Hilferty chi-squared p-value."""
    if max_lag < 1:
        raise ValueError("max_lag must be at least one")
    n = len(values)
    if n <= max_lag + 1:
        raise ValueError("series too short for the requested max_lag")
    statistic = 0.0
    for lag in range(1, max_lag + 1):
        r = autocorrelation(values, lag)
        statistic += r * r / (n - lag)
    statistic *= n * (n + 2)
    k, x = float(max_lag), statistic
    if k <= 0 or x <= 0:
        return statistic, 1.0
    z = ((x / k) ** (1.0 / 3.0) - (1 - 2 / (9 * k))) / sqrt(2 / (9 * k))
    p_value = normal_sf(z)
    return statistic, min(1.0, max(0.0, p_value))


def hurst_exponent(values: Sequence[float], *, min_chunk: int = 4) -> float:
    """Rescaled-range estimate of the Hurst exponent.

    H < 0.5 mean-reverting, H ~ 0.5 random walk, H > 0.5 trending.
    """
    if len(values) < min_chunk * 4:
        raise ValueError(f"hurst_exponent requires at least {min_chunk * 4} values")
    returns = [values[i] / values[i - 1] - 1.0 for i in range(1, len(values)) if values[i - 1] != 0]
    if len(returns) < min_chunk * 4:
        raise ValueError("series too short after return computation")
    log_points: list[tuple[float, float]] = []
    size = len(returns)
    chunk = min_chunk
    while chunk <= size // 2:
        n_chunks = size // chunk
        rs_values: list[float] = []
        for c in range(n_chunks):
            window = returns[c * chunk:(c + 1) * chunk]
            mean = fmean(window)
            cumulative = 0.0
            best = -float("inf")
            worst = float("inf")
            for v in window:
                cumulative += v - mean
                best = max(best, cumulative)
                worst = min(worst, cumulative)
            std = sqrt(sum((v - mean) ** 2 for v in window) / chunk)
            if std > 0:
                rs_values.append((best - worst) / std)
        if rs_values:
            average_rs = fmean(rs_values)
            if average_rs > 0:
                log_points.append((log(chunk), log(average_rs)))
        chunk *= 2
    if len(log_points) < 2:
        return 0.5
    regression = linear_regression([p for p, _ in log_points], [r for _, r in log_points])
    return regression.slope


__all__ = [
    "RegressionResult",
    "TTestResult",
    "autocorrelation",
    "hurst_exponent",
    "jarque_bera",
    "linear_regression",
    "ljung_box",
    "normal_cdf",
    "normal_pdf",
    "normal_quantile",
    "normal_sf",
    "sample_kurtosis",
    "sample_skewness",
    "welch_t_test",
]

