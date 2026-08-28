"""Tests for the composed evolution engine and diversity management."""

from __future__ import annotations

import pytest

from orion.evolution import (
    EvolutionEngine,
    Fitness,
    StrategyCandidate,
    enforce_diversity,
)


def _fitness(lookback: float) -> Fitness:
    return Fitness(
        risk_adjusted_return=lookback / 10,
        max_drawdown=-0.1,
        turnover=0.2,
        stability=0.4,
        generalization=0.3,
        calibration=0.5,
    )


def _candidate(name: str, lookback: float, threshold: float = 0.02) -> StrategyCandidate:
    return StrategyCandidate(name, {"lookback": lookback, "threshold": threshold})


class TestDiversityManagement:
    def test_enforce_diversity_keeps_distinct_members(self) -> None:
        clones = tuple(_candidate(f"clone{i}", 5.0) for i in range(5))
        distinct = _candidate("distinct", 20.0)
        kept = enforce_diversity(clones + (distinct,), min_distance=0.05, target_size=5)
        assert any(candidate.identifier == "distinct" for candidate in kept)
        assert len(kept) <= 5

    def test_target_size_respected(self) -> None:
        population = tuple(_candidate(f"c{i}", float(i)) for i in range(8))
        assert len(enforce_diversity(population, min_distance=0.0, target_size=3)) == 3

    def test_empty_population_allowed(self) -> None:
        assert enforce_diversity((), target_size=3) == ()

    def test_target_size_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            enforce_diversity((_candidate("a", 1),), target_size=0)


class TestEngineComposition:
    def test_engine_still_seeded_and_deterministic(self) -> None:
        first = EvolutionEngine(seed=4)
        second = EvolutionEngine(seed=4)
        assert first.seed_population(4) == second.seed_population(4)

    def test_engine_retains_size_and_generations(self) -> None:
        engine = EvolutionEngine(seed=4)
        population = engine.seed_population(4)
        result = engine.evolve(population, lambda candidate: _fitness(candidate.parameters["lookback"]))
        assert result.generation == 1
        assert len(result.next_population) == 4
        assert result.ranked[0][1].score >= result.ranked[-1][1].score
        assert all(candidate.generation == 1 for candidate in result.next_population)

    def test_engine_tracks_diversity(self) -> None:
        engine = EvolutionEngine(seed=11)
        population = engine.seed_population(6)
        engine.evolve(population, lambda candidate: _fitness(candidate.parameters["lookback"]))
        assert engine.last_diversity >= 0.0

    def test_multi_generation_evolution_runs(self) -> None:
        engine = EvolutionEngine(seed=9)
        population = engine.seed_population(6)
        for _ in range(3):
            result = engine.evolve(population, lambda candidate: _fitness(candidate.parameters["lookback"]))
            population = result.next_population
        assert population[0].generation == 3

    def test_elite_survives(self) -> None:
        engine = EvolutionEngine(seed=2)
        population = engine.seed_population(5)
        result = engine.evolve(population, lambda candidate: _fitness(candidate.parameters["lookback"]))
        best_identifier = result.ranked[0][0].identifier
        assert any(candidate.identifier == best_identifier for candidate in result.next_population)

    def test_tiny_population_rejected(self) -> None:
        engine = EvolutionEngine()
        with pytest.raises(ValueError):
            engine.evolve((_candidate("solo", 3.0),), lambda c: _fitness(3))
