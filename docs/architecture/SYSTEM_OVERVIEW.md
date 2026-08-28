# ORION System Overview

ORION is one system. Every capability shown below is wired through
`src/orion/orchestration/system.py::OrionSystem`, which composes the world
model, memory, forecaster, council, reasoner, risk engine, executive, learning,
evolution, research, simulator, governance, and provenance into a single
coordinated whole.

## The master loop

```
             ┌───────────────────────┐
             │   WORLD / DATA layer  │   data/ (contracts+validation)
             └───────────┬───────────┘
                         │ validate
                         ▼
             ┌───────────────────────┐
             │ SITUATIONAL AWARENESS │   world_model/ (WorldState/MarketState/...)
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │ MEMORY + WORLD MODEL  │   memory/ (7 layers), world_model/temporal
             └───────────┬───────────┘
                         ▼
            ┌────────────┴────────────┐
            ▼                         ▼
   ┌───────────────┐          ┌──────────────┤
   │   RESEARCH    │          │  PREDICTION   │   research/ + prediction/
   └───────┬───────┘          └───────┬───────┘
            └────────────┬────────────┘
                         ▼
             ┌───────────────────────┐
             │  GENERATIVE BRAIN     │   hypothesis/, strategies, council options
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │  EVOLUTION ENGINE     │   evolution/  (candidates only)
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │ SIMULATION / EXPERIMENTS │ simulation/ + backtesting/
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │       EVALUATION      │   learning/evaluation + backtesting/evaluation
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │   EXECUTIVE BRAIN     │   brain/ExecutiveOrchestrator (16-phase loop)
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │      RISK ENGINE      │   trading/risk (deterministic gate)
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │       EXECUTION       │   trading/execution SimulatedBroker
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │       OUTCOME         │
             └───────────┬───────────┘
                         ▼
             ┌───────────────────────┐
             │       LEARNING        │   learning/self_improvement, memory
             └───────────┬───────────┘
                         └──────────► back to WORLD MODEL
```

## Ownership in code

| Layer | Modules |
|---|---|
| World / data | `data/` (`Asset`, `MarketQuote`, `Prediction`, `DataQualityValidator`) |
| Situational awareness | `world_model/state.py` (`FinancialWorldModel`, 9 state objects, `KnowledgeStatus`) |
| Memory | `memory/` (`LayeredMemory`, `MemoryLayer`, `WorkingMemory`, `MemoryStore`) |
| Research | `research/` (`ResearchDiscovery`, `ResearchAgent`, `ExperimentPipeline`, `synthesize`) |
| Prediction | `prediction/` (`ModelCouncil`, forecasters, regime detector, uncertainty, calibration) |
| Generative brain | `brain/hypothesis.py`, `coding/generation.py` |
| Evolution | `evolution/` (`EvolutionEngine`, operators, selection, population) |
| Simulation / experiments | `simulation/market.py`, `backtesting/`, `research/experiments.py` |
| Evaluation | `learning/evaluation.py`, `backtesting/evaluation.py` |
| Benchmarking | `benchmarking/` (walk-forward model + strategy comparison) |
| Executive | `brain/orchestrator.py` (`ExecutiveOrchestrator`), `brain/executive.py` |
| Risk | `trading/risk.py` (`RiskEngine`) |
| Execution | `trading/execution.py` (`SimulatedBroker`) |

## Determinism and safety

- The executive loop (`run_cycle`) is deterministic given identical inputs, so
  every `LoopTrace` is reproducible.
- Content processes through the **risk gate before any fill**; risk is
  deterministic and independent of language models.
- Live execution and cloud inference are **BLOCKED** by construction
  (`LiveTradingDisabledError`, `CloudProviderUnavailable`).