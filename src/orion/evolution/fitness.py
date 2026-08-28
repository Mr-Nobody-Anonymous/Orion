"""Configurable multi-objective fitness scoring.

Raw return is never the fitness. The canonical weights penalize drawdown,
turnover, and reward stability, generalization, and calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .engine import Fitness


@dataclass(frozen=True, slots=True)
class FitnessWeights:
    """Weights for each fitness component; all must be finite."""

    risk_adjusted_return: float = 0.35
    stability: float = 0.20
    generalization: float = 0.20
    calibration: float = 0.15
    drawdown_penalty: float = 0.07
    turnover_penalty: float = 0.03

    def __post_init__(self) -> None:
        values = (self.risk_adjusted_return, self.stability, self.generalization,
                  self.calibration, self.drawdown_penalty, self.turnover_penalty)
        if any(value != value or value in (float("inf"), float("-inf")) for value in values):
            raise ValueError("weights must be finite")


def weighted_score(fitness: Fitness, weights: FitnessWeights | None = None) -> float:
    """Score a fitness with explicit weights (defaults mirror Fitness.score)."""
    weights = weights or FitnessWeights()
    return (
        fitness.risk_adjusted_return * weights.risk_adjusted_return
        + fitness.stability * weights.stability
        + fitness.generalization * weights.generalization
        + fitness.calibration * weights.calibration
        - abs(fitness.max_drawdown) * weights.drawdown_penalty
        - fitness.turnover * weights.turnover_penalty
    )


def fitness_as_dict(fitness: Fitness) -> dict[str, Any]:
    return {
        "risk_adjusted_return": fitness.risk_adjusted_return,
        "max_drawdown": fitness.max_drawdown,
        "turnover": fitness.turnover,
        "stability": fitness.stability,
        "generalization": fitness.generalization,
        "calibration": fitness.calibration,
        "score": fitness.score,
    }


__all__ = ["FitnessWeights", "fitness_as_dict", "weighted_score"]
