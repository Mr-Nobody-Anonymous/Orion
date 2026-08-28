"""Monte Carlo bootstrap backtesting.

A real ORION environment may want geometric Brownian motion or
block-bootstrap. This module implements both, with a deterministic seed,
and reports the empirical distribution of outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from random import Random
from statistics import mean, pstdev
from typing import Sequence

from ..engine import BacktestResult, vectorized_momentum_backtest


@dataclass(frozen=True, slots=True)
class MonteCarloReport:
    paths: int
    horizon: int
    seed: int
    terminal_mean: float
    terminal_p05: float
    terminal_p50: float
    terminal_p95: float
    terminal_min: float
    terminal_max: float
    probability_of_loss: float
    sharpe_distribution: tuple[float, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "paths": self.paths,
            "horizon": self.horizon,
            "seed": self.seed,
            "terminal_mean": self.terminal_mean,
            "terminal_p05": self.terminal_p05,
            "terminal_p50": self.terminal_p50,
            "terminal_p95": self.terminal_p95,
            "terminal_min": self.terminal_min,
            "terminal_max": self.terminal_max,
            "probability_of_loss": self.probability_of_loss,
            "sharpe_distribution": list(self.sharpe_distribution),
        }


def block_bootstrap_returns(
    prices: Sequence[float], *, paths: int, horizon: int, block_size: int = 5, seed: int = 7
) -> MonteCarloReport:
    """Generate return paths using a block bootstrap to preserve some serial structure."""
    if len(prices) < 3 or any(p <= 0 for p in prices):
        raise ValueError("prices must contain at least 3 positive observations")
    if paths < 1 or horizon < 1:
        raise ValueError("paths and horizon must be positive")
    if block_size < 1:
        raise ValueError("block_size must be at least 1")
    returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
    rng = Random(seed)
    terminals: list[float] = []
    sharpes: list[float] = []
    for _ in range(paths):
        last = float(prices[-1])
        path_returns: list[float] = []
        while len(path_returns) < horizon:
            block_start = rng.randint(0, max(0, len(returns) - block_size))
            for i in range(block_size):
                if len(path_returns) < horizon:
                    path_returns.append(returns[block_start + i] if block_start + i < len(returns) else 0.0)
        price_path = [last]
        for r in path_returns:
            price_path.append(price_path[-1] * (1 + r))
        terminals.append(price_path[-1])
        avg = mean(path_returns) if path_returns else 0.0
        sd = pstdev(path_returns) if len(path_returns) > 1 else 0.0
        sharpes.append((avg / sd) * sqrt(252) if sd > 0 else 0.0)
    terminals_sorted = sorted(terminals)
    last = float(prices[-1])
    loss_prob = sum(1 for t in terminals if t < last) / len(terminals)
    return MonteCarloReport(
        paths=paths,
        horizon=horizon,
        seed=seed,
        terminal_mean=mean(terminals),
        terminal_p05=_percentile(terminals_sorted, 0.05),
        terminal_p50=_percentile(terminals_sorted, 0.50),
        terminal_p95=_percentile(terminals_sorted, 0.95),
        terminal_min=min(terminals),
        terminal_max=max(terminals),
        probability_of_loss=loss_prob,
        sharpe_distribution=tuple(sharpes),
    )


def geometric_brownian_motion(
    prices: Sequence[float], *, paths: int, horizon: int, seed: int = 7
) -> MonteCarloReport:
    """Parametric GBM simulation using historical drift and volatility."""
    if len(prices) < 3 or any(p <= 0 for p in prices):
        raise ValueError("prices must contain at least 3 positive observations")
    returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
    mu = mean(returns)
    sigma = pstdev(returns) if len(returns) > 1 else 0.0
    last = float(prices[-1])
    rng = Random(seed)
    terminals: list[float] = []
    sharpes: list[float] = []
    for _ in range(paths):
        path = [last]
        path_returns: list[float] = []
        for _ in range(horizon):
            shock = rng.gauss(mu, sigma)
            path.append(path[-1] * (1 + shock))
            path_returns.append(shock)
        terminals.append(path[-1])
        avg = mean(path_returns) if path_returns else 0.0
        sd = pstdev(path_returns) if len(path_returns) > 1 else 0.0
        sharpes.append((avg / sd) * sqrt(252) if sd > 0 else 0.0)
    terminals_sorted = sorted(terminals)
    return MonteCarloReport(
        paths=paths,
        horizon=horizon,
        seed=seed,
        terminal_mean=mean(terminals),
        terminal_p05=_percentile(terminals_sorted, 0.05),
        terminal_p50=_percentile(terminals_sorted, 0.50),
        terminal_p95=_percentile(terminals_sorted, 0.95),
        terminal_min=min(terminals),
        terminal_max=max(terminals),
        probability_of_loss=sum(1 for t in terminals if t < last) / len(terminals),
        sharpe_distribution=tuple(sharpes),
    )


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("sorted_values must be non-empty")
    if not 0 <= q <= 1:
        raise ValueError("q must be between 0 and 1")
    index = max(0, min(len(sorted_values) - 1, int(round(q * (len(sorted_values) - 1)))))
    return sorted_values[index]


def monte_carlo_backtest(
    prices: Sequence[float], *, paths: int = 100, horizon: int = 20, seed: int = 7, lookback: int = 3
) -> dict[str, object]:
    """Apply the canonical momentum backtest to a panel of bootstrapped paths."""
    if len(prices) < 4 or any(p <= 0 for p in prices):
        raise ValueError("prices must contain at least 4 positive observations")
    returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
    rng = Random(seed)
    results: list[BacktestResult] = []
    for _ in range(paths):
        path = [float(prices[-1])]
        for _ in range(horizon):
            path.append(path[-1] * (1 + rng.choice(returns)))
        try:
            results.append(vectorized_momentum_backtest(path, lookback=lookback))
        except ValueError:
            continue
    if not results:
        raise ValueError("no paths produced a valid backtest")
    final_returns = [float(r.total_return) for r in results]
    return {
        "paths": len(results),
        "mean_return": mean(final_returns),
        "p05": _percentile(sorted(final_returns), 0.05),
        "p50": _percentile(sorted(final_returns), 0.50),
        "p95": _percentile(sorted(final_returns), 0.95),
        "stdev": pstdev(final_returns) if len(final_returns) > 1 else 0.0,
    }
