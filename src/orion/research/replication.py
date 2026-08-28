"""Replication checks: an experiment claim is only retained if it replicates.

Replication re-runs the same specification on resampled/subsampled data with
different seeds and requires directional consistency. A result that only
appears on one specific window is treated as noise, not alpha.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Sequence

from ..backtesting.evaluation import performance_metrics
from ..backtesting.engine import vectorized_momentum_backtest


@dataclass(frozen=True, slots=True)
class ReplicationTrial:
    seed: int
    sample_fraction: float
    total_return: float
    sharpe: float


@dataclass(frozen=True, slots=True)
class ReplicationReport:
    trials: tuple[ReplicationTrial, ...]
    consistent_fraction: float
    replicates: bool
    required_consistency: float

    def as_dict(self) -> dict[str, object]:
        return {
            "trials": [
                {"seed": t.seed, "sample_fraction": t.sample_fraction,
                 "total_return": t.total_return, "sharpe": t.sharpe}
                for t in self.trials
            ],
            "consistent_fraction": self.consistent_fraction,
            "replicates": self.replicates,
            "required_consistency": self.required_consistency,
        }


def _subsample(prices: Sequence[float], fraction: float, rng: Random) -> list[float]:
    count = max(20, int(len(prices) * fraction))
    count = min(count, len(prices))
    start = rng.randint(0, len(prices) - count)
    return list(prices[start:start + count])


def replicate(
    prices: Sequence[float],
    *,
    lookback: int = 3,
    trials: int = 8,
    required_consistency: float = 0.6,
    seed: int = 7,
) -> ReplicationReport:
    """Re-run the strategy across random windows; require directional consistency.

    A trial "confirms" when its total return has the same sign as the
    full-sample result. If the full-sample result is ~zero, nothing can
    replicate and the report says so honestly.
    """
    if len(prices) < 20:
        raise ValueError("at least 20 prices are required for replication")
    if trials < 2:
        raise ValueError("at least two trials are required")
    if not 0 < required_consistency <= 1:
        raise ValueError("required_consistency must be within (0, 1]")
    baseline = vectorized_momentum_backtest(prices, lookback=lookback)
    baseline_sign = 1 if baseline.total_return > 0 else -1 if baseline.total_return < 0 else 0
    if baseline_sign == 0:
        return ReplicationReport((), 0.0, False, required_consistency)
    rng = Random(seed)
    confirmed = 0
    results: list[ReplicationTrial] = []
    for trial_index in range(trials):
        fraction = rng.uniform(0.5, 0.9)
        sample = _subsample(prices, fraction, rng)
        try:
            result = vectorized_momentum_backtest(sample, lookback=lookback)
            metrics = performance_metrics(sample, result)
        except ValueError:
            continue
        sign = 1 if result.total_return > 0 else -1
        confirmed += 1 if sign == baseline_sign else 0
        results.append(ReplicationTrial(seed + trial_index, fraction, float(result.total_return), float(metrics.sharpe)))
    if not results:
        return ReplicationReport((), 0.0, False, required_consistency)
    consistency = confirmed / len(results)
    return ReplicationReport(tuple(results), consistency, consistency >= required_consistency, required_consistency)
