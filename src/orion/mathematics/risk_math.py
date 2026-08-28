"""Risk mathematics: VaR, CVaR, Kelly sizing, drawdowns, risk parity.

All computations are historical/closed-form. Parametric VaR assumes i.i.d.
normal returns and is labeled as such; it is an estimate, never a guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from .statistics import normal_quantile


def historical_var(returns: Sequence[float], *, confidence: float = 0.95) -> float:
    """Historical Value-at-Risk (positive number = loss) at the given confidence."""
    if not returns:
        raise ValueError("returns must be non-empty")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    ordered = sorted(returns)
    index = max(0, round((1 - confidence) * len(ordered)) - 1)
    return -ordered[index]


def parametric_var(returns: Sequence[float], *, confidence: float = 0.95) -> float:
    """Normal-distribution VaR; assumes i.i.d. normal returns (an estimate)."""
    if len(returns) < 2:
        raise ValueError("parametric VaR requires at least two returns")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    mean = fmean(returns)
    std = (sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
    z = normal_quantile(1 - confidence)
    return -(mean + z * std)


def conditional_var(returns: Sequence[float], *, confidence: float = 0.95) -> float:
    """Expected Shortfall (CVaR): mean loss beyond the VaR threshold."""
    if not returns:
        raise ValueError("returns must be non-empty")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    ordered = sorted(returns)
    tail_size = max(1, int(round((1 - confidence) * len(ordered))))
    tail = ordered[:tail_size]
    return -fmean(tail)


@dataclass(frozen=True, slots=True)
class KellyResult:
    full_kelly: float
    half_kelly: float
    quarter_kelly: float


def kelly_criterion(win_probability: float, win_loss_ratio: float) -> KellyResult:
    """Kelly fraction for binary bets; negative means the bet should not be taken."""
    if not 0 <= win_probability <= 1:
        raise ValueError("win_probability must be within [0, 1]")
    if win_loss_ratio <= 0:
        raise ValueError("win_loss_ratio must be positive")
    fraction = (win_probability * win_loss_ratio - (1 - win_probability)) / win_loss_ratio
    fraction = max(-1.0, min(1.0, fraction))
    return KellyResult(fraction, fraction / 2.0, fraction / 4.0)


def continuous_kelly(expected_return: float, variance: float) -> KellyResult:
    """Kelly fraction for continuous returns: f* = mu / sigma^2."""
    if variance <= 0:
        raise ValueError("variance must be positive")
    fraction = max(-1.0, min(1.0, expected_return / variance))
    return KellyResult(fraction, fraction / 2.0, fraction / 4.0)


@dataclass(frozen=True, slots=True)
class DrawdownReport:
    max_drawdown: float
    current_drawdown: float
    longest_drawdown_days: int
    drawdown_series: tuple[float, ...]


def drawdown_series(equity_curve: Sequence[float]) -> DrawdownReport:
    """Drawdown statistics from an equity curve (negative values = underwater)."""
    if not equity_curve or any(v <= 0 for v in equity_curve):
        raise ValueError("equity curve must be non-empty and strictly positive")
    peak = equity_curve[0]
    series: list[float] = []
    longest = current_length = 0
    for value in equity_curve:
        peak = max(peak, value)
        if value < peak:
            current_length += 1
        else:
            current_length = 0
        longest = max(longest, current_length)
        series.append(value / peak - 1.0)
    return DrawdownReport(min(series), series[-1], longest, tuple(series))


def risk_parity_weights(vols: Sequence[float]) -> tuple[float, ...]:
    """Inverse-volatility risk parity weights (normalized, sum to 1)."""
    if not vols or any(v <= 0 for v in vols):
        raise ValueError("volatilities must be non-empty and strictly positive")
    inverse = [1.0 / v for v in vols]
    total = sum(inverse)
    return tuple(v / total for v in inverse)


def ulcer_index(equity_curve: Sequence[float]) -> float:
    """Ulcer index: RMS of percentage drawdowns (higher = worse)."""
    report = drawdown_series(equity_curve)
    return (sum(d * d for d in report.drawdown_series) / len(report.drawdown_series)) ** 0.5


__all__ = [
    "DrawdownReport",
    "KellyResult",
    "conditional_var",
    "continuous_kelly",
    "drawdown_series",
    "historical_var",
    "kelly_criterion",
    "parametric_var",
    "risk_parity_weights",
    "ulcer_index",
]
