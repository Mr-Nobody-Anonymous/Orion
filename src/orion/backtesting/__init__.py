"""ORION-owned backtesting capabilities."""

from .engine import BacktestResult, vectorized_momentum_backtest
from .evaluation import PerformanceMetrics, WalkForwardResult, performance_metrics, walk_forward_momentum
from .monte_carlo import (
    MonteCarloReport,
    block_bootstrap_returns,
    geometric_brownian_motion,
    monte_carlo_backtest,
)
from .robustness import (
    RobustnessReport,
    detect_look_ahead_bias,
    detect_overfit,
    detect_survivorship_bias,
    evaluate_robustness,
    parameter_sensitivity,
)
from .stress_testing import (
    DEFAULT_SCENARIOS,
    StressResult,
    StressScenario,
    flash_crash,
    liquidity_gap,
    regime_break,
    run_stress_suite,
    volatility_spike,
)
from .walk_forward import (
    WalkForwardReport,
    WalkForwardWindow,
    purged_walk_forward,
    walk_forward,
)

__all__ = [
    "DEFAULT_SCENARIOS",
    "BacktestResult",
    "MonteCarloReport",
    "PerformanceMetrics",
    "RobustnessReport",
    "StressResult",
    "StressScenario",
    "WalkForwardReport",
    "WalkForwardResult",
    "WalkForwardWindow",
    "block_bootstrap_returns",
    "detect_look_ahead_bias",
    "detect_overfit",
    "detect_survivorship_bias",
    "evaluate_robustness",
    "flash_crash",
    "geometric_brownian_motion",
    "liquidity_gap",
    "monte_carlo_backtest",
    "parameter_sensitivity",
    "performance_metrics",
    "purged_walk_forward",
    "regime_break",
    "run_stress_suite",
    "vectorized_momentum_backtest",
    "volatility_spike",
    "walk_forward",
    "walk_forward_momentum",
]
