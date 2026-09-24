"""Population management: size, diversity, and culling.

Diversity preservation prevents the population from collapsing into clones
of a single lucky ancestor — the evolutionary analogue of overfitting.
"""

from __future__ import annotations

from typing import Sequence

from .engine import StrategyCandidate


def normalized_distance(first: StrategyCandidate, second: StrategyCandidate) -> float:
    """Mean absolute parameter difference normalized by magnitude."""
    names = set(first.parameters) | set(second.parameters)
    if not names:
        return 0.0
    total = 0.0
    for name in names:
        a = first.parameters.get(name, 0.0)
        b = second.parameters.get(name, 0.0)
        scale = max(abs(a), abs(b), 1e-9)
        total += abs(a - b) / scale
    return total / len(names)


def population_diversity(population: Sequence[StrategyCandidate]) -> float:
    """Mean pairwise distance; 0 means every candidate is identical."""
    if len(population) < 2:
        return 0.0
    distances = [
        normalized_distance(population[i], population[j])
        for i in range(len(population))
        for j in range(i + 1, len(population))
    ]
    return sum(distances) / len(distances)


def enforce_diversity(
    population: Sequence[StrategyCandidate],
    *,
    min_distance: float = 0.05,
    target_size: int,
) -> tuple[StrategyCandidate, ...]:
    """Greedy diversity filter: keep the first occurrence, drop near-clones.

    The result never exceeds `target_size` and never drops below one member.
    """
    if target_size < 1:
        raise ValueError("target_size must be at least one")
    if not population:
        return ()
    kept: list[StrategyCandidate] = [population[0]]
    for candidate in population[1:]:
        if len(kept) >= target_size:
            break
        if all(normalized_distance(candidate, existing) >= min_distance for existing in kept):
            kept.append(candidate)
    return tuple(kept)


__all__ = [
    "enforce_diversity",
    "normalized_distance",
    "population_diversity",
]
