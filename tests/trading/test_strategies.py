"""Smoke tests for the strategy catalog.

These tests are intentionally lightweight: they verify that the
strategy module and all of its public names import correctly, and
that each strategy returns a structurally valid :class:`TradeProposal`
on a simple price series.  The full backtest engine is exercised
in :mod:`tests.backtesting`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from orion.data.contracts import Action, Asset, AssetClass
from orion.trading.strategies import (
    StrategyContext,
    equal_weight_rebalance,
    mean_reversion_strategy,
    momentum_strategy,
    risk_parity_weights,
    volatility_breakout_strategy,
)
from orion.trading.strategies.catalog import (
    StrategyContext as DirectStrategyContext,
    equal_weight_rebalance as direct_equal_weight_rebalance,
    mean_reversion_strategy as direct_mean_reversion_strategy,
    momentum_strategy as direct_momentum_strategy,
    risk_parity_weights as direct_risk_parity_weights,
    volatility_breakout_strategy as direct_volatility_breakout_strategy,
)


def _ctx(prices: list[float]) -> StrategyContext:
    return StrategyContext(
        asset=Asset("DEMO", AssetClass.EQUITY),
        prices=tuple(prices),
        equity=Decimal("100000"),
        exposure=Decimal("0"),
    )


def test_module_imports_cleanly() -> None:
    """The catalog module and its public re-exports must be importable."""
    assert DirectStrategyContext is StrategyContext
    assert direct_momentum_strategy is momentum_strategy
    assert direct_mean_reversion_strategy is mean_reversion_strategy
    assert direct_volatility_breakout_strategy is volatility_breakout_strategy
    assert direct_equal_weight_rebalance is equal_weight_rebalance
    assert direct_risk_parity_weights is risk_parity_weights


def test_momentum_strategy_produces_valid_proposal() -> None:
    ctx = _ctx([100, 101, 102, 103, 104, 105])
    proposal = momentum_strategy(ctx)
    assert proposal.order.asset.symbol == "DEMO"
    assert proposal.order.side in {Action.BUY, Action.SELL}
    assert proposal.order.quantity > 0
    assert "momentum" in proposal.rationale


def test_momentum_strategy_rejects_short_history() -> None:
    ctx = _ctx([100, 101])
    with pytest.raises(ValueError):
        momentum_strategy(ctx, lookback=5)


def test_mean_reversion_strategy_produces_valid_proposal() -> None:
    ctx = _ctx([100, 100, 100, 100, 110, 100, 100])
    proposal = mean_reversion_strategy(ctx)
    assert proposal.order.side in {Action.BUY, Action.SELL}
    assert proposal.order.quantity > 0


def test_volatility_breakout_strategy_produces_valid_proposal() -> None:
    ctx = _ctx([100, 101, 102, 103, 104, 105, 110, 111, 112, 113, 150])
    proposal = volatility_breakout_strategy(ctx, lookback=5, k=0.5)
    assert proposal.order.side in {Action.BUY, Action.SELL, Action.HOLD}


def test_equal_weight_rebalance_returns_orders() -> None:
    aapl = Asset("AAPL", AssetClass.EQUITY)
    msft = Asset("MSFT", AssetClass.EQUITY)
    orders = equal_weight_rebalance(
        [aapl, msft],
        {aapl: Decimal("0"), msft: Decimal("0")},
        Decimal("20000"),
        price_lookup=lambda asset: 100.0,
    )
    assert len(orders) == 2
    assert all(o.side == Action.BUY for o in orders)


def test_risk_parity_weights_returns_weights() -> None:
    weights = risk_parity_weights(
        {
            "AAPL": [0.01, 0.02, -0.01, 0.03, 0.0, 0.01],
            "MSFT": [0.0, 0.0, 0.01, -0.02, 0.01, 0.0],
        }
    )
    assert set(weights.keys()) == {"AAPL", "MSFT"}
    assert all(w >= 0 for w in weights.values())
    assert abs(sum(weights.values()) - 1.0) < 1e-9
