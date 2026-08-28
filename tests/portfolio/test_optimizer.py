"""Tests for the P2-5 portfolio optimiser."""

from __future__ import annotations

import math

import pytest

from orion.portfolio.optimizer import (
    drawdown_aware_weights,
    hierarchical_risk_parity,
    mean_variance,
    mvp_weights,
    risk_parity,
    volatility_targeting,
    tax_aware_rebalance,
)


def test_mvp_weights_sum_to_one() -> None:
    weights = mvp_weights(["A", "B", "C"], volatilities={"A": 0.2, "B": 0.3, "C": 0.25})
    total = sum(weights.weights.values())
    assert math.isclose(total, 1.0, abs_tol=1e-9)
    # Lowest vol should get the highest weight in a diagonal-cov MVO.
    assert weights.weights["A"] > weights.weights["B"]


def test_mvo_weights_handle_known_returns() -> None:
    weights = mean_variance(
        {"A": 0.10, "B": 0.05, "C": 0.02},
        volatilities={"A": 0.20, "B": 0.15, "C": 0.10},
        risk_aversion=5.0,
    )
    assert math.isclose(sum(weights.weights.values()), 1.0, abs_tol=1e-9)
    # Higher return + lower vol should get the largest weight.
    assert weights.weights["B"] > weights.weights["C"]


def test_mvo_rejects_negative_risk_aversion() -> None:
    with pytest.raises(ValueError):
        mean_variance({"A": 0.1, "B": 0.05}, volatilities={"A": 0.2, "B": 0.2}, risk_aversion=-1.0)


def test_risk_parity_with_diagonal_cov() -> None:
    n = 4
    cov = [[0.0] * n for _ in range(n)]
    vols = [0.1, 0.2, 0.3, 0.4]
    for i, v in enumerate(vols):
        cov[i][i] = v * v
    weights = risk_parity(["A", "B", "C", "D"], covariance=cov)
    assert math.isclose(sum(weights.weights.values()), 1.0, abs_tol=1e-6)
    # In a diagonal-cov risk-parity, the lowest-vol asset should carry the most.
    assert weights.weights["A"] > weights.weights["D"]


def test_risk_parity_with_zero_volatility_splits_evenly() -> None:
    weights = risk_parity(["A", "B"], volatilities={"A": 0.0, "B": 0.0})
    assert math.isclose(weights.weights["A"], 0.5, abs_tol=1e-9)


def test_hierarchical_risk_parity_runs() -> None:
    n = 3
    cov = [[0.04, 0.001, 0.0], [0.001, 0.09, 0.0], [0.0, 0.0, 0.16]]
    weights = hierarchical_risk_parity(["A", "B", "C"], covariance=cov)
    assert math.isclose(sum(weights.weights.values()), 1.0, abs_tol=1e-6)
    for w in weights.weights.values():
        assert w >= 0.0


def test_volatility_targeting_scales_base() -> None:
    base = {"A": 0.5, "B": 0.5}
    result = volatility_targeting(
        base,
        target_volatility=0.10,
        volatilities={"A": 0.20, "B": 0.30},
    )
    diagnostics = result.diagnostics
    assert "scale" in diagnostics
    assert math.isclose(diagnostics["ex_ante_vol"], 0.10, abs_tol=1e-9)


def test_volatility_targeting_caps_at_floor_and_ceiling() -> None:
    base = {"A": 1.0, "B": 0.0}
    floored = volatility_targeting(
        base,
        target_volatility=0.05,
        volatilities={"A": 0.5, "B": 0.0},
        cap=0.5,
    )
    assert floored.weights["A"] <= 0.5


def test_volatility_targeting_rejects_zero_target() -> None:
    with pytest.raises(ValueError):
        volatility_targeting(
            {"A": 1.0, "B": 0.0},
            target_volatility=0.0,
            volatilities={"A": 0.2, "B": 0.3},
        )


def test_drawdown_aware_shrinks_high_drawdown() -> None:
    base = {"A": 0.5, "B": 0.5}
    drawdowns = {"A": [100, 80, 60, 80, 100], "B": [100, 90, 80, 90, 100]}
    result = drawdown_aware_weights(base, drawdown_histories=drawdowns, target_max_drawdown=0.30)
    # A has drawdown 40%, B has 20%; only A is above the target.
    assert result.weights["A"] < result.weights["B"]


def test_tax_aware_rebalance_marks_loss_harvest() -> None:
    # Construct the cost basis so that the symbol being sold has an
    # unrealised loss: cost_basis is the dollar amount invested, and
    # the current value is what that position is worth today.
    target = {"A": 0.6, "B": 0.4}
    current = {"A": 0.8, "B": 0.2}
    # A: current value = 0.8 * 10000 = 8000; basis = 10000 → loss of 2000.
    # B: current value = 0.2 * 10000 = 2000; basis = 1000 → gain of 1000.
    cost_basis = {"A": 10000.0, "B": 1000.0}
    plan = tax_aware_rebalance(
        current_weights=current,
        target_weights=target,
        cost_basis=cost_basis,
        market_value=10000.0,
    )
    # Selling A from 0.8 → 0.6 should be flagged as loss-harvest.
    assert plan.loss_harvested >= 1
    payload = plan.as_dict()
    assert "trades" in payload
    assert payload["portfolio_value"] == 10000.0


def test_tax_aware_rebalance_rejects_zero_market_value() -> None:
    with pytest.raises(ValueError):
        tax_aware_rebalance(
            current_weights={"A": 0.5, "B": 0.5},
            target_weights={"A": 0.5, "B": 0.5},
            cost_basis={"A": 100.0, "B": 50.0},
            market_value=0.0,
        )
