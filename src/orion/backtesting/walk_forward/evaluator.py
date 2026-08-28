"""Walk-forward and rolling-window backtest evaluation.

Walk-forward testing is the primary defense against look-ahead bias: only
information available at the time of each decision is allowed to influence
each window's choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Sequence

from ..engine import BacktestResult, vectorized_momentum_backtest
from ..evaluation import PerformanceMetrics, performance_metrics


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    test_result: BacktestResult
    test_metrics: PerformanceMetrics

    def as_dict(self) -> dict[str, object]:
        return {
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "return": str(self.test_result.total_return),
            "sharpe": str(self.test_metrics.sharpe),
            "max_drawdown": str(self.test_metrics.max_drawdown),
        }


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    windows: tuple[WalkForwardWindow, ...]
    aggregate_return: Decimal
    aggregate_sharpe: Decimal
    consistency: float
    rejected_windows: int

    def as_dict(self) -> dict[str, object]:
        return {
            "aggregate_return": str(self.aggregate_return),
            "aggregate_sharpe": str(self.aggregate_sharpe),
            "consistency": self.consistency,
            "rejected_windows": self.rejected_windows,
            "windows": [w.as_dict() for w in self.windows],
        }


def walk_forward(
    prices: Sequence[float],
    *,
    train_window: int = 20,
    test_window: int = 10,
    lookback_strategy: Callable[[Sequence[float]], int] | None = None,
) -> WalkForwardReport:
    """Run a walk-forward evaluation with rolling train/test windows."""
    if train_window < 6 or test_window < 2:
        raise ValueError("train_window must be at least 6 and test_window at least 2")
    if len(prices) <= train_window + test_window:
        raise ValueError("not enough prices for any walk-forward window")
    strategy = lookback_strategy or _default_strategy
    windows: list[WalkForwardWindow] = []
    rejected = 0
    for start in range(0, len(prices) - train_window - test_window + 1, test_window):
        train = prices[start : start + train_window]
        test = prices[start + train_window : start + train_window + test_window]
        lookback = max(2, min(strategy(train), len(test) - 1))
        try:
            result = vectorized_momentum_backtest(test, lookback=lookback)
            metrics = performance_metrics(test, result)
        except ValueError:
            rejected += 1
            continue
        windows.append(
            WalkForwardWindow(
                train_start=start,
                train_end=start + train_window,
                test_start=start + train_window,
                test_end=start + train_window + test_window,
                test_result=result,
                test_metrics=metrics,
            )
        )
    if not windows:
        raise ValueError("no windows produced a valid result")
    aggregate_return = sum((w.test_result.total_return for w in windows), Decimal("0")) / len(windows)
    aggregate_sharpe = sum((w.test_metrics.sharpe for w in windows), Decimal("0")) / len(windows)
    wins = sum(1 for w in windows if w.test_result.total_return > 0)
    consistency = wins / len(windows)
    return WalkForwardReport(tuple(windows), aggregate_return, aggregate_sharpe, consistency, rejected)


def _default_strategy(train: Sequence[float]) -> int:
    if train[-1] >= train[0]:
        return 3
    return 5


def purged_walk_forward(
    prices: Sequence[float],
    *,
    train_window: int = 20,
    test_window: int = 10,
    purge_window: int = 2,
) -> WalkForwardReport:
    """Walk-forward with a purge window between train and test to prevent leakage."""
    if purge_window < 0:
        raise ValueError("purge_window must be non-negative")
    if len(prices) <= train_window + test_window + purge_window:
        raise ValueError("not enough prices for a purged walk-forward window")
    windows: list[WalkForwardWindow] = []
    rejected = 0
    stride = test_window
    start = 0
    while start + train_window + purge_window + test_window <= len(prices):
        train = prices[start : start + train_window]
        test = prices[start + train_window + purge_window : start + train_window + purge_window + test_window]
        lookback = max(2, min(_default_strategy(train), len(test) - 1))
        try:
            result = vectorized_momentum_backtest(test, lookback=lookback)
            metrics = performance_metrics(test, result)
        except ValueError:
            rejected += 1
            start += stride
            continue
        windows.append(
            WalkForwardWindow(
                train_start=start,
                train_end=start + train_window,
                test_start=start + train_window + purge_window,
                test_end=start + train_window + purge_window + test_window,
                test_result=result,
                test_metrics=metrics,
            )
        )
        start += stride
    if not windows:
        raise ValueError("purged walk-forward produced no windows")
    aggregate_return = sum((w.test_result.total_return for w in windows), Decimal("0")) / len(windows)
    aggregate_sharpe = sum((w.test_metrics.sharpe for w in windows), Decimal("0")) / len(windows)
    wins = sum(1 for w in windows if w.test_result.total_return > 0)
    consistency = wins / len(windows)
    return WalkForwardReport(tuple(windows), aggregate_return, aggregate_sharpe, consistency, rejected)
