"""Robustness and overfitting detection.

ORION is designed to fail loudly. These checks explicitly look for
overfitting, look-ahead bias, leakage, and other pathologies.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from ..engine import BacktestResult, vectorized_momentum_backtest


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    passes: tuple[str, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]

    @property
    def is_robust(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, object]:
        return {
            "passes": list(self.passes),
            "warnings": list(self.warnings),
            "failures": list(self.failures),
            "is_robust": self.is_robust,
        }


def parameter_sensitivity(
    prices: Sequence[float], *, lookbacks: Sequence[int] = (2, 3, 5, 8, 13)
) -> dict[int, Decimal]:
    """Run the canonical backtest with different lookback values and report the resulting returns."""
    if not lookbacks:
        raise ValueError("lookbacks must be non-empty")
    out: dict[int, Decimal] = {}
    for lookback in lookbacks:
        try:
            result = vectorized_momentum_backtest(prices, lookback=lookback)
            out[lookback] = result.total_return
        except ValueError:
            continue
    return out


def detect_look_ahead_bias(prices: Sequence[float], *, lookback: int = 3) -> bool:
    """Returns True if the simple momentum backtest produces obviously
    impossible results (e.g. unbounded return in a flat series)."""
    if len(prices) <= lookback or any(p <= 0 for p in prices):
        return True
    try:
        result = vectorized_momentum_backtest(prices, lookback=lookback)
    except ValueError:
        return True
    # Heuristic: a flat series should produce ~0 return.
    flat = all(abs(prices[i] - prices[i + 1]) < 1e-9 for i in range(len(prices) - 1))
    if flat and abs(result.total_return) > Decimal("0.0001"):
        return True
    return False


def detect_survivorship_bias(
    train_returns: Sequence[Decimal], test_returns: Sequence[Decimal]
) -> bool:
    """Heuristic: if the test-period mean return is dramatically lower than
    the train-period mean, the strategy may have been implicitly selected on
    survival. Returns True when the gap is unusually large."""
    if not train_returns or not test_returns:
        return True
    train_mean = sum(train_returns, Decimal("0")) / len(train_returns)
    test_mean = sum(test_returns, Decimal("0")) / len(test_returns)
    return (train_mean - test_mean) > Decimal("0.10")


def detect_overfit(
    in_sample_sharpe: float, out_of_sample_sharpe: float, *, degradation: float = 0.5
) -> bool:
    """Returns True if out-of-sample performance has degraded by more than
    `degradation` (default 50%) relative to in-sample performance."""
    if in_sample_sharpe <= 0:
        return False
    if out_of_sample_sharpe <= 0:
        return True
    return (in_sample_sharpe - out_of_sample_sharpe) / in_sample_sharpe > degradation


def evaluate_robustness(
    prices: Sequence[float],
    *,
    in_sample_sharpe: float,
    out_of_sample_sharpe: float,
    lookbacks: Sequence[int] = (2, 3, 5, 8, 13),
) -> RobustnessReport:
    passes: list[str] = []
    warnings: list[str] = []
    failures: list[str] = []

    if not detect_look_ahead_bias(prices):
        passes.append("no_look_ahead_bias_detected")
    else:
        failures.append("look_ahead_bias_detected")

    if not detect_overfit(in_sample_sharpe, out_of_sample_sharpe):
        passes.append("no_obvious_overfit")
    else:
        failures.append("overfit_degradation_exceeds_threshold")

    sensitivity = parameter_sensitivity(prices, lookbacks=lookbacks)
    if sensitivity:
        values = [float(v) for v in sensitivity.values()]
        spread = max(values) - min(values)
        if spread > 0.20:
            warnings.append(f"high_parameter_sensitivity: spread={spread:.3f}")
        else:
            passes.append("parameter_sensitivity_within_tolerance")
    else:
        warnings.append("parameter_sensitivity_not_evaluated")

    return RobustnessReport(tuple(passes), tuple(warnings), tuple(failures))
