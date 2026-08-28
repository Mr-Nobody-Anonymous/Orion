"""Tests for walk-forward, Monte Carlo, stress testing, and robustness checks."""

from __future__ import annotations

from decimal import Decimal

import pytest

from orion.backtesting import (
    block_bootstrap_returns,
    detect_look_ahead_bias,
    detect_overfit,
    detect_survivorship_bias,
    evaluate_robustness,
    flash_crash,
    geometric_brownian_motion,
    liquidity_gap,
    parameter_sensitivity,
    purged_walk_forward,
    regime_break,
    run_stress_suite,
    volatility_spike,
    walk_forward,
)


def _prices() -> list[float]:
    return [100, 101, 102, 100, 99, 101, 103, 104, 102, 105, 107, 106, 108, 110, 109, 111, 113, 112, 114, 115, 116]


def test_walk_forward_runs_all_windows() -> None:
    report = walk_forward(_prices(), train_window=8, test_window=4)
    assert report.windows
    assert 0 <= report.consistency <= 1


def test_purged_walk_forward_preserves_gap() -> None:
    report = purged_walk_forward(_prices(), train_window=8, test_window=4, purge_window=2)
    for window in report.windows:
        assert window.test_start - window.train_end == 2


def test_walk_forward_rejects_short_series() -> None:
    with pytest.raises(ValueError):
        walk_forward([100, 101, 102], train_window=8, test_window=4)


def test_block_bootstrap_produces_aggregated_report() -> None:
    report = block_bootstrap_returns(_prices(), paths=20, horizon=10, seed=42, block_size=3)
    assert report.paths == 20
    assert report.terminal_p05 <= report.terminal_p50 <= report.terminal_p95
    assert 0 <= report.probability_of_loss <= 1


def test_geometric_brownian_motion_is_deterministic() -> None:
    a = geometric_brownian_motion(_prices(), paths=10, horizon=20, seed=1)
    b = geometric_brownian_motion(_prices(), paths=10, horizon=20, seed=1)
    assert a.terminal_mean == b.terminal_mean


def test_stress_scenarios_apply_to_prices() -> None:
    prices = _prices()
    crash = flash_crash(prices, magnitude=0.2)
    assert crash[len(crash) // 2] < prices[len(crash) // 2]
    break_ = regime_break(prices, shift=0.1)
    midpoint = len(prices) // 2
    assert all(p < prices[midpoint + i] for i, p in enumerate(break_))
    spike = volatility_spike(prices, factor=2.0, window=3)
    assert spike != list(prices)
    gap = liquidity_gap(prices, gap=0.05)
    assert gap[-1] != prices[-1]


def test_run_stress_suite_returns_results() -> None:
    results = run_stress_suite(_prices())
    assert len(results) >= 1
    for r in results:
        assert r.scenario
        assert r.result.total_return is not None


def test_parameter_sensitivity_keys_are_lookbacks() -> None:
    sensitivity = parameter_sensitivity(_prices(), lookbacks=(2, 5, 8))
    assert set(sensitivity.keys()) == {2, 5, 8}


def test_look_ahead_bias_detector_handles_flat_series() -> None:
    # Flat series should not produce a non-zero return.
    from orion.backtesting.engine import vectorized_momentum_backtest
    result = vectorized_momentum_backtest([100] * 10, lookback=3)
    assert abs(result.total_return) < Decimal("0.0001")
    # The detector returns False when the backtest is valid and the return is within tolerance.
    assert detect_look_ahead_bias([100] * 10) is False


def test_overfit_detector_flags_severe_degradation() -> None:
    assert detect_overfit(in_sample_sharpe=2.0, out_of_sample_sharpe=0.5) is True
    assert detect_overfit(in_sample_sharpe=1.0, out_of_sample_sharpe=0.9) is False


def test_survivorship_bias_detector_flags_large_gap() -> None:
    train = [Decimal("0.10"), Decimal("0.12"), Decimal("0.08")]
    test = [Decimal("-0.05"), Decimal("-0.10")]
    assert detect_survivorship_bias(train, test) is True


def test_evaluate_robustness_passes_with_stable_inputs() -> None:
    report = evaluate_robustness(_prices(), in_sample_sharpe=1.0, out_of_sample_sharpe=0.8)
    assert report.is_robust
    assert "no_obvious_overfit" in report.passes
