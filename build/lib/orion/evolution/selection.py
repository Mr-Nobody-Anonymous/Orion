"""Selection operators: tournament and roulette wheel.

Selection is pressure, not destiny: elitism preserves the best, tournaments
propagate strength, and the weakest always have a residual path via mutation.
"""

from __future__ import annotations

from random import Random
from typing import Sequence

from .engine import Fitness, StrategyCandidate


def ranked(population: Sequence[StrategyCandidate], evaluator) -> list[tuple[StrategyCandidate, Fitness, float]]:
    """Return (candidate, fitness, score) sorted best-first."""
    scored = [(candidate, fitness := evaluator(candidate), fitness.score) for candidate in population]
    return sorted(scored, key=lambda item: item[2], reverse=True)


def tournament_select(
    scored: Sequence[tuple[StrategyCandidate, float]],
    *,
    rng: Random,
    tournament_size: int = 3,
) -> StrategyCandidate:
    """Pick the best of `tournament_size` random contestants."""
    if not scored:
        raise ValueError("scored population must be non-empty")
    if tournament_size < 2:
        raise ValueError("tournament_size must be at least two")
    contestants = rng.sample(list(scored), min(tournament_size, len(scored)))
    return max(contestants, key=lambda item: item[1])[0]


def roulette_select(
    scored: Sequence[tuple[StrategyCandidate, float]],
    *,
    rng: Random,
) -> StrategyCandidate:
    """Fitness-proportionate selection; negative scores are floored at 0."""
    if not scored:
        raise ValueError("scored population must be non-empty")
    floor = min(0.0, min(score for _, score in scored))
    weights = [score - floor + 1e-9 for _, score in scored]
    total = sum(weights)
    threshold = rng.random() * total
    cumulative = 0.0
    for (candidate, _), weight in zip(scored, weights):
        cumulative += weight
        if cumulative >= threshold:
            return candidate
    return scored[-1][0]


def elitism(ranked_population: Sequence[tuple[StrategyCandidate, Fitness, float]], *,
            count: int) -> list[StrategyCandidate]:
    if count < 1:
        raise ValueError("elite count must be at least one")
    return [candidate for candidate, _, _ in ranked_population[:count]]


__all__ = ["elitism", "ranked", "roulette_select", "tournament_select"]
