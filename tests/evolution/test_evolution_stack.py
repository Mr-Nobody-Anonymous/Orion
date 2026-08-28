"""Tests for the modular evolution stack: fitness, selection, operators."""

from __future__ import annotations

from random import Random

import pytest

from orion.evolution import (
    Fitness,
    FitnessWeights,
    StrategyCandidate,
    blend_crossover,
    clamp_parameters,
    mutate,
    population_diversity,
    ranked,
    roulette_select,
    tournament_select,
    uniform_crossover,
    weighted_score,
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


class TestFitnessWeights:
    def test_default_weights_reproduce_canonical_score(self) -> None:
        fitness = _fitness(5)
        assert weighted_score(fitness) == pytest.approx(fitness.score)

    def test_custom_weights_change_ranking(self) -> None:
        a = Fitness(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        b = Fitness(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        return_heavy = FitnessWeights(risk_adjusted_return=1.0, stability=0.0)
        stability_heavy = FitnessWeights(risk_adjusted_return=0.0, stability=1.0)
        assert weighted_score(a, return_heavy) > weighted_score(b, return_heavy)
        assert weighted_score(b, stability_heavy) > weighted_score(a, stability_heavy)

    def test_nonfinite_weights_rejected(self) -> None:
        with pytest.raises(ValueError):
            FitnessWeights(risk_adjusted_return=float("nan"))


class TestSelection:
    def test_ranked_sorts_best_first(self) -> None:
        population = (_candidate("weak", 1), _candidate("strong", 9), _candidate("mid", 5))
        scored = ranked(population, lambda c: _fitness(c.parameters["lookback"]))
        assert scored[0][0].identifier == "strong"
        assert scored[-1][0].identifier == "weak"

    def test_tournament_prefers_strong(self) -> None:
        rng = Random(7)
        scored = [(_candidate("weak", 1), 0.0), (_candidate("strong", 9), 10.0)]
        winners = {tournament_select(scored, rng=rng).identifier for _ in range(50)}
        assert winners == {"strong"}

    def test_roulette_always_returns_member(self) -> None:
        rng = Random(3)
        scored = [(_candidate("a", 1), 0.5), (_candidate("b", 2), 0.5)]
        assert roulette_select(scored, rng=rng).identifier in {"a", "b"}


class TestOperators:
    def test_mutate_changes_at_most_one_parameter(self) -> None:
        rng = Random(5)
        parent = _candidate("p", 4.0, 0.02)
        child = mutate(parent, rng=rng)
        changed = [name for name in parent.parameters if parent.parameters[name] != child.parameters[name]]
        assert len(changed) <= 1
        assert child.parents == ("p",)

    def test_mutate_lookback_stays_integer_like(self) -> None:
        rng = Random(1)
        parent = _candidate("p", 4.0)
        for _ in range(20):
            child = mutate(parent, rng=rng, strength=2.0)
            assert child.parameters["lookback"] == float(int(child.parameters["lookback"]))
            assert child.parameters["lookback"] >= 2

    def test_blend_crossover_interpolates(self) -> None:
        rng = Random(2)
        first = _candidate("a", 2.0, 0.01)
        second = _candidate("b", 8.0, 0.03)
        child = blend_crossover(first, second, rng=rng)
        for name in first.parameters:
            low = min(first.parameters[name], second.parameters[name])
            high = max(first.parameters[name], second.parameters[name])
            assert low - 1e-9 <= child.parameters[name] <= high + 1e-9

    def test_crossover_requires_matching_parameters(self) -> None:
        a = StrategyCandidate("a", {"lookback": 2.0})
        b = StrategyCandidate("b", {"threshold": 0.01})
        with pytest.raises(ValueError):
            blend_crossover(a, b, rng=Random(1))

    def test_uniform_crossover_picks_parents_values(self) -> None:
        first = _candidate("a", 2.0, 0.01)
        second = _candidate("b", 8.0, 0.03)
        child = uniform_crossover(first, second, rng=Random(4))
        assert child.parameters["lookback"] in {2.0, 8.0}

    def test_clamp_parameters(self) -> None:
        clamped = clamp_parameters({"lookback": 99.0, "threshold": 0.5}, {"lookback": (2.0, 30.0)})
        assert clamped["lookback"] == 30.0
        assert clamped["threshold"] == 0.5  # unbounded

    def test_diversity_basics(self) -> None:
        clones = tuple(_candidate(f"c{i}", 5.0) for i in range(4))
        assert population_diversity(clones) == 0.0
        varied = tuple(_candidate(f"v{i}", float(i + 1)) for i in range(4))
        assert population_diversity(varied) > 0.0
