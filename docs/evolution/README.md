# Evolution

Evolutionary candidate generation with deterministic, multi-objective fitness.
Evolved artifacts are candidates that must pass evaluation and the promotion
gate before any integration — they are never written into production.

Modules: `evolution/` — `engine.py`, `fitness.py`, `operators.py`,
`population.py`, `selection.py`.

## Capabilities

| Capability | Status | Entry points |
|---|---|---|
| Population seeding | IMPLEMENTED | `EvolutionEngine.seed_population` |
| Selection (tournament/roulette) | IMPLEMENTED | `tournament_select`, `roulette_select`, `elitism` |
| Crossover | IMPLEMENTED | `uniform_crossover`, `blend_crossover` |
| Mutation | IMPLEMENTED | `mutate`, `clamp_parameters` |
| Diversity preservation | IMPLEMENTED | `enforce_diversity`, `population_diversity` |
| Multi-objective fitness | IMPLEMENTED | `Fitness.score` (risk-adj, stability, generalization, calibration, −drawdown, −turnover) |
| Governed deployment | IMPLEMENTED | candidates → backtest → promotion gate |

## Governance

Fitness is explicitly **not raw return**. Candidates from evolution are ranked,
but only the promotion gate may decide deployment (`infrastructure/governance.py`).

See also: [evolution loop](../architecture/EVOLUTION_LOOP.md).