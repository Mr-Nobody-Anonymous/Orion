"""Tests for the strategy-level baseline runner.

The baselines are the lower bound ORION must beat to claim an
intelligence advantage (per the 2026-08-28 external review). The
tests confirm that:

* Each baseline produces a non-trivial return series on a
  nontrivial price history.
* ``BuyAndHold`` is a real long position, not a degenerate zero.
* ``MomentumStrategy`` is long in uptrends, flat in downtrends.
* ``MeanReversionStrategy`` is the mirror image.
* ``RandomStrategy`` is deterministic for a given seed.
* Transaction costs reduce returns when turnover is high.
* The summary metrics are well-formed and finite.
* ``run_baseline_suite`` returns results for every baseline.
* The runner refuses nonsense inputs.
"""

from __future__ import annotations

import math
import random

import pytest

from orion.evaluation.baselines_strategies import (
    BuyAndHold,
    FactorNeutralBaseline,
    MeanReversionStrategy,
    MomentumStrategy,
    RandomNullStrategy,
    RandomStrategy,
    run_backtest,
    run_baseline_suite,
)


def _uptrend(n: int = 200) -> list[float]:
    return [100.0 * (1.001 ** i) for i in range(n)]


def _downtrend(n: int = 200) -> list[float]:
    return [200.0 * (0.999 ** i) for i in range(n)]


def _alternating(n: int = 200) -> list[float]:
    return [100.0 + (1.0 if i % 2 == 0 else -1.0) * 0.5 for i in range(n)]


# --------------------------------------------------------------------------- buy and hold


def test_buy_and_hold_is_always_long() -> None:
    s = BuyAndHold()
    for i in range(50):
        assert s.position(_uptrend(60), i) == 1.0


def test_buy_and_hold_matches_price_return_on_uptrend() -> None:
    prices = _uptrend(100)
    res = run_backtest(BuyAndHold(), prices, cost_per_trade=0.0)
    # With zero cost, the equity should grow at the same rate as the price.
    expected_final = prices[-1] / prices[0]
    assert res.final_equity == pytest.approx(expected_final, rel=1e-9)
    assert res.n_trades == 0  # no turnover
    assert res.metrics["hit_rate"] == pytest.approx(1.0)  # every bar is a win on a monotonic uptrend


def test_buy_and_hold_loses_on_downtrend() -> None:
    prices = _downtrend(100)
    res = run_backtest(BuyAndHold(), prices, cost_per_trade=0.0)
    assert res.final_equity < 1.0
    assert res.metrics["total_return"] < 0.0


# --------------------------------------------------------------------------- momentum


def test_momentum_long_on_uptrend_flat_on_downtrend() -> None:
    m = MomentumStrategy(lookback=20)
    # Uptrend: the trailing return is positive -> long
    assert m.position(_uptrend(60), 30) == 1.0
    # Downtrend: trailing return is negative -> flat
    assert m.position(_downtrend(60), 30) == 0.0


def test_momentum_lookback_validation() -> None:
    with pytest.raises(ValueError):
        MomentumStrategy(lookback=0)


def test_momentum_underperforms_buy_and_hold_with_costs() -> None:
    """The reviewer said: ORION must beat these after costs. The
    momentum baseline on a simple uptrend with realistic costs should
    NOT beat buy-and-hold because of the early lookback-period
    inactivity + the cost of repeatedly entering the market.
    """
    prices = _uptrend(500)
    cost = 0.001  # 10 bps per trade
    buy_hold = run_backtest(BuyAndHold(), prices, cost_per_trade=cost)
    momentum = run_backtest(MomentumStrategy(lookback=20), prices, cost_per_trade=cost)
    # On a clean uptrend with costs, B&H should beat momentum.
    assert buy_hold.final_equity > momentum.final_equity


# --------------------------------------------------------------------------- mean reversion


def test_mean_reversion_long_on_downtrend_flat_on_uptrend() -> None:
    m = MeanReversionStrategy(lookback=20)
    assert m.position(_downtrend(60), 30) == 1.0
    assert m.position(_uptrend(60), 30) == 0.0


def test_mean_reversion_validates_inputs() -> None:
    with pytest.raises(ValueError):
        MeanReversionStrategy(lookback=0)


# --------------------------------------------------------------------------- random


def test_random_strategy_is_deterministic_for_seed() -> None:
    r1 = RandomStrategy(seed=7, p_long=0.5)
    r2 = RandomStrategy(seed=7, p_long=0.5)
    # Same seed -> same sequence of positions
    for i in range(1, 50):
        assert r1.position(_alternating(60), i) == r2.position(_alternating(60), i)


def test_random_strategy_validates_p_long() -> None:
    with pytest.raises(ValueError):
        RandomStrategy(p_long=-0.1)
    with pytest.raises(ValueError):
        RandomStrategy(p_long=1.5)


def test_random_strategy_p_long_zero_is_always_flat() -> None:
    r = RandomStrategy(p_long=0.0)
    assert all(r.position(_uptrend(50), i) == 0.0 for i in range(1, 50))


def test_random_strategy_p_long_one_is_always_long() -> None:
    r = RandomStrategy(p_long=1.0)
    assert all(r.position(_uptrend(50), i) == 1.0 for i in range(1, 50))


# --------------------------------------------------------------------------- runner / metrics


def test_runner_rejects_too_short_prices() -> None:
    with pytest.raises(ValueError):
        run_backtest(BuyAndHold(), [100.0])
    with pytest.raises(ValueError):
        run_backtest(BuyAndHold(), [])


def test_runner_rejects_nonpositive_prices() -> None:
    with pytest.raises(ValueError):
        run_backtest(BuyAndHold(), [100.0, 0.0, 101.0])


def test_runner_rejects_negative_costs() -> None:
    with pytest.raises(ValueError):
        run_backtest(BuyAndHold(), _uptrend(50), cost_per_trade=-0.01)


def test_runner_rejects_nonpositive_equity() -> None:
    with pytest.raises(ValueError):
        run_backtest(BuyAndHold(), _uptrend(50), initial_equity=0.0)


def test_metrics_are_finite() -> None:
    res = run_backtest(MomentumStrategy(), _uptrend(200))
    for key, value in res.metrics.items():
        assert math.isfinite(value), f"{key} is not finite: {value}"


def test_higher_costs_reduce_final_equity_for_active_strategy() -> None:
    prices = _uptrend(500)
    low_cost = run_backtest(MomentumStrategy(), prices, cost_per_trade=0.0)
    high_cost = run_backtest(MomentumStrategy(), prices, cost_per_trade=0.01)
    assert high_cost.final_equity < low_cost.final_equity


def test_max_drawdown_is_non_positive() -> None:
    res = run_backtest(BuyAndHold(), _uptrend(200))
    assert res.metrics["max_drawdown"] <= 0.0


def test_sharpe_is_zero_for_constant_returns() -> None:
    """A perfectly monotonic price series with buy-and-hold produces
    strictly positive returns; the std is non-zero. So we cannot test
    for zero Sharpe directly. Instead we test the no-lookback random
    seed that always says flat: that produces zero returns and a
    zero-variance series, which the runner reports as Sharpe 0.0."""
    class AlwaysFlat:
        name = "always_flat"
        def position(self, prices, index):
            return 0.0
    res = run_backtest(AlwaysFlat(), _uptrend(200))
    assert res.metrics["sharpe"] == 0.0
    assert res.metrics["total_return"] == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- suite


def test_baseline_suite_returns_all_four_strategies() -> None:
    suite = run_baseline_suite(_uptrend(200))
    # The canonical suite per the 2026-08-28 review has 5 strategies:
    # buy-and-hold, momentum, mean-reversion, factor-neutral, random-null.
    assert set(suite.keys()) == {
        "buy_and_hold",
        "momentum",
        "mean_reversion",
        "factor_neutral",
        "random_null",
    }


def test_baseline_suite_results_are_independent() -> None:
    """Each strategy must produce a different equity curve (modulo ties)."""
    prices = _alternating(200)
    suite = run_baseline_suite(prices)
    finals = {name: r.final_equity for name, r in suite.items()}
    # At least three distinct values
    assert len(set(round(v, 6) for v in finals.values())) >= 3


# --------------------------------------------------------------------------- factor-neutral


def test_factor_neutral_is_half_when_history_too_short() -> None:
    """With insufficient history, factor-neutral is the neutral 0.5."""
    f = FactorNeutralBaseline(lookback=20)
    for i in range(20):
        assert f.position(_uptrend(50), i) == 0.5


def test_factor_neutral_is_half_when_prices_flat() -> None:
    """If the trailing return is exactly zero, momentum and mean-reversion
    both abstain and the position is the neutral 0.5."""
    f = FactorNeutralBaseline(lookback=5)
    flat = [100.0] * 50
    for i in range(10, 50):
        assert f.position(flat, i) == 0.5


def test_factor_neutral_is_one_on_pure_uptrend() -> None:
    """On a strictly increasing series, only momentum is active,
    so the position should be 1.0."""
    f = FactorNeutralBaseline(lookback=10)
    up = [100.0 + i for i in range(50)]
    for i in range(15, 50):
        assert f.position(up, i) == 1.0


def test_factor_neutral_is_zero_on_pure_downtrend() -> None:
    """On a strictly decreasing series, only mean-reversion is
    active, so the position should be 0.0."""
    f = FactorNeutralBaseline(lookback=10)
    down = [200.0 - i for i in range(50)]
    for i in range(15, 50):
        assert f.position(down, i) == 0.0


def test_factor_neutral_validates_lookback() -> None:
    with pytest.raises(ValueError):
        FactorNeutralBaseline(lookback=0)


def test_factor_neutral_does_not_beat_buy_and_hold_on_pure_uptrend() -> None:
    """On a clean uptrend, factor-neutral underperforms B&H
    because it actively takes the 0.5 neutral position most of
    the time rather than riding the full trend. This is the
    cost of factor neutrality."""
    prices = _uptrend(500)
    bh = run_backtest(BuyAndHold(), prices, cost_per_trade=0.001)
    fn = run_backtest(FactorNeutralBaseline(lookback=20), prices, cost_per_trade=0.001)
    assert bh.final_equity > fn.final_equity


def test_factor_neutral_cancels_momentum_and_mean_reversion_by_construction() -> None:
    """The whole point of factor-neutral is that it averages two
    opposing signals. Verify the construction: on the same
    price series, the factor-neutral position is the mean of
    the momentum and mean-reversion positions, ignoring the
    scaling that maps {0,1} -> {0,1} (factor-neutral maps
    {-1, 0, +1} -> {0, 0.5, 1}).
    """
    import random
    rng = random.Random(0)
    prices = [100.0]
    for _ in range(200):
        prices.append(prices[-1] * (1.0 + rng.gauss(0, 0.01)))
    m = MomentumStrategy(lookback=20)
    r = MeanReversionStrategy(lookback=20)
    fn = FactorNeutralBaseline(lookback=20)
    for i in range(25, 200):
        pm = m.position(prices, i)
        pr = r.position(prices, i)
        pfn = fn.position(prices, i)
        # pm, pr are in {0, 1}.  When pm == pr the signals agree
        # and factor-neutral is the neutral 0.5; when they
        # disagree, factor-neutral tilts toward whichever said
        # long.  More precisely:
        #   pm=1, pr=0 -> 1.0  (momentum)
        #   pm=0, pr=1 -> 0.0  (mean-reversion)
        #   pm=pr     -> 0.5
        if pm == 1.0 and pr == 0.0:
            assert pfn == 1.0
        elif pm == 0.0 and pr == 1.0:
            assert pfn == 0.0
        else:
            assert pfn == 0.5


# --------------------------------------------------------------------------- random_null


def test_random_null_strategy_is_a_separate_named_strategy() -> None:
    r = RandomNullStrategy(seed=42)
    assert r.name == "random_null"


def test_random_strategy_alias_preserved() -> None:
    """The old name 'random' is preserved as an alias for backward
    compatibility with any caller that registered it."""
    r = RandomStrategy(seed=42)
    assert r.name == "random"


def test_baseline_suite_preserves_reproducibility() -> None:
    prices = _alternating(200)
    suite1 = run_baseline_suite(prices)
    suite2 = run_baseline_suite(prices)
    for name in suite1:
        assert suite1[name].final_equity == suite2[name].final_equity


def test_backtest_result_as_dict_is_serialisable() -> None:
    import json
    res = run_backtest(MomentumStrategy(), _uptrend(100))
    payload = json.dumps(res.as_dict())
    assert "per_period_returns" in payload
    assert "metrics" in payload
