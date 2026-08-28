from orion.evolution import EvolutionEngine, Fitness


def test_evolution_is_seeded_and_retains_population_size() -> None:
    engine = EvolutionEngine(seed=4)
    population = engine.seed_population(4)
    result = engine.evolve(population, lambda candidate: Fitness(
        risk_adjusted_return=candidate.parameters["lookback"] / 10,
        max_drawdown=-0.1,
        turnover=0.2,
        stability=0.4,
        generalization=0.3,
        calibration=0.5,
    ))
    assert result.generation == 1
    assert len(result.next_population) == 4
    assert result.ranked[0][1].score >= result.ranked[-1][1].score
