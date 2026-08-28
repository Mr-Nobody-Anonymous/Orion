"""Deterministic multi-objective candidate evolution.

Composes the modular operators in this package (selection, mutation,
crossover, diversity) into one engine. Fitness is deliberately
multi-objective: raw return alone never wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Callable


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    identifier: str
    parameters: dict[str, float]
    generation: int = 0
    parents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Fitness:
    risk_adjusted_return: float
    max_drawdown: float
    turnover: float
    stability: float
    generalization: float
    calibration: float

    @property
    def score(self) -> float:
        return (
            self.risk_adjusted_return * 0.35 + self.stability * 0.2 + self.generalization * 0.2
            + self.calibration * 0.15 - abs(self.max_drawdown) * 0.07 - self.turnover * 0.03
        )


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    generation: int
    ranked: tuple[tuple[StrategyCandidate, Fitness], ...]
    next_population: tuple[StrategyCandidate, ...]


class EvolutionEngine:
    """Deterministic candidate evolution over the canonical parameter space."""

    def __init__(self, seed: int = 7, elite_fraction: float = 0.25) -> None:
        self._random = Random(seed)
        self.elite_fraction = elite_fraction

    def seed_population(self, size: int = 8, *, max_lookback: int = 30) -> tuple[StrategyCandidate, ...]:
        if size < 2:
            raise ValueError("population size must be at least two")
        if max_lookback < 2:
            raise ValueError("max_lookback must be at least two")
        return tuple(StrategyCandidate(f"strategy-{index:03d}", {
            "lookback": float(self._random.randint(2, max_lookback)),
            "threshold": round(self._random.uniform(0.001, 0.05), 4),
        }) for index in range(size))

    def evolve(self, population: tuple[StrategyCandidate, ...], evaluator: Callable[[StrategyCandidate], Fitness]) -> EvolutionResult:
        if len(population) < 2:
            raise ValueError("population size must be at least two")

        # Deferred imports keep the dataclasses here authoritative and avoid
        # circular imports at module load time.
        from .operators import blend_crossover, mutate
        from .population import enforce_diversity, population_diversity
        from .selection import elitism, ranked, tournament_select

        scored = ranked(population, evaluator)
        generation = max(candidate.generation for candidate in population) + 1
        elite_count = max(1, round(len(population) * self.elite_fraction))
        elites = elitism(scored, count=elite_count)

        offspring: list[StrategyCandidate] = []
        scored_pairs = [(candidate, score) for candidate, _, score in scored]
        while len(elites) + len(offspring) < len(population):
            first = tournament_select(scored_pairs, rng=self._random)
            second = tournament_select(scored_pairs, rng=self._random)
            child = blend_crossover(first, second, rng=self._random,
                                    next_identifier=f"strategy-g{generation}-{len(elites) + len(offspring):03d}",
                                    generation=generation)
            child = mutate(child, rng=self._random,
                           next_identifier=f"strategy-g{generation}-{len(elites) + len(offspring):03d}",
                           generation=generation)
            offspring.append(child)

        # Elites survive, but they advance to the new generation so lineage
        # tracking stays meaningful (they are carried into gen N, not stuck in N-1).
        advanced_elites = tuple(
            StrategyCandidate(
                candidate.identifier,
                dict(candidate.parameters),
                generation=generation,
                parents=candidate.parents,
            )
            for candidate in elites
        )
        next_population = enforce_diversity(
            advanced_elites + tuple(offspring),
            min_distance=0.01,
            target_size=len(population),
        )
        while len(next_population) < len(population):
            # Diversity culling was too aggressive: regenerate via mutation of the best.
            best = elites[0]
            extra = mutate(best, rng=self._random,
                           next_identifier=f"strategy-g{generation}-x{len(next_population):03d}",
                           generation=generation)
            next_population = next_population + (extra,)
        result = EvolutionResult(
            generation=generation,
            ranked=tuple((candidate, fitness) for candidate, fitness, _ in scored),
            next_population=next_population[:len(population)],
        )
        self._last_diversity = population_diversity(result.next_population)
        return result

    @property
    def last_diversity(self) -> float:
        """Diversity of the most recent next_population (0.0 before any evolve)."""
        return getattr(self, "_last_diversity", 0.0)

