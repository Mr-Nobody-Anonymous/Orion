"""Tests for the contamination-safe benchmark suite."""

from __future__ import annotations

from decimal import Decimal

import pytest

from orion.benchmarking import (
    BenchmarkReport,
    benchmark_forecaster,
    benchmark_models,
    benchmark_strategies,
    build_default_report,
    build_comparison_report,
    compute_metrics,
    default_strategy_candidates,
    default_subjects,
    head_to_head,
)
from orion.data.contracts import Asset, Prediction

SERIES = [100.0, 101.0, 100.5, 102.0, 103.0, 104.0, 105.0, 100.0, 98.0, 101.0, 103.0, 99.0, 102.0, 104.0]


class _FlatForecaster:
    """Always predicts a fixed next-step return."""

    name = "flat"

    def __init__(self, value: float = 0.01) -> None:
        self.value = value

    def predict(self, asset: Asset, prices, horizon: str = "5d") -> Prediction:
        asset = asset or Asset(symbol="BENCH", asset_class=asset.asset_class)
        return Prediction(
            asset,
            horizon,
            Decimal(str(self.value)),
            Decimal("0.5"),
            Decimal("0.2"),
            Decimal("0.3"),
            Decimal("-0.1"),
            Decimal("0.1"),
            Decimal("0.5"),
            self.name,
        )


class _RecorderForecaster:
    """Records the windows it was given so tests can prove no future leaks."""

    name = "recorder"

    def __init__(self) -> None:
        self.seen: list[tuple[float, ...]] = []

    def predict(self, asset: Asset, prices, horizon: str = "5d") -> Prediction:
        self.seen.append(tuple(prices))
        return _FlatForecaster().predict(asset, prices, horizon)


def test_walk_forward_is_contamination_safe() -> None:
    """Every prediction window must end strictly before the scored bar."""
    recorder = _RecorderForecaster()
    predicted, actual, _ = benchmark_forecaster(recorder, SERIES, warmup=5)
    windows = recorder.seen
    assert len(windows) == len(predicted) == len(actual) == len(SERIES) - 5
    # The longest window seen must exclude the final bar.
    assert max(len(window) for window in windows) == len(SERIES) - 1
    # Every window is a strict prefix of the series: no bar after `t` leaks in.
    for window in windows:
        assert window == tuple(SERIES[: len(window)])
        assert len(window) < len(SERIES)


def test_short_series_rejected() -> None:
    with pytest.raises(ValueError):
        benchmark_forecaster(_FlatForecaster(), [100.0, 101.0], warmup=5)
    with pytest.raises(ValueError):
        benchmark_forecaster(_FlatForecaster(), SERIES, warmup=1)


def test_compute_metrics_is_exact() -> None:
    predicted = [0.01, -0.02, 0.005]
    actual = [0.02, -0.01, 0.0]
    metrics = compute_metrics("flat", predicted, actual)
    assert metrics.count == 3
    assert metrics.mae == pytest.approx((0.01 + 0.01 + 0.005) / 3)
    assert metrics.directional_accuracy == 1.0
    assert metrics.bias == pytest.approx(-0.005)
    assert metrics.rmse == pytest.approx(0.0086602540)


def test_empty_samples_score_zero() -> None:
    metrics = compute_metrics("none", [], [])
    assert metrics.count == 0
    assert metrics.score == 0.0
    assert metrics.failures == 0


def test_benchmark_models_deterministic_and_ranked() -> None:
    first = benchmark_models(default_subjects(), [SERIES], warmup=5)
    second = benchmark_models(default_subjects(), [SERIES], warmup=5)
    assert [item.metrics.subject for item in first] == [item.metrics.subject for item in second]
    scores = [item.metrics.score for item in first]
    assert scores == sorted(scores, reverse=True)
    assert all(item.metrics.count >= 1 for item in first)


def test_benchmark_models_aggregates_multiple_series() -> None:
    models = benchmark_models([_FlatForecaster()], [SERIES[:8], SERIES[4:]], warmup=3)
    assert len(models) == 1
    assert models[0].metrics.count == (len(SERIES[:8]) - 3) + (len(SERIES[4:]) - 3)


def test_strategy_benchmark_identical_inputs_identical_outputs() -> None:
    candidates = default_strategy_candidates((3, 5))
    first = benchmark_strategies(candidates, SERIES)
    second = benchmark_strategies(candidates, SERIES)
    assert [item.score for item in first] == [item.score for item in second]
    assert first[0].score >= first[1].score
    assert all(item.trades >= 0 for item in first)


def test_strategy_benchmark_requires_prices() -> None:
    with pytest.raises(ValueError):
        benchmark_strategies(default_strategy_candidates((3,)), [100.0])


def test_head_to_head_sums_to_evaluated_bars() -> None:
    first, second = default_subjects()[0], default_subjects()[1]
    result = head_to_head(first, second, SERIES, warmup=5)
    evaluated = len(SERIES) - 5 - 1
    assert result.wins + result.losses + result.ties == evaluated


def test_comparison_report_pairing() -> None:
    comparisons = build_comparison_report(list(default_subjects())[:2], [SERIES], warmup=5)
    assert len(comparisons) == 1
    pair = next(iter(comparisons.values()))
    assert pair.wins + pair.losses + pair.ties == len(SERIES) - 5 - 1


def test_build_default_report_shape() -> None:
    report = build_default_report(SERIES, lookbacks=(3, 5))
    assert isinstance(report, BenchmarkReport)
    payload = report.as_dict()
    assert payload["models"]
    assert payload["strategies"]
    assert "methodology" in payload


def test_default_report_as_dict_json_friendly() -> None:
    import json

    report = build_default_report([100.0, 101.0, 100.5, 102.0, 103.0, 104.0, 105.0, 99.0, 98.0, 101.0])
    json.dumps(report.as_dict())  # must not raise


def test_requires_subjects_or_series() -> None:
    with pytest.raises(ValueError):
        benchmark_models([], [SERIES])
    with pytest.raises(ValueError):
        benchmark_models([_FlatForecaster()], [])