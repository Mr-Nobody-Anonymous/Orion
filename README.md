<div align="center">
  <pre>
   ██████╗ ██████╗ ██╗ ██████╗ ███╗   ██╗
  ██╔═══██╗██╔══██╗██║██╔═══██╗████╗  ██║
  ██║   ██║██████╔╝██║██║   ██║██╔██╗ ██║
  ██║   ██║██╔══██╗██║██║   ██║██║╚██╗██║
  ╚██████╔╝██║  ██║██║╚██████╔╝██║ ╚████║
   ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝
  </pre>
</div>

# 🛰️ ORION — Autonomous Financial Intelligence Platform

> **A self-evolving, safety-first research brain for markets — one system that observes, reasons, researches, predicts, evolves, simulates, decides, executes, and learns from every outcome.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Tests: 771 passing](https://img.shields.io/badge/Tests-771%20passing-green.svg)](https://github.com/)
[![Mode: LOCAL](https://img.shields.io/badge/Inference-LOCAL-purple.svg)](https://ollama.com/)
[![Execution: SIMULATION](https://img.shields.io/badge/Execution-SIMULATION-orange.svg)](https://github.com/)
[![Safety: First](https://img.shields.io/badge/Safety-First-red.svg)](https://github.com/)
[![Zero Fake Integrations](https://img.shields.io/badge/Zero%20Fake-Integrations-green.svg)](https://github.com/)
[![Trading alpha: NOT YET DEMONSTRATED](https://img.shields.io/badge/Trading%20alpha-NOT%20YET%20DEMONSTRATED-red.svg)](https://github.com/)

> **771 tests passing. No evidence of trading alpha yet.** The next milestone is a reproducible out-of-sample result, not more infrastructure. See [PHASE_31G_AUDIT.md](docs/architecture/PHASE_31G_AUDIT.md) for the predict/plan/persist layer (tool executor with immutable invocation log, persistent agent loop, real goal manager, predict-before-act), and [PHASE_31D_AUDIT.md](docs/architecture/PHASE_31D_AUDIT.md) for the broader plan.

---

## 🌟 What Makes ORION Different?

ORION is **not** a folder of adapters wrapped around a pile of repositories. It is a single
application whose brain runs a closed, auditable cognitive loop, and whose "intelligence"
must survive the scrutiny of its own backtests, stress tests, and governance gates before
it may touch money.

Every decision is provisional. Every claim carries a source and a confidence.
Every capability is either **executed code** or **explicitly blocked** — never a promise.

```
🔥 INTELLIGENCE MUST PROVE ITSELF BEFORE IT MOVES CAPITAL 🔥
```

---

## 🧠 The Master Loop

```
             ┌──────────────────────┐
             │    WORLD / DATA      │   data/ — validated typed observations
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │ SITUATIONAL AWARENESS│   world_model/ — regime, volatility, quality
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │   MEMORY + WORLD     │   memory/ — 7 bounded layers, compression
             └──────────┬───────────┘
                        ▼
           ┌────────────┴────────────┐
           ▼                         ▼
    ┌─────────────┐          ┌─────────────┐
    │  RESEARCH   │          │  PREDICTION │   research/ + prediction/
    └──────┬──────┘          └──────┬──────┘
           └───────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  GENERATIVE BRAIN    │   hypothesis/, coding/generation
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │  EVOLUTION ENGINE    │   evolution/ — candidates only
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │ SIMULATION / BACKTEST│   simulation/ + backtesting/
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │      EVALUATION      │   learning/evaluation, benchmarking/
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │   EXECUTIVE BRAIN    │   brain/ — 16-phase cognitive loop
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │     RISK ENGINE      │   trading/risk — deterministic gate
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │     EXECUTION        │   trading/execution — SimulatedBroker
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │      OUTCOME → LEARN │   learning/self_improvement → back to top
             └──────────────────────┘
```
---

## 🚀 Core Capabilities

### 🧠 **Executive Brain — a Real Cognitive Loop**
The `ExecutiveOrchestrator` in `brain/orchestrator.py` runs every cycle through
16 explicit phases — `OBSERVE → UNDERSTAND → REMEMBER → RESEARCH → HYPOTHESIZE →
PREDICT → GENERATE OPTIONS → SIMULATE → EVALUATE → PLAN → RISK CHECK → DECIDE →
ACT → OBSERVE OUTCOME → REFLECT → LEARN` — and records a fully auditable
`LoopTrace` (decision, rationale, confidence, risk verdict, every phase payload).
The loop is **deterministic given identical inputs**, so the audit trail is
reproducible.

### 🌍 **Situational Awareness That Admits Ignorance**
Every value in the world model (`world_model/state.py`) carries a `KnowledgeStatus`:

| Status | Meaning |
|---|---|
| `known` | Directly observed/validated |
| `unknown` | Never observed |
| `estimated` | Derived, not measured |
| `predicted` | Model-generated forward view |
| `uncertain` | Present but low-confidence |
| `conflicting` | Multiple sources disagree |

Nine explicit state objects (`WorldState/MarketState/PortfolioState/AgentState/ResearchState/ModelState/RiskState/DecisionState/LearningState`) keep the
executive situationally aware across market regime, volatility, liquidity,
data quality, portfolio exposure, open positions, model confidence and
disagreement.

### 🗂️ **Layered Memory with Compression, Not Hoarding**
`memory/layered.py` provides seven layers — working, episodic, semantic,
procedural, market, research, trading — with bounded `WorkingMemory` that
**compresses evicted items into episodic memory** instead of accumulating raw
data. Retrieval is scored by term relevance ×2 + importance, then recency.

### 🔬 **Autonomous Research Agent**
The `research/` subsystem forms a question → discovers real papers via the
**public OpenAlex metadata API** → extracts structured profiles → synthesizes
consensus *and* conflicts → generates hypotheses → runs controlled experiments
(unit test → backtest → walk-forward) → replicates → records provenance. On a
network outage it returns an explicit `BLOCKED` response — **it never invents
evidence**.

### 📊 **Multi-Model Council (No Blind Averages)**
`prediction/ensembles/model_council.py` combines trend, mean-reversion, EWMA
and linear-trend forecasters with **regime-dependent weights** — momentum is
weighted higher in bull regimes, mean-reversion in ranges — and tracks
disagreement (epistemic uncertainty), outlier members, and calibrated
prediction intervals.

### 🧬 **Evolution That Rewards Survival, Not Just Returns**
`evolution/` evolves strategy candidates through deterministic tournament
selection, blend/uniform crossover, mutation, and diversity enforcement.
`Fitness.score` weighs **risk-adjusted return (35%), stability (20%),
generalization (20%), calibration (15%)**, minus drawdown and turnover
penalties. Raw return alone never wins.

### 🧪 **Contamination-Safe Benchmarking**
`benchmarking/suite.py` scores every forecaster with a strict walk-forward
protocol (each prediction sees only bars strictly before its target), so
look-ahead leakage is structurally impossible. Strategies are compared on the
*identical* price series with the *identical* metrics.

### 🛡️ **Risk Above Intelligence**
Execution is always `AI → decision → risk → execution`. The deterministic
`RiskEngine` (`trading/risk.py`) enforces order-notional, exposure, correlation,
position, and minimum-confidence limits plus an emergency-stop kill switch,
**independent of any language model**. Rejected proposals never reach a broker.

### 🔄 **Controlled Self-Learning**
`learning/` turns observation → prediction → decision → outcome into validated
training material through versioned datasets, leakage detection, chronological
splits, model cards, calibration error, and a **deny-by-default promotion gate**
(`infrastructure/governance.py`). Nothing auto-promotes because a validation
metric improved.

### 🧑‍💻 **Code Generation, Sandboxed by Policy**
`coding/` generates, analyzes, statically verifies, debugs, and patches
candidate strategy code. Unsafe constructs are rejected before execution; a
dedicated process/container runtime sandbox remains a **documented blocker**.
Generated code can never modify production directly.

### 🌐 **Asset-Class Agnostic Core**
One risk/portfolio/decision/memory core; `markets/` contributes specialist
parameters for **equities, ETFs, crypto, futures, FX, commodities, fixed
income, options, and prediction markets** — without ever overriding the risk
engine.
---

## 🧱 Architecture (the canonical tree)

All product code lives under `src/orion/`. Everything is real, tested code —
**no placeholder modules** (the Phase-30 audit found zero stubs in the package).

```
orion/
├── brain/                          # 🧠 The executive brain
│   ├── orchestrator.py             #   16-phase cognitive loop, auditable LoopTrace
│   ├── executive.py                #   Risk-before-execution coordinator
│   ├── decision.py                 #   DecisionContext / DecisionEngine → Action
│   ├── reflection.py               #   Prediction-vs-outcome error analysis
│   ├── metacognition.py            #   Confidence / uncertainty self-assessment
│   ├── goal_management.py          #   Goal hierarchy + horizon steering
│   ├── hypothesis.py               #   Hypothesis artifacts
│   ├── planning.py  reasoning.py   #   Planner + reasoning contracts
│   └── __init__.py
├── intelligence/                  # 🤖 Agent & language layer
│   ├── llm/
│   │   ├── providers.py            #   LLMProvider protocol + Ollama wiring
│   │   └── ollama.py               #   Local model runtime config
│   ├── financial_reasoning/
│   │   └── reasoner.py             #   Structured financial conclusions + uncertainty
│   ├── sentiment/
│   │   └── analyzer.py             #   Deterministic sentiment analysis
│   ├── tool_use/
│   │   ├── registry.py             #   Permissioned tool registry (AgentProfile)
│   │   └── tools.py                #   backtest / simulate / pricing / regime / stats / memory
│   └── __init__.py
├── prediction/                    # 📊 Forecasting & uncertainty
│   ├── forecasting.py              #   LinearTrendForecaster, PredictionEnsemble
│   ├── time_series/                #   Momentum, MeanReversion, Volatility, EWMA
│   ├── ensembles/
│   │   └── model_council.py        #   Regime-weighted council + disagreement
│   ├── statistical/                #   descriptive.py, signals.py
│   ├── machine_learning/ridge.py   #   MLRidgeForecaster
│   ├── regime/detector.py          #   Market-regime detection
│   ├── uncertainty/estimators.py   #   Epistemic + confidence intervals
│   ├── calibration/metrics.py      #   Calibration error
│   └── __init__.py
├── trading/                       # 💹 Execution, risk, portfolio, strategies
│   ├── execution.py                #   SimulatedBroker, AlpacaAdapter (BLOCKED)
│   ├── risk.py                     #   RiskEngine, RiskLimits (deterministic gate)
│   ├── strategies/catalog.py       #   Strategy catalog
│   ├── portfolio/                  #   allocator.py, constructor.py
│   ├── brokers/                    #   Broker adapters
│   └── __init__.py
├── markets/                       # 🌐 Asset-class specialists
│   ├── specialist.py               #   specialist_for(config, asset_class)
│   ├── equities/  etfs/  crypto/  futures/  forex/  commodities/
│   └── fixed_income/  options/  prediction_markets/
├── mathematics/                   # 🧮 Math & risk math
│   ├── pricing.py  derivatives.py  probability.py  risk_math.py
│   └── statistics.py  optimization.py
├── backtesting/                   # ⏪ Backtest rigor
│   ├── engine.py                   #   Vectorized momentum backtest, fee-aware
│   ├── evaluation.py               #   Sharpe / Sortino / Calmar / drawdown / win-rate
│   ├── walk_forward/               #   Purged walk-forward windows
│   ├── monte_carlo/                #   GBM + block bootstrap + Monte Carlo
│   ├── stress_testing/             #   Flash crash, vol spike, regime break, liquidity gap
│   ├── robustness/                 #   Overfit / look-ahead / survivorship checks
│   └── __init__.py
├── benchmarking/                  # 🧪 Contamination-safe comparisons
│   └── suite.py                    #   Walk-forward model + strategy scoring
├── learning/                      # 🔄 Controlled continual learning
│   ├── experience.py  datasets.py  training.py
│   ├── evaluation.py  promotion.py  self_improvement.py
│   └── __init__.py
├── evolution/                     # 🧬 Deterministic candidate evolution
│   ├── engine.py  fitness.py  operators.py  population.py  selection.py
├── models/                        # 📁 Model runtime & routing
│   ├── local/ollama.py            #   Local OllamaProvider (qwen2.5 default)
│   ├── cloud/provider.py           #   NullCloudProvider (raises CloudProviderUnavailable)
│   ├── routing/router.py           #   HardwareProfile → ModelTier
│   ├── registry/                   #   ImmutableRegistry, RegistryStatus
│   └── __init__.py
├── memory/                        # 🗂️ Bounded layered memory
│   ├── layered.py  working.py  store.py  short_term/
├── world_model/                   # 🌍 Situational state
│   ├── state.py                   #   FinancialWorldModel, 9 state objects, StateValue
│   ├── entities.py  regimes.py  temporal.py  uncertainty.py
├── data/                          # 📦 Typed data contracts
│   ├── contracts.py               #   60+ dataclasses (Asset, MarketQuote, Prediction...)
│   └── validation.py               #   DataQualityValidator
├── research/                      # 🔬 Autonomous research
│   ├── discovery.py                #   OpenAlex metadata discovery (BLOCKED-safe)
│   ├── extraction.py  synthesis.py #   Paper profiles, evidence conflicts
│   ├── experiments.py             #   ExperimentPipeline (unit→backtest→walk-forward)
│   ├── replication.py  agent.py     #   Trials + ResearchAgent loop
├── coding/                        # 🧑💻 Code intelligence
│   ├── generation.py  analysis.py  verification.py
│   └── sandbox.py  debugging.py  patching.py
├── simulation/                     # 🎲 Market simulation
│   └── market.py                   #   Seeded bootstrap paths (p05 / p95)
├── infrastructure/                # 🏗️ Foundations
│   ├── configuration.py            #   OrionConfig: mode LOCAL / CLOUD / HYBRID
│   ├── event_bus.py  governance.py  hardware.py  provenance.py
├── orchestration/                 # 🎛️ System wiring
│   ├── system.py                   #   OrionSystem — the ONE composition root
│   ├── scheduler.py                #   Budgeted autonomous research scheduler
│   └── supervisor.py               #   Job / health supervision
├── security/                      # 🔒 Security
│   ├── secrets.py                  #   SecretVault, PromptGuard, redaction
│   └── audit.py                    #   AuditLog, ApprovalGate
├── cli/main.py                    # ⌨️ status/analyze/backtest/train/evaluate/research/
│                                     #   discover-papers/evolve/simulate/benchmark/doctor
├── backtest.py  config.py  data_quality.py  decision.py  domain.py
├── event_bus.py  execution.py  executive.py  forecasting.py  quant.py
├── local_ai.py  providers.py  registry.py  risk.py  workflow.py  integrations.py
└── __init__.py                     #   Public exports

tests/                             # âœ… 771 passing (4 skipped, 0 failing)
├── unit/  integration/  end_to_end/  brain/  prediction/  trading/
├── research/  coding/  evolution/  learning/  memory/  models/
├── backtesting/  benchmarking/  mathematics/  security/  intelligence/
└── world_model/

docs/                              # 📚 Full docs + architecture diagrams
source_repositories/               # 🗄️ Preserved upstream checkouts (NEVER modified)
workers/                           # 🔌 Reserved for isolated heavyweight runtimes
configs/  integrations/            # Reserved deployment / integration surface
```
---

## 🎮 Quick Start

Everything runs from the repository root — no database, no broker account, no GPU required.

```powershell
# System health + capabilities
python -m orion status
python -m orion doctor

# Full executive cycle on a symbol (16-phase loop, auditable trace)
python -m orion run AAPL --prices 100 101 100.5 102 103 104 105 --actual-return 0.02

# Analyze with the model council + financial reasoner
python -m orion analyze AAPL

# Backtest, simulate, evolve, benchmark
python -m orion backtest --prices 100 101 100.5 102 103 104 105
python -m orion simulate --prices 100 101 100.5 102 103 104 105 --paths 200
python -m orion evolve --prices 100 101 100.5 102 103 104 105 --population 12
python -m orion benchmark --prices 100 101 100.5 102 103 104 105

# Train / evaluate a residual model
python -m orion train
python -m orion evaluate                                     # 200-bar synthetic default
python -m orion evaluate --no-walk-forward --prices 100 101 100.5 102 103 104 105  # short series

# Autonomous research against the public OpenAlex metadata API
python -m orion research "market regime forecasting"
python -m orion discover-papers "financial time series forecasting"
```

Or use the library directly:

```python
from orion.data.contracts import Asset, AssetClass
from orion.prediction.ensembles.model_council import build_default_council
from orion.orchestration.system import OrionSystem

system = OrionSystem()
print(system.status())

council = build_default_council()
result = council.predict(
    Asset("AAPL", AssetClass.EQUITY),
    [100, 101, 100.5, 102, 103, 104, 105],
    regime="bull",
)
print(result.prediction.expected_return)  # Decimal
print(result.disagreement)                # epistemic uncertainty among members
```

---

## 🔬 Live Demo — an Executive Cycle, End to End

When you run `python -m orion run DEMO`, the executive walks all 16 phases and
prints an auditable trace:

```
OBSERVE ──► UNDERSTAND ──► REMEMBER ──► RESEARCH ──► HYPOTHESIZE ──► PREDICT
  ▼
GENERATE OPTIONS ──► SIMULATE ──► EVALUATE ──► PLAN ──► RISK CHECK
  ▼
DECIDE: BUY  ──► ACT (fill recorded)  ──► OBSERVE OUTCOME ──► REFLECT ──► LEARN
```

```json
{
  "cycle_id": "cycle-0001",
  "market_regime": "bull",
  "decision": "BUY",
  "confidence": "0.9383",
  "status": "estimated",
  "rationale": "weighted net=+0.399 over 2 sources; consistent; status=estimated",
  "risk_approved": true
}
```

Every number carries a `source`, a `confidence`, and a `KnowledgeStatus` —
ORION never lets an estimate masquerade as a fact.
---

## ⚙️ Configuration

ORION is configured with `OrionConfig` (`src/orion/infrastructure/configuration.py`).
Mode is configuration, never code:

```python
from orion.infrastructure.configuration import AIMode, ExecutionMode, OrionConfig

config = OrionConfig(
    mode=AIMode.LOCAL,            # LOCAL | HYBRID | CLOUD (cloud is BLOCKED by default)
    execution_mode=ExecutionMode.SIMULATION,  # SIMULATION | PAPER | LIVE
    autonomy_level=0,
    live_trading_enabled=False,
)
```

Non-negotiable defaults:

| Setting | Default | Why |
|---|---|---|
| `mode` | `LOCAL` | no implicit cloud calls; cloud must be explicitly configured |
| `execution_mode` | `SIMULATION` | live trading is a deliberate, audited decision |
| `live_trading_enabled` | `False` | `AlpacaAdapter` refuses to construct otherwise |
| `autonomy_level` | `0` | autonomous research, evolution, and promotion stay gated |

Risk limits (`trading/risk.py::RiskLimits`) are similarly explicit:
`max_order_notional`, `max_portfolio_exposure`, `max_correlation`,
`min_model_confidence`, and `emergency_stop`. Research, learning, evolution,
and generated code can never alter them.
---
## 🧪 Testing

```powershell
python -m pytest tests -q       # full suite (771 tests)
python -m compileall src        # byte-compile every module
python -m orion doctor          # health + safety posture check
```

Currently **771 tests pass** (4 skipped, 0 failing) across `tests/unit`, `tests/integration`,
`tests/end_to_end`, plus per-domain suites for brain, prediction, trading,
research, coding, evolution, learning, memory, models, backtesting,
benchmarking, mathematics, security, intelligence, evaluation, registry_v2,
ops, storage, exchange, options, market_data, providers, brokers,
backtesting, and world model. Tests
cover **failure paths** (network-outage `BLOCKED` responses, risk-gate
rejections, leakage detection, short-series inputs, look-ahead contamination,
live-trading refusal), not just happy paths.
---

## 🚦 Roadmap

- [x] 🧠 Executive brain with a 16-phase, reproducible cognitive loop
- [x] 🌍 Situational awareness with explicit `known / unknown / estimated / predicted / uncertain / conflicting`
- [x] 🗂️ Seven-layer bounded memory with compression policy
- [x] 🔬 Autonomous research agent (discovery, extraction, synthesis, experiments, replication, provenance)
- [x] 📊 Regime-weighted multi-model council with disagreement tracking
- [x] 🧬 Deterministic multi-objective candidate evolution
- [x] 🧪 Contamination-safe walk-forward benchmarking (models + strategies)
- [x] 🛡️ Deterministic risk engine, kill switch, risk-gated paper execution
- [x] 🔄 Controlled continual learning with leakage detection, model cards, and a deny-by-default promotion gate
- [x] 🧑💻 Code generation / analysis / static verification / debugging / patching
- [x] 🌐 Asset-class specialists (equities, ETFs, crypto, futures, FX, commodities, fixed income, options, prediction markets)
- [x] 🔒 Secret isolation, prompt guarding, tamper-evident audit, approval gates
- [x] ⏪ Walk-forward, Monte Carlo, stress, and robustness backtesting
- [ ] ☁️ Cloud inference — BLOCKED until a configured, budgeted, evaluated provider exists
- [ ] 🔴 Live execution — BLOCKED until a credential-isolated, audited broker adapter is enabled
- [ ] 🏗️ Generated-code process/container sandbox — BLOCKED (static gate in place)
- [ ] 🗄️ Heavyweight upstream runtimes (QLib, Kronos, FinGPT, QuantLib) as isolated workers
---
## 📚 Documentation

Start at **[docs/README.md](docs/README.md)**. The full architecture suite
includes the ORION brain loop, research loop, learning loop, evolution loop,
model routing, local/cloud architecture, risk architecture, data flow, and
memory architecture — each with an ASCII diagram:

| Doc | What it answers |
|---|---|
| [System overview](docs/architecture/SYSTEM_OVERVIEW.md) | How everything is *one* system |
| [Brain](docs/architecture/BRAIN.md) | The 16-phase executive loop |
| [Research loop](docs/architecture/RESEARCH_LOOP.md) | Paper → idea → hypothesis → experiment → report |
| [Learning loop](docs/architecture/LEARNING_LOOP.md) | Experience → validate → train → promote (governed) |
| [Evolution loop](docs/architecture/EVOLUTION_LOOP.md) | Population → mutate → select → diversify |
| [Model routing](docs/architecture/MODEL_ROUTING.md) | Hardware-aware local inference + council |
| [Risk](docs/architecture/RISK_ARCHITECTURE.md) | AI → decision → risk → execution |
| [Data flow](docs/architecture/DATA_FLOW.md) | World → state → memory → forecast → outcome |
| [Memory](docs/architecture/MEMORY_ARCHITECTURE.md) | Seven bounded layers with compression |
| [Capability registry](docs/architecture/CAPABILITY_REGISTRY.md) | Upstream audit, licenses, integration status |

Domain guides live under `docs/agents`, `docs/research`, `docs/learning`,
`docs/evolution`, `docs/models`, `docs/trading`, `docs/risk`, `docs/data`,
and `docs/coding`; provenance under `docs/provenance`.
---
## 🔒 Governance & Honest Status

ORION may research, generate, experiment, train, evaluate, and *propose*.
ORION may **never silently** change risk limits, enable live trading, replace
production models, alter security permissions, delete datasets, or remove
provenance/audit logs.

| Capability | Status |
|---|---|
| Situational state, layered memory, research discovery, prediction council, evolution, simulation, paper execution, benchmarking, learning + promotion gate, code intelligence, security, persistent agent kernel (with hierarchical goals, calibrated belief updating, persistent loop, immutable invocation log, predict-before-act) | **IMPLEMENTED** (771 tests) |
| Cloud inference | **BLOCKED** — `NullCloudProvider` raises until a configured, budgeted, evaluated provider exists |
| Live execution | **BLOCKED** — `AlpacaAdapter` raises `LiveTradingDisabledError` by construction |
| Generated-code runtime sandbox | **BLOCKED** — static verification gate in place; dedicated runtime sandbox required |
| Heavyweight upstream runtimes (QLib, Kronos, FinGPT, QuantLib) | **WORKER / REFERENCE** — preserved unmodified under `source_repositories/` |

No capability is documented as *integrated* that is not executed code.
Repositories in `source_repositories/` are preserved and **never modified**.
---
## 📜 License & Philosophy

ORION is an ORION project: the canonical application in `src/orion/` is
kept free of GPL/AGPL-derived code from the preserved repositories, and those
upstreams retain their own licenses. Everything in the canonical package runs
on the Python standard library plus optional, explicitly configured external
services.

> **The backtest is never the promise. The benchmark is never the proof.**
> ORION's edge is that it *knows* the difference — and engineers its own
> skepticism into every promotion gate.

Built as one continuous system — not thirty repositories behind adapters. The
objective is not to claim "AGI"; it is to build the strongest
experimentally-validated autonomous financial intelligence platform that
available hardware, data, models, and discipline can support.