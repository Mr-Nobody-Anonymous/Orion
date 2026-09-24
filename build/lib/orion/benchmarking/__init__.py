"""Benchmarking: standardized, contamination-safe model and strategy comparison.

Benchmarks never tune on the evaluated window. Forecasting is scored with a
strict walk-forward protocol (each prediction uses only bars strictly before the
target) so look-ahead contamination is structurally impossible. Strategies are
compared on a shared price series with standard performance metrics.
"""

from .suite import (
    BEHAVIORAL_ASSET,
    BenchmarkMetrics,
    BenchmarkReport,
    ModelBenchmark,
    StrategyBenchmark,
    benchmark_forecaster,
    benchmark_models,
    benchmark_strategies,
    build_comparison_report,
    build_default_report,
    compute_metrics,
    default_strategy_candidates,
    default_subjects,
    head_to_head,
)

__all__ = [
    "BEHAVIORAL_ASSET",
    "BenchmarkMetrics",
    "BenchmarkReport",
    "ModelBenchmark",
    "StrategyBenchmark",
    "benchmark_forecaster",
    "benchmark_models",
    "benchmark_strategies",
    "build_comparison_report",
    "build_default_report",
    "compute_metrics",
    "default_strategy_candidates",
    "default_subjects",
    "head_to_head",
]