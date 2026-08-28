"""Tests for the P1-6 factor intelligence layer."""

from __future__ import annotations

import math

import pytest

from orion.portfolio.factors import (
    FACTOR_NAMES,
    FACTOR_REGISTRY,
    compute_factor_signal,
    factor_alpha_decomposition,
)


def test_factor_registry_is_not_empty() -> None:
    assert len(FACTOR_NAMES) >= 10
    assert "momentum" in FACTOR_NAMES
    assert "value" in FACTOR_NAMES
    assert "quality" in FACTOR_NAMES


def test_factor_library_rejects_duplicates() -> None:
    from orion.portfolio.factors.catalog import FactorDefinition, FactorLibrary
    with pytest.raises(ValueError):
        FactorLibrary(
            [
                FactorDefinition("momentum", "x", 10, lambda prices: 0.0),
                FactorDefinition("momentum", "y", 20, lambda prices: 0.0),
            ]
        )


def test_factor_lookup() -> None:
    momentum = FACTOR_REGISTRY.get("momentum")
    assert momentum.name == "momentum"
    assert momentum.lookback >= 20


def test_compute_factor_signal_returns_signal() -> None:
    prices = [100 + i * 0.1 for i in range(60)]
    signal = compute_factor_signal("momentum", prices)
    assert signal.name == "momentum"
    assert -1.0 <= signal.value <= 1.0


def test_factor_signal_short_series_yields_nan() -> None:
    signal = compute_factor_signal("momentum", [100, 101, 102])
    assert math.isnan(signal.value)


def test_alpha_decomposition_runs_regression() -> None:
    strategy_returns = [0.01, -0.02, 0.03, -0.01, 0.02, 0.04, -0.03, 0.01, 0.0, 0.05]
    factor_returns = {
        "momentum": [0.005, -0.015, 0.020, -0.005, 0.010, 0.030, -0.020, 0.005, 0.0, 0.040],
        "value": [0.002, 0.001, -0.001, 0.003, -0.002, 0.004, -0.001, 0.0, 0.001, 0.002],
        "quality": [0.001, -0.001, 0.002, 0.0, 0.001, 0.003, -0.001, 0.001, 0.0, 0.002],
        "size": [0.0, 0.0, 0.001, 0.0, 0.0, 0.0, 0.0, 0.001, 0.0, 0.0],
        "low-volatility": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "carry": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "growth": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "profitability": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "term-structure": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "liquidity": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "sentiment": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    report = factor_alpha_decomposition(
        strategy_returns,
        factor_returns,
        factor_names=("momentum", "value", "quality", "size"),
    )
    assert report.n_observations == 10
    assert len(report.factor_names) == 4
    assert report.r_squared > 0.0  # strategy correlates with momentum
    payload = report.as_dict()
    assert payload["factors"] == ["momentum", "value", "quality", "size"]
    assert "alpha" in payload


def test_alpha_decomposition_handles_nan() -> None:
    strategy_returns = [0.01, float("nan"), 0.02, 0.03, 0.01, 0.02]
    factor_returns = {
        "momentum": [0.005, 0.0, 0.010, 0.020, 0.005, 0.010],
        "value": [0.001, 0.001, 0.001, 0.001, 0.001, 0.001],
        "quality": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "size": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "low-volatility": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "carry": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "growth": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "profitability": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "term-structure": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "liquidity": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "sentiment": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    report = factor_alpha_decomposition(
        strategy_returns,
        factor_returns,
        factor_names=("momentum", "value"),
    )
    assert report.n_observations == 5  # NaN row dropped


def test_alpha_decomposition_rejects_short_input() -> None:
    with pytest.raises(ValueError):
        factor_alpha_decomposition(
            [0.01, 0.02],
            {"momentum": [0.0, 0.0], "value": [0.0, 0.0]},
            factor_names=("momentum", "value"),
        )


def test_alpha_decomposition_rejects_unknown_factor() -> None:
    with pytest.raises(KeyError):
        factor_alpha_decomposition(
            [0.01, 0.02, 0.03, 0.04, 0.05],
            {"momentum": [0.0, 0.0, 0.0, 0.0, 0.0]},
            factor_names=("momentum", "no-such-factor"),
        )
