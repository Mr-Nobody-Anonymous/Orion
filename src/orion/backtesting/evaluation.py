from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from math import sqrt
from typing import Sequence

from .engine import BacktestResult, vectorized_momentum_backtest


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    total_return: Decimal
    annualized_volatility: Decimal
    sharpe: Decimal
    sortino: Decimal
    max_drawdown: Decimal
    calmar: Decimal
    win_rate: Decimal
    profit_factor: Decimal | None
    observations: int


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    windows: tuple[BacktestResult, ...]
    aggregate_return: Decimal
    rejected_windows: int


def performance_metrics(prices: Sequence[float], result: BacktestResult, periods_per_year: int = 252) -> PerformanceMetrics:
    if len(prices) < 3:
        raise ValueError("at least three prices are required")
    returns = [Decimal(str(prices[index] / prices[index - 1] - 1)) for index in range(1, len(prices))]
    average = sum(returns, Decimal("0")) / len(returns)
    variance = sum((item - average) ** 2 for item in returns) / len(returns)
    volatility = Decimal(str(float(variance.sqrt()) * sqrt(periods_per_year))) if variance else Decimal("0")
    downside = [item for item in returns if item < 0]
    downside_variance = sum(item ** 2 for item in downside) / len(downside) if downside else Decimal("0")
    sharpe = Decimal("0") if variance == 0 else Decimal(str(float(average / variance.sqrt()) * sqrt(periods_per_year)))
    sortino = Decimal("0") if downside_variance == 0 else Decimal(str(float(average / downside_variance.sqrt()) * sqrt(periods_per_year)))
    equity = Decimal(str(prices[0]))
    peak = equity
    drawdowns: list[Decimal] = []
    for item in returns:
        equity *= 1 + item
        peak = max(peak, equity)
        drawdowns.append(equity / peak - 1)
    max_drawdown = min(drawdowns, default=Decimal("0"))
    annualized_return = (Decimal("1") + result.total_return) ** Decimal(str(periods_per_year / len(returns))) - 1
    calmar = Decimal("0") if max_drawdown == 0 else annualized_return / abs(max_drawdown)
    wins = sum(item > 0 for item in returns)
    gains = sum((item for item in returns if item > 0), Decimal("0"))
    losses = abs(sum((item for item in returns if item < 0), Decimal("0")))
    return PerformanceMetrics(result.total_return, volatility, sharpe, sortino, max_drawdown, calmar,
                              Decimal(wins) / len(returns), gains / losses if losses else None, len(returns))


def walk_forward_momentum(prices: Sequence[float], *, train_window: int = 20, test_window: int = 10) -> WalkForwardResult:
    if train_window < 6 or test_window < 2:
        raise ValueError("train_window must be at least 6 and test_window at least 2")
    windows: list[BacktestResult] = []
    rejected = 0
    for start in range(0, len(prices) - train_window - test_window + 1, test_window):
        train = prices[start:start + train_window]
        test = prices[start + train_window:start + train_window + test_window]
        lookback = 3 if train[-1] >= train[0] else 5
        try:
            window = vectorized_momentum_backtest(test, lookback=min(lookback, len(test) - 1))
        except ValueError:
            rejected += 1
            continue
        windows.append(window)
    if not windows:
        raise ValueError("insufficient prices for a walk-forward window")
    aggregate = sum((window.total_return for window in windows), Decimal("0")) / len(windows)
    return WalkForwardResult(tuple(windows), aggregate, rejected)
