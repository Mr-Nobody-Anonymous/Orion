"""Variation operators: mutation and crossover.

Operators are parameter-agnostic: `lookback` is rounded to integers, every
other parameter is treated as a continuous value with a floor, matching the
canonical ORION parameter space.
"""

from __future__ import annotations

from random import Random
from typing import Mapping, Sequence

from .engine import StrategyCandidate


def mutate(
    candidate: StrategyCandidate,
    *,
    rng: Random,
    strength: float = 0.2,
    next_identifier: str = "child",
    generation: int = 0,
) -> StrategyCandidate:
    """Perturb one randomly chosen parameter by up to ±strength (relative)."""
    if not candidate.parameters:
        raise ValueError("candidate has no parameters to mutate")
    if not 0 < strength <= 2:
        raise ValueError("strength must be within (0, 2]")
    parameters = dict(candidate.parameters)
    name = rng.choice(tuple(parameters))
    value = parameters[name]
    perturbed = value * (1 + rng.uniform(-strength, strength))
    if name == "lookback":
        parameters[name] = float(max(2, round(perturbed)))
    else:
        parameters[name] = round(max(0.0001, perturbed), 4)
    return StrategyCandidate(next_identifier, parameters, generation, (candidate.identifier,))


def blend_crossover(
    first: StrategyCandidate,
    second: StrategyCandidate,
    *,
    rng: Random,
    next_identifier: str = "child",
    generation: int = 0,
) -> StrategyCandidate:
    """Whole-arithmetic blend: child = alpha*first + (1-alpha)*second."""
    missing = set(first.parameters) ^ set(second.parameters)
    if missing:
        raise ValueError(f"parents must share parameter names; differing: {sorted(missing)}")
    alpha = rng.random()
    parameters = {
        name: alpha * first.parameters[name] + (1 - alpha) * second.parameters[name]
        for name in first.parameters
    }
    return StrategyCandidate(next_identifier, parameters, generation, (first.identifier, second.identifier))


def uniform_crossover(
    first: StrategyCandidate,
    second: StrategyCandidate,
    *,
    rng: Random,
    next_identifier: str = "child",
    generation: int = 0,
) -> StrategyCandidate:
    """Each parameter is taken from either parent with probability 0.5."""
    if set(first.parameters) != set(second.parameters):
        raise ValueError("parents must share parameter names")
    parameters = {
        name: (first.parameters[name] if rng.random() < 0.5 else second.parameters[name])
        for name in first.parameters
    }
    return StrategyCandidate(next_identifier, parameters, generation, (first.identifier, second.identifier))


def clamp_parameters(parameters: Mapping[str, float], bounds: Mapping[str, Sequence[float]]) -> dict[str, float]:
    """Clamp parameters into optional (low, high) bounds."""
    clamped: dict[str, float] = {}
    for name, value in parameters.items():
        if name in bounds:
            low, high = bounds[name][0], bounds[name][1]
            clamped[name] = min(high, max(low, value))
        else:
            clamped[name] = value
    return clamped


__all__ = [
    "blend_crossover",
    "clamp_parameters",
    "mutate",
    "uniform_crossover",
]
