"""Contamination-safe benchmarking suite.

PRINCIPLE
    A benchmark must never reward a model for seeing the future. Every
    forecasting score below is produced by a strict walk-forward protocol:

        for each t in [warmup, n-2]:
            prediction_t = model.predict(prices[:t+1])   # no bars after t
            actual_t     = prices[t+1] / prices[t] - 1

    The window passed to a model *ends at t*, so look-ahead contamination is
    structurally impossible regardless of model internals.

    Strategy comparisons run every candidate on the same prices with the same
    performance metrics and are ranked deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from math import sqrt
from statistics import mean
from typing import Sequence

from ..data.contracts import Asset, AssetClass
from ..evolution import StrategyCandidate

#: The fixed instrument used for all benchmark predictions.
BEHAVIORAL_ASSET = Asset(symbol="BENCH", asset_class=AssetClass.EQUITY)


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """Aggregated forecast scoring for one subject over one or more series."""

    subject: str
    count: int
    mae: float
    rmse: float
    directional_accuracy: float
    bias: float
    score: float
    failures: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "count": self.count,
            "mae": round(self.mae, 6),
            "rmse": round(self.rmse, 6),
            "directional_accuracy": round(self.directional_accuracy, 6),
            "bias": round(self.bias, 6),
            "score": round(self.score, 6),
            "failures": self.failures,
        }


@dataclass(frozen=True, slots=True)
class ModelBenchmark:
    """One benchmarked forecast model."""

    metrics: BenchmarkMetrics
    protocol: str = "walk-forward"

    def as_dict(self) -> dict[str, object]:
        return {"protocol": self.protocol, "metrics": self.metrics.as_dict()}


@dataclass(frozen=True, slots=True)
class StrategyBenchmark:
    """One benchmarked strategy candidate on a shared price series."""

    name: str
    parameters: dict[str, float]
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    trades: int
    score: float

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "parameters": self.parameters,
            "total_return": round(self.total_return, 6),
            "sharpe": round(self.sharpe, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "win_rate": round(self.win_rate, 6),
            "trades": self.trades,
            "score": round(self.score, 6),
        }


@dataclass(frozen=True, slots=True)
class HeadToHead:
    """Directional-accuracy wins/losses/ties between two subjects."""

    wins: int
    losses: int
    ties: int

    def as_dict(self) -> dict[str, object]:
        return {"wins": self.wins, "losses": self.losses, "ties": self.ties}


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Complete, auditable benchmark output."""

    models: tuple[ModelBenchmark, ...] = ()
    strategies: tuple[StrategyBenchmark, ...] = ()
    comparisons: dict[str, HeadToHead] = field(default_factory=dict)
    methodology: str = (
        "forecasting: strict walk-forward (prediction t uses only bars up to t); "
        "strategies: identical price series, identical metrics; no tuning on the "
        "evaluated window."
    )

    def as_dict(self) -> dict[str, object]:
        return {
            "methodology": self.methodology,
            "models": [model.as_dict() for model in self.models],
            "strategies": [strategy.as_dict() for strategy in self.strategies],
            "comparisons": {pair: report.as_dict() for pair, report in self.comparisons.items()},
        }


# --------------------------------------------------------------------------- forecast


def _expected_return(result: object) -> Decimal:
    """Normalise ModelCouncil, PredictionEnsemble and raw Prediction outputs."""
    prediction = result.prediction if hasattr(result, "prediction") else result
    return Decimal(getattr(prediction, "expected_return"))


def benchmark_forecaster(
    model: object,
    prices: Sequence[float],
    *,
    warmup: int = 20,
    horizon: str = "5d",
) -> tuple[tuple[float, ...], tuple[float, ...], int]:
    """Walk-forward predicted/actual return pairs.

    Each prediction at step ``t`` sees only ``prices[:t+1]``. The actual is the
    next observed return. Returns (predicted, actual, failures) where failures
    counts bars the model could not score (e.g. insufficient lookback).
    """
    if warmup < 2:
        raise ValueError("warmup must be at least two")
    if len(prices) < warmup + 2:
        raise ValueError(
            f"price series too short for warmup={warmup} (need at least {warmup + 2} bars)"
        )
    predicted: list[float] = []
    actual: list[float] = []
    failures = 0
    for index in range(warmup - 1, len(prices) - 1):
        window = list(prices[: index + 1])
        try:
            generated = _expected_return(model.predict(BEHAVIORAL_ASSET, window, horizon=horizon))
        except ValueError:
            failures += 1
            continue
        predicted.append(float(generated))
        actual.append(float(prices[index + 1] / prices[index] - 1))
    return tuple(predicted), tuple(actual), failures


def compute_metrics(
    subject: str,
    predicted: Sequence[float],
    actual: Sequence[float],
    *,
    failures: int = 0,
) -> BenchmarkMetrics:
    """Deterministic forecasting metrics (MAE, RMSE, directional accuracy, bias)."""
    if not predicted:
        return BenchmarkMetrics(subject, 0, 0.0, 0.0, 0.0, 0.0, 0.0, failures)
    mae = mean(abs(p - a) for p, a in zip(predicted, actual))
    rmse = sqrt(sum((p - a) ** 2 for p, a in zip(predicted, actual)) / len(predicted))
    directional = mean(1 if (p >= 0) == (a >= 0) else 0 for p, a in zip(predicted, actual))
    bias = mean(p - a for p, a in zip(predicted, actual))
    score = 0.5 * directional - 0.25 * mae - 0.25 * rmse - 0.25 * abs(bias)
    return BenchmarkMetrics(subject, len(predicted), mae, rmse, directional, bias, score, failures)


def _subject_name(model: object) -> str:
    return str(getattr(model, "name", type(model).__name__))


def benchmark_models(
    models: Sequence[object],
    series: Sequence[Sequence[float]],
    *,
    warmup: int = 20,
    horizon: str = "5d",
) -> tuple[ModelBenchmark, ...]:
    """Score every model over every series with the walk-forward protocol."""
    if not models:
        raise ValueError("at least one model is required")
    if not series:
        raise ValueError("at least one price series is required")
    results: list[ModelBenchmark] = []
    for model in models:
        predicted: list[float] = []
        actual: list[float] = []
        failures = 0
        for prices in series:
            predicted_step, actual_step, failed = benchmark_forecaster(
                model, prices, warmup=warmup, horizon=horizon
            )
            predicted.extend(predicted_step)
            actual.extend(actual_step)
            failures += failed
        results.append(
            ModelBenchmark(
                compute_metrics(_subject_name(model), predicted, actual, failures=failures)
            )
        )
    return tuple(sorted(results, key=lambda item: item.metrics.score, reverse=True))


# --------------------------------------------------------------------------- strategies


def default_subjects() -> tuple[object, ...]:
    """Default forecast benchmark subjects, sized for modest price histories."""
    from ..prediction import LinearTrendForecaster
    from ..prediction.time_series import (
        ExponentiallyWeightedForecaster,
        MeanReversionForecaster,
        MomentumForecaster,
    )

    return (
        LinearTrendForecaster(),
        MomentumForecaster(lookback=5),
        MeanReversionForecaster(window=5),
        ExponentiallyWeightedForecaster(alpha=0.3),
    )


def default_strategy_candidates(lookbacks: Sequence[int] = (3, 5, 8)) -> tuple[StrategyCandidate, ...]:
    """Strategy candidates whose ``lookback`` parameter is benchmarked."""
    if not lookbacks:
        raise ValueError("at least one lookback is required")
    return tuple(
        StrategyCandidate(
            identifier=f"strategy-bench-{lookback}",
            parameters={"lookback": float(lookback), "threshold": 0.0},
        )
        for lookback in lookbacks
    )


def benchmark_strategies(
    candidates: Sequence[StrategyCandidate],
    prices: Sequence[float],
) -> tuple[StrategyBenchmark, ...]:
    """Run every candidate on the *same* price series with the same metrics."""
    from ..backtesting.engine import vectorized_momentum_backtest
    from ..backtesting.evaluation import performance_metrics

    if not candidates:
        raise ValueError("at least one strategy candidate is required")
    if len(prices) < 4:
        raise ValueError("at least four prices are required for strategy benchmarking")
    results: list[StrategyBenchmark] = []
    for candidate in candidates:
        lookback = max(2, min(len(prices) - 1, int(candidate.parameters.get("lookback", 5))))
        backtest = vectorized_momentum_backtest(list(prices), lookback=lookback)
        metrics = performance_metrics(prices, backtest)
        score = float(metrics.sharpe) - 0.1 * float(metrics.max_drawdown)
        results.append(
            StrategyBenchmark(
                name=candidate.identifier,
                parameters=candidate.parameters,
                total_return=float(metrics.total_return),
                sharpe=float(metrics.sharpe),
                max_drawdown=float(metrics.max_drawdown),
                win_rate=float(metrics.win_rate),
                trades=backtest.trades,
                score=score,
            )
        )
    return tuple(sorted(results, key=lambda item: item.score, reverse=True))


# --------------------------------------------------------------------------- comparison


def _directions(predicted: Sequence[float]) -> tuple[int, ...]:
    return tuple(1 if value >= 0 else -1 for value in predicted)


def head_to_head(first: object, second: object, prices: Sequence[float], *, warmup: int = 5) -> HeadToHead:
    """Count directional forecasts where ``first`` beats ``second`` and vice versa."""
    predicted_first, actual, _ = benchmark_forecaster(first, prices, warmup=warmup)
    predicted_second, _, _ = benchmark_forecaster(second, prices, warmup=warmup)
    paired = list(
        zip(
            _directions(predicted_first),
            _directions(predicted_second),
            _directions(actual),
        )
    )
    wins = sum(1 for f, s, a in paired if f == a and s != a)
    losses = sum(1 for f, s, a in paired if f != a and s == a)
    return HeadToHead(wins, losses, len(paired) - wins - losses)


def build_comparison_report(
    subjects: Sequence[object],
    series: Sequence[Sequence[float]],
    *,
    warmup: int = 5,
) -> dict[str, HeadToHead]:
    """Pairwise directional head-to-heads for the given subjects."""
    names = [_subject_name(subject) for subject in subjects]
    comparisons: dict[str, HeadToHead] = {}
    for left in range(len(subjects)):
        for right in range(left + 1, len(subjects)):
            compare = HeadToHead(0, 0, 0)
            for prices in series:
                result = head_to_head(subjects[left], subjects[right], prices, warmup=warmup)
                compare = HeadToHead(
                    compare.wins + result.wins,
                    compare.losses + result.losses,
                    compare.ties + result.ties,
                )
            comparisons[f"{names[left]} vs {names[right]}"] = compare
    return comparisons


def build_default_report(prices: Sequence[float], *, lookbacks: Sequence[int] = (3, 5, 8)) -> BenchmarkReport:
    """One-call benchmark over forecast models and strategies on a price series.

    The warmup is derived from the series length so short series (e.g. CLI
    ``--prices`` inputs) are benchmarked without artificial lookbacks.
    """
    warmup = min(20, max(3, len(prices) // 3))
    models = benchmark_models(default_subjects(), [list(prices)], warmup=warmup)
    strategies = benchmark_strategies(default_strategy_candidates(lookbacks), list(prices))
    return BenchmarkReport(models=models, strategies=strategies)