"""Calibration, uncertainty, and statistical-signal utilities."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, pstdev
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """A single reliability bin for probabilistic forecasts."""

    predicted_confidence: float
    realized_accuracy: float
    count: int

    @property
    def gap(self) -> float:
        return self.predicted_confidence - self.realized_accuracy


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    bins: tuple[CalibrationBin, ...]
    expected_calibration_error: float
    brier_score: float
    log_loss: float
    sample_size: int

    def as_dict(self) -> dict[str, object]:
        return {
            "expected_calibration_error": self.expected_calibration_error,
            "brier_score": self.brier_score,
            "log_loss": self.log_loss,
            "sample_size": self.sample_size,
            "bins": [
                {
                    "predicted_confidence": b.predicted_confidence,
                    "realized_accuracy": b.realized_accuracy,
                    "count": b.count,
                    "gap": b.gap,
                }
                for b in self.bins
            ],
        }


def reliability_bins(
    predicted: Sequence[float],
    realized: Sequence[int],
    *,
    n_bins: int = 10,
) -> tuple[CalibrationBin, ...]:
    """Compute per-bin reliability statistics for binary outcomes."""
    if len(predicted) != len(realized):
        raise ValueError("predicted and realized must be the same length")
    if n_bins < 2:
        raise ValueError("n_bins must be at least 2")
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, r in zip(predicted, realized):
        if not 0 <= p <= 1:
            raise ValueError("predicted probabilities must be in [0, 1]")
        if r not in (0, 1):
            raise ValueError("realized outcomes must be 0 or 1")
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, r))
    out: list[CalibrationBin] = []
    for entries in bins:
        if not entries:
            continue
        out.append(
            CalibrationBin(
                predicted_confidence=mean(p for p, _ in entries),
                realized_accuracy=mean(r for _, r in entries),
                count=len(entries),
            )
        )
    return tuple(out)


def calibration_report(
    predicted: Sequence[float],
    realized: Sequence[int],
    *,
    n_bins: int = 10,
) -> CalibrationReport:
    """Compute ECE, Brier score, and log loss from binary-outcome predictions."""
    bins = reliability_bins(predicted, realized, n_bins=n_bins)
    total = sum(b.count for b in bins) or 1
    ece = sum(abs(b.gap) * b.count for b in bins) / total
    brier = sum((p - r) ** 2 for p, r in zip(predicted, realized)) / max(1, len(predicted))
    eps = 1e-9
    log_loss = -sum(
        r * (p if p > eps else eps) + (1 - r) * ((1 - p) if (1 - p) > eps else eps)
        for p, r in zip(predicted, realized)
    ) / max(1, len(predicted))
    return CalibrationReport(
        bins=bins,
        expected_calibration_error=ece,
        brier_score=brier,
        log_loss=log_loss,
        sample_size=len(predicted),
    )


def mean_absolute_error(predicted: Iterable[float], actual: Iterable[float]) -> float:
    p = list(predicted)
    a = list(actual)
    if not p or len(p) != len(a):
        raise ValueError("predicted and actual must be equal-length non-empty")
    return sum(abs(x - y) for x, y in zip(p, a)) / len(p)


def root_mean_squared_error(predicted: Iterable[float], actual: Iterable[float]) -> float:
    p = list(predicted)
    a = list(actual)
    if not p or len(p) != len(a):
        raise ValueError("predicted and actual must be equal-length non-empty")
    return sqrt(sum((x - y) ** 2 for x, y in zip(p, a)) / len(p))


def prediction_interval(returns: Sequence[float], *, coverage: float = 0.95) -> tuple[float, float]:
    """Empirical prediction interval for the next observation from a return series."""
    if not returns:
        raise ValueError("returns must be non-empty")
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between 0 and 1")
    sorted_returns = sorted(returns)
    lower_index = max(0, int(round((1 - coverage) / 2 * (len(sorted_returns) - 1))))
    upper_index = min(len(sorted_returns) - 1, int(round((1 + coverage) / 2 * (len(sorted_returns) - 1))))
    return sorted_returns[lower_index], sorted_returns[upper_index]


def summary_stats(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise ValueError("values must be non-empty")
    return {
        "mean": mean(values),
        "stdev": pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "n": float(len(values)),
    }


def decimal_to_float(values: Iterable[Decimal]) -> list[float]:
    return [float(v) for v in values]
