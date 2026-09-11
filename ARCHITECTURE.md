# Orion Architecture

## 1. Purpose

Orion is an autonomous trading and research system: a runtime agent that pursues missions through planning, reasoning, prediction, and tool use; executes trades through broker integrations under risk and compliance controls; and continuously learns from evaluation, backtesting, and experience. It spans the full loop from goal formation to execution to feedback-driven self-improvement.

## 2. Architectural Layers

### Control Plane
`agent/`, `agents/`, `brain/`, `orchestration/`, `mission/`
Runtime kernel, agent lifecycle, planning/reasoning/decisions, scheduler/supervisor wiring, and the mission/objective layer. This plane decides *what happens*; it does not implement domain math or brokers.

### Intelligence Plane
`intelligence/`, `models/`, `prediction/`, `research/`, `learning/`, `evolution/`
Capability registry, LLM abstractions, forecasting, research discovery, learning from experience, and evolutionary optimization. Produces judgments and improvements, never direct market actions.

### Domain Plane
`markets/`, `mathematics/`, `portfolio/`, `strategies/`, `trading/` (incl. risk-related domain logic)
Market-domain definitions, mathematical primitives, factor/optimizer logic, strategy registry, and trading/exposure/risk domain logic. Pure domain semantics and computation.

### Data Plane
`data/`, `storage/`, `memory/`, `world_model/`
Data contracts, market data providers and validation, SQLite/Parquet persistence, memory stores/layers, and world-model entities/state/regimes. Owns representation and persistence of state.

### Execution & Integration Plane
`integrations/`, `simulation/`, `distributed/`, `coding/`
External broker/integration adapters, exchange/market simulation, queue/controller/worker infrastructure, and code-generation/sandboxing capabilities. The boundary to the outside world and to synthetic worlds.

### Governance & Operations Plane
`security/`, `compliance/`, `infrastructure/`, `ops/`
Secrets and security auditing, permissions/restrictions/audit controls, configuration/event bus/hardware/provenance, and health/metrics/tracing/alerts. Cross-cutting enforcement and observability.

### Evaluation & Presentation Plane
`backtesting/`, `evaluation/`, `experiments/`, `dashboard/`, `cli/`
Backtesting/Monte Carlo/walk-forward, evaluation labs/reports, experiment tracking, and CLI/TUI/web presentation. Measures the system and renders it to humans; never a source of live state mutation.

## 3. Dependency Direction

```
Presentation/CLI
    ↓
Control Plane
    ↓
Intelligence + Domain
    ↓
Data/Infrastructure
    ↓
External integrations
```

- Lower layers must not depend on presentation layers.
- Domain logic must not depend directly on CLI/dashboard.
- External providers belong behind interfaces/adapters.
- Security/compliance checks must remain enforceable at execution boundaries.
- Evaluation/backtesting must not silently mutate live trading state.
- Memory/world-model persistence must be accessed through defined interfaces.

## 4. Runtime Flow

```
Input
→ Mission/Goal
→ Agent/Brain
→ Planning/Reasoning
→ Prediction/Strategy
→ Risk/Compliance
→ Execution
→ Storage/Event Bus
→ Evaluation/Learning feedback
```

This is the intended macro-flow, not a guarantee of exact call paths. When modifying runtime behavior, verify exact wiring by inspecting only the relevant subsystem and its direct interfaces — do not scan the entire repository.

## 5. Folder Structure

```
src/orion/
├── agent/            # Runtime agent kernel: state, goals, execution, memory
├── agents/           # Agent implementations and controller
├── brain/            # Planning, reasoning, decisions, reflection, executive control
├── intelligence/     # Capability registry, LLM, sentiment, peer AI, tool use
├── models/           # Model providers, routing, lifecycle/registry
├── memory/           # Memory stores and memory layers
├── world_model/      # Entities, state, regimes, temporal/uncertainty modeling
├── orchestration/    # Scheduler, supervisor, system wiring
├── infrastructure/   # Configuration, environment, event bus, hardware, provenance
├── data/             # Data contracts, market data, providers, validation
├── markets/          # Market-domain definitions
├── mathematics/      # Mathematical primitives
├── prediction/       # Features, models, forecasting, regimes, uncertainty, volatility
├── portfolio/        # Factors and portfolio optimizers
├── strategies/       # Strategy registry
├── trading/          # Trading execution, exposure, risk, brokers, options, portfolio
├── integrations/     # External broker/integration adapters
├── simulation/       # Exchange/market simulation
├── backtesting/      # Backtesting, Monte Carlo, robustness, walk-forward
├── evaluation/       # Evaluation labs, baselines, holdouts, reports
├── evolution/        # Evolutionary optimization / self-improvement
├── learning/         # Datasets, experience, learner, mistakes, promotion, training
├── research/         # Research discovery, extraction, replication, synthesis
├── coding/           # Code generation, analysis, debugging, patching, sandboxing
├── compliance/       # Permissions, restrictions, audit/best-execution controls
├── security/         # Secrets and security auditing
├── storage/          # SQLite/Parquet persistence
├── distributed/      # Queue/controller/worker infrastructure
├── ops/              # Health, metrics, tracing, alerts
├── experiments/      # Experiment tracking
├── dashboard/        # CLI/TUI/web presentation
├── cli/              # User-facing command-line entry points
└── mission/          # Mission/objective layer
```

**Legacy top-level modules:** `config.py`, `domain.py`, `decision.py`, `execution.py`, `executive.py`, `forecasting.py`, `integrations.py`, `local_ai.py`, `providers.py`, `quant.py`, `registry.py`, `risk.py`, `workflow.py`, `data_quality.py`, `backtest.py` exist at the top level as legacy/compatibility surfaces. Do not assume they should be moved; treat them as deprecated entry points unless evidence proves otherwise.

## 6. Architectural Boundaries

| Area | Owns | Must Not Own |
|---|---|---|
| `agent` | Runtime lifecycle, state, goals, execution loop | Domain-specific trading logic |
| `agents` | Agent implementations, controller | Broker/infra plumbing |
| `brain` | Reasoning, planning, decisions, reflection | Broker connectivity |
| `intelligence` | Model/capability abstraction, tool use | Execution authority |
| `models` | Model providers, routing, lifecycle | Business decisions |
| `prediction` | Forecasting, features, uncertainty | Trade execution |
| `markets` / `mathematics` | Domain definitions, math primitives | I/O, providers, UI |
| `portfolio` / `strategies` | Optimization, strategy registry | Execution, UI |
| `trading` | Execution, exposure, trading risk | UI, external API plumbing |
| `integrations` | External-system adapters | Strategy logic |
| `simulation` | Synthetic exchange/market behavior | Live trading state |
| `data` / `storage` | Contracts, validation, persistence | Business decisions |
| `memory` / `world_model` | State representation, recall | Enforcement, execution |
| `compliance` / `security` | Enforcement, audit, secrets | Strategy generation |
| `infrastructure` / `ops` | Config, events, hardware, observability | Domain logic |
| `evaluation` / `backtesting` | Measurement, robustness analysis | Live execution / live-state mutation |
| `learning` / `evolution` | Improvement from experience | Direct market action |
| `dashboard` / `cli` | Presentation, user entry points | Domain state mutation |

## 7. Known Architectural Duplication / Migration Zones

These areas overlap conceptually and are **migration candidates, NOT automatic refactoring targets**. Do not consolidate them without a dedicated, explicitly-scoped task.

- `agent/` vs `agents/` — runtime kernel vs agent implementations/controller.
- `brain/` vs top-level `executive.py`, `decision.py`, `workflow.py` — newer executive control vs legacy decision/workflow surfaces.
- `integrations/` vs `trading/` broker implementations — external adapters vs trading-domain broker logic.
- `models/` vs `intelligence/` LLM abstractions — provider routing vs capability-level LLM use.
- `evaluation/` vs `backtesting/` — evaluation labs/reports vs backtest/Monte Carlo machinery.
- `learning/` vs `evolution/` — experience-based learning vs evolutionary optimization.
- Legacy top-level modules (`config.py`, `risk.py`, `quant.py`, `execution.py`, `backtest.py`, etc.) vs the newer packages they predate.

## 8. Rules for Future Changes

1. Read `ARCHITECTURE.md` first.
2. Inspect only the target subsystem and its direct interfaces.
3. Do not recursively read the repository unless required.
4. Preserve existing public APIs unless the task explicitly requires a breaking change.
5. Add tests only for changed behavior.
6. Prefer existing interfaces over introducing parallel abstractions.
7. Do not create another subsystem when an existing subsystem owns the responsibility.
8. Keep adapters at system boundaries.
9. Keep security/compliance enforcement close to irreversible actions.
10. Update `ARCHITECTURE.md` only when boundaries actually change.

## 9. Verification Strategy

Architecture work should use targeted checks, not full-suite runs:

- Import/compile check for changed modules.
- Targeted unit tests for the changed subsystem.
- Targeted integration tests for touched boundaries.
- Architecture boundary tests where applicable.

Do **not** run the entire test suite unless requested or clearly necessary.

