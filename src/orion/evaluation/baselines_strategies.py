"""Strategy-level baseline runner.

The :mod:`orion.evaluation.baselines` module provides
*prediction*-level baselines (a function that turns a price
history into a predicted return). That is sufficient for the
prediction-only evaluation lab. Strategy-level baselines — the
kind the external review of 2026-08-28 said ORION must beat
before claiming any intelligence advantage — require more: a
position policy, an entry/exit signal, realistic transaction
costs, and a return series.

This module provides:

* :class:`Strategy` — a stateless policy that maps a price history
  to a *target position* (``-1.0`` to ``+1.0`` of equity).
* :class:`BacktestResult` — the structured outcome of a single
  backtest (per-period returns, equity curve, summary metrics).
* :func:`run_backtest` — apply a strategy to a price history with
  realistic frictions and produce a :class:`BacktestResult`.
* Four baseline strategies:

  - :class:`BuyAndHold` — long the asset for the entire period.
  - :class:`MomentumStrategy` — long when the trailing return is
    positive, flat otherwise.
  - :class:`MeanReversionStrategy` — long when the trailing
    return is negative, flat otherwise.
  - :class:`RandomStrategy` — a deterministic seeded random
    position policy; the negative control.

The runner is intentionally small. It is **not** a backtesting
engine. It is the simplest thing that can produce a per-strategy
return series so the rest of the system can compare them on
equal footing.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence


# --------------------------------------------------------------------------- strategies


class Strategy:
    """Base class for strategy-level baselines.

    A strategy is a pure function from a price history to a target
    position in [-1.0, +1.0]. +1.0 means "all-in long", -1.0 means
    "all-in short", 0.0 means "flat". Subclasses override
    :meth:`position`.
    """

    name: str = "abstract"

    def position(self, prices: Sequence[float], index: int) -> float:
        raise NotImplementedError


class BuyAndHold(Strategy):
    """Buy at the start, hold to the end. The lower bound every other
    strategy should beat on a long-only comparison."""

    name = "buy_and_hold"

    def position(self, prices: Sequence[float], index: int) -> float:
        return 1.0


class MomentumStrategy(Strategy):
    """Long when the trailing lookback return is positive, flat otherwise.

    A textbook 12-1 momentum signal: measure the return over the
    previous ``lookback`` bars; if positive, go long; if non-positive,
    go to cash. This is the most-cited equity factor in academic
    literature, and the baseline any momentum-based ORION
    intelligence must beat after costs.
    """

    name = "momentum"

    def __init__(self, lookback: int = 20) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        self.lookback = lookback

    def position(self, prices: Sequence[float], index: int) -> float:
        if index < self.lookback:
            return 0.0
        past = prices[index - self.lookback]
        if past <= 0:
            return 0.0
        ret = prices[index] / past - 1.0
        return 1.0 if ret > 0 else 0.0


class MeanReversionStrategy(Strategy):
    """Long when the trailing lookback return is negative.

    The mirror of momentum. The baseline any mean-reversion
    ORION intelligence must beat.
    """

    name = "mean_reversion"

    def __init__(self, lookback: int = 20) -> None:
        if lookback < 1:
            raise ValueError("lookback must be >= 1")
        self.lookback = lookback

    def position(self, prices: Sequence[float], index: int) -> float:
        if index < self.lookback:
            return 0.0
        past = prices[index - self.lookback]
        if past <= 0:
            return 0.0
        ret = prices[index] / past - 1.0
        return 1.0 if ret < 0 else 0.0


class RandomStrategy(Strategy):
    """A deterministic seeded random position policy.

    A negative control. If ORION cannot beat this, something is
    seriously wrong.
    """

    name = "random"

    def __init__(self, seed: int = 0, p_long: float = 0.5) -> None:
        if not 0.0 <= p_long <= 1.0:
            raise ValueError("p_long must be in [0, 1]")
        self.seed = seed
        self.p_long = p_long
        # Use a single seeded RNG for reproducibility
        self._rng = random.Random(seed)

    def position(self, prices: Sequence[float], index: int) -> float:
        return 1.0 if self._rng.random() < self.p_long else 0.0


# --------------------------------------------------------------------------- result


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Structured outcome of a backtest."""

    strategy: str
    per_period_returns: tuple[float, ...]
    equity_curve: tuple[float, ...]
    final_equity: float
    n_periods: int
    cost_per_trade: float
    n_trades: int
    metrics: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "per_period_returns": list(self.per_period_returns),
            "equity_curve": list(self.equity_curve),
            "final_equity": self.final_equity,
            "n_periods": self.n_periods,
            "cost_per_trade": self.cost_per_trade,
            "n_trades": self.n_trades,
            "metrics": dict(self.metrics),
        }


# --------------------------------------------------------------------------- runner


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if not math.isfinite(den) or abs(den) < 1e-12:
        return default
    return num / den


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _max_drawdown(equity: Sequence[float]) -> float:
    if len(equity) < 2:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        if value > peak:
            peak = value
        dd = _safe_div(value - peak, peak, default=0.0)
        if dd < max_dd:
            max_dd = dd
    return max_dd


def run_backtest(
    strategy: Strategy,
    prices: Sequence[float],
    *,
    cost_per_trade: float = 0.001,
    initial_equity: float = 1.0,
) -> BacktestResult:
    """Run a backtest on a price history with linear frictions.

    Parameters
    ----------
    strategy:
        The :class:`Strategy` to evaluate.
    prices:
        Strictly positive price history, oldest first. The runner
        iterates one bar at a time and applies the strategy's
        target position for the *next* bar.
    cost_per_trade:
        Proportional cost applied whenever the position changes
        (e.g. 0.001 = 10 bps round-trip assumption). The cost is
        applied to the absolute change in target position.
    initial_equity:
        Starting equity, normalised to 1.0 for direct comparability
        across strategies.

    Returns
    -------
    :class:`BacktestResult`
        Per-period returns, the equity curve, and summary metrics.
    """
    if len(prices) < 2:
        raise ValueError("at least two prices are required")
    if any(p <= 0 for p in prices):
        raise ValueError("all prices must be strictly positive")
    if not math.isfinite(cost_per_trade) or cost_per_trade < 0:
        raise ValueError("cost_per_trade must be a non-negative finite number")
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")

    n = len(prices)
    per_period_returns: list[float] = []
    equity_curve: list[float] = [initial_equity]
    position = strategy.position(prices, 0)
    n_trades = 0
    equity = initial_equity

    for i in range(1, n):
        prev_price = prices[i - 1]
        cur_price = prices[i]
        if prev_price <= 0:
            per_period_returns.append(0.0)
            equity_curve.append(equity)
            continue
        # Market return for the bar: position × relative price move.
        market_return = position * (cur_price / prev_price - 1.0)
        # The strategy's next target position.
        new_position = strategy.position(prices, i)
        # Transaction cost on the absolute change in position.
        turnover = abs(new_position - position)
        cost = turnover * cost_per_trade
        net_return = market_return - cost
        if turnover > 0:
            n_trades += 1
        per_period_returns.append(net_return)
        equity *= 1.0 + net_return
        equity_curve.append(equity)
        position = new_position

    # Summary metrics
    rets = per_period_returns
    n_periods = len(rets)
    total_return = equity / initial_equity - 1.0
    mean_ret = _mean(rets)
    std_ret = _std(rets)
    # Annualised return/vol assuming daily bars (252 trading days/year)
    # — this is a *rough* annualisation and only correct for daily
    # bars. The caller knows the bar frequency; we report both raw
    # and annualised numbers so the comparison is honest.
    ann_factor = 252.0
    if n_periods > 1:
        cagr = (equity / initial_equity) ** (ann_factor / n_periods) - 1.0
    else:
        cagr = 0.0
    sharpe = _safe_div(mean_ret * ann_factor, std_ret * math.sqrt(ann_factor))
    max_dd = _max_drawdown(equity_curve)
    # Hit rate
    wins = sum(1 for r in rets if r > 0)
    hit_rate = wins / n_periods if n_periods else 0.0
    # Turnover (sum of |Δposition|) normalised by # periods
    total_turnover = sum(abs(rets[i]) for i in range(n_periods))  # rough
    # Better: count position flips via the strategy's reported position
    # — not strictly necessary for a baseline.

    metrics = {
        "total_return": total_return,
        "cagr": cagr,
        "mean_period_return": mean_ret,
        "std_period_return": std_ret,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "hit_rate": hit_rate,
        "n_trades": float(n_trades),
    }
    return BacktestResult(
        strategy=strategy.name,
        per_period_returns=tuple(per_period_returns),
        equity_curve=tuple(equity_curve),
        final_equity=equity,
        n_periods=n_periods,
        cost_per_trade=cost_per_trade,
        n_trades=n_trades,
        metrics=metrics,
    )


# --------------------------------------------------------------------------- suite


def default_baselines() -> tuple[Strategy, ...]:
    """Return a fresh tuple of default baseline strategies.

    Each call returns a *new* set of instances. ``RandomStrategy``
    holds a mutable RNG; sharing instances across runs would leak
    state and break reproducibility.
    """
    return (
        BuyAndHold(),
        MomentumStrategy(),
        MeanReversionStrategy(),
        RandomStrategy(seed=42),
    )


# Backwards-compatible constant: do not mutate or use directly.
DEFAULT_BASELINES: tuple[Strategy, ...] = default_baselines()


def run_baseline_suite(
    prices: Sequence[float],
    *,
    cost_per_trade: float = 0.001,
    initial_equity: float = 1.0,
) -> dict[str, BacktestResult]:
    """Run the default baseline suite on a price history.

    Returns
    -------
    dict
        A mapping from strategy name to its :class:`BacktestResult`.
    """
    return {
        s.name: run_backtest(
            s, prices, cost_per_trade=cost_per_trade, initial_equity=initial_equity
        )
        for s in default_baselines()
    }
