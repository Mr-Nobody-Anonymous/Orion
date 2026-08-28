"""Stress testing and scenario analysis.

Stress tests intentionally break the historical distribution to expose
fragility. The scenarios here are simple, transparent, and deterministic
so that they can be added to a regression suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Sequence

from ..engine import BacktestResult, vectorized_momentum_backtest
from ..evaluation import PerformanceMetrics, performance_metrics


@dataclass(frozen=True, slots=True)
class StressScenario:
    name: str
    description: str
    transform: Callable[[Sequence[float]], list[float]]


@dataclass(frozen=True, slots=True)
class StressResult:
    scenario: str
    prices: tuple[float, ...]
    result: BacktestResult
    metrics: PerformanceMetrics

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "return": str(self.result.total_return),
            "sharpe": str(self.metrics.sharpe),
            "max_drawdown": str(self.metrics.max_drawdown),
            "win_rate": str(self.metrics.win_rate),
        }


def flash_crash(prices: Sequence[float], *, magnitude: float = 0.30, index: int | None = None) -> list[float]:
    """Apply a sudden price drop to the series."""
    if magnitude <= 0 or magnitude >= 1:
        raise ValueError("magnitude must be between 0 and 1")
    out = list(prices)
    target = index if index is not None else len(out) // 2
    out[target] = out[target] * (1 - magnitude)
    return out


def regime_break(prices: Sequence[float], *, shift: float = 0.10) -> list[float]:
    """Apply a permanent level shift to the second half of the series."""
    if not 0 < shift < 1:
        raise ValueError("shift must be between 0 and 1")
    midpoint = len(prices) // 2
    return [p * (1 - shift) for p in prices[midpoint:]]


def volatility_spike(prices: Sequence[float], *, factor: float = 3.0, window: int = 5) -> list[float]:
    """Multiply short-window returns by `factor` to create a temporary volatility spike."""
    if not 1 < factor <= 10:
        raise ValueError("factor must be in (1, 10]")
    if window < 2 or window >= len(prices):
        raise ValueError("window must be at least 2 and smaller than the series length")
    out = list(prices)
    for i in range(window, min(len(out), window * 2)):
        out[i] = out[i - 1] * (1 + factor * (out[i] / out[i - 1] - 1))
    return out


def liquidity_gap(prices: Sequence[float], *, gap: float = 0.05, index: int | None = None) -> list[float]:
    """Insert a one-step gap up or down (sign chosen by gap)."""
    if not 0 < gap < 1:
        raise ValueError("gap must be between 0 and 1")
    out = list(prices)
    target = index if index is not None else len(out) - 2
    out[target + 1] = out[target] * (1 + gap)
    return out


DEFAULT_SCENARIOS: tuple[StressScenario, ...] = (
    StressScenario(
        name="flash_crash",
        description="A 30% sudden drop at the midpoint",
        transform=lambda p: flash_crash(p, magnitude=0.30),
    ),
    StressScenario(
        name="regime_break",
        description="A 10% permanent level shift in the second half",
        transform=lambda p: regime_break(p, shift=0.10),
    ),
    StressScenario(
        name="volatility_spike",
        description="Tripled returns in a 5-bar window",
        transform=lambda p: volatility_spike(p, factor=3.0, window=5),
    ),
    StressScenario(
        name="liquidity_gap",
        description="A 5% gap on the second-to-last bar",
        transform=lambda p: liquidity_gap(p, gap=0.05),
    ),
)


def run_stress_suite(
    prices: Sequence[float], *, lookback: int = 3, scenarios: Sequence[StressScenario] = DEFAULT_SCENARIOS
) -> tuple[StressResult, ...]:
    if lookback < 2:
        raise ValueError("lookback must be at least 2")
    results: list[StressResult] = []
    for scenario in scenarios:
        transformed = scenario.transform(prices)
        if len(transformed) <= lookback or any(p <= 0 for p in transformed):
            continue
        try:
            backtest = vectorized_momentum_backtest(transformed, lookback=lookback)
            metrics = performance_metrics(transformed, backtest)
        except ValueError:
            continue
        results.append(
            StressResult(
                scenario=scenario.name,
                prices=tuple(transformed),
                result=backtest,
                metrics=metrics,
            )
        )
    return tuple(results)
