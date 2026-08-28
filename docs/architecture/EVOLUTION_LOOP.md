# Evolution Loop

Evolution produces candidate strategies/parameters. Nothing evolved enters
production directly: candidates flow through evaluation and the promotion gate.

Modules: `evolution/` — `engine.py`, `fitness.py`, `operators.py`,
`population.py`, `selection.py`.

## Loop

```
                  ┌───────────────────────┐
                  │ POPULATION (candidates)│  StrategyCandidate{lookback, threshold}
                  └───────────┬───────────┘
                              │  ranked(...) + evaluate fitness
                              ▼
                  ┌───────────────────────┐
                  │  SELECTION            │  tournament_select, roulette_select,
                  │  (tournament/roulette)│  elitism
                  └───────────┬───────────┘
                              │ blend_crossover(first, second)
                              ▼
                  ┌───────────────────────┐
                  │  CROSSOVER            │  uniform_crossover / blend_crossover
                  └───────────┬───────────┘
                              │ mutate(child)
                              ▼
                  ┌───────────────────────┐
                  │  MUTATION             │  mutate, clamp_parameters
                  └───────────┬───────────┘
                              │ enforce_diversity(...)
                              ▼
                  ┌───────────────────────┐
                  │  NEXT POPULATION      │  elites + offspring, min-distance culling
                  └───────────┬───────────┘
                              │  → next generation (repeat)
                              ▼
                  ┌───────────────────────┐
                  │  EVALUATION + GATE    │  backtesting → promotion gate
                  └───────────────────────┘
```

## Fitness is multi-objective (`evolution/fitness.py`, `engine.py`)

`Fitness` is **not raw return**. The composite score weights:

- risk-adjusted return (35%)
- stability (20%)
- generalization (20%)
- calibration (15%)
- drawdown penalty (−7%)
- turnover penalty (−3%)

This directly encodes `Fitness.score` in `evolution/engine.py`.

## Lineage and determinism

- `EvolutionEngine(seed=7, elite_fraction=0.25)` is deterministic; each
  `StrategyCandidate` records `generation` and `parents`.
- Elites advance into the new generation so lineage remains meaningful,
  `population_diversity` and `enforce_diversity` preserve spread, and a
  diversity-culling underfill is regenerated from the best elite.

## Relationship to generative intelligence

- The **generative brain** (`coding/generation.py`, `brain/hypothesis.py`)
  proposes candidates.
- The **evolution engine** selects and improves populations of candidates.
- **Simulation/backtesting** tests them; the **executive** decides resource
  allocation; the **promotion gate** decides deployment.

Nothing evolved is directly written into production.