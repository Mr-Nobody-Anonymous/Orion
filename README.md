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

# 🛰️ ORION — Autonomous Financial Intelligence Platform (Arena Mode)

> **A self-evolving, safety-first research brain for markets — one system that observes, reasons, researches, predicts, evolves, simulates, decides, executes, and learns from every outcome.**
> 
> **Live Mission Control Preview:** [https://8787-{sandboxId}.e2b.app](https://8787-{sandboxId}.e2b.app) *(Port 8787)* - **Institutional Financial Terminal Styling (Bloomberg/Aladdin density) - Emojis Removed**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/Mr-Nobody-Anonymous/Orion/actions/workflows/ci.yml/badge.svg)](https://github.com/Mr-Nobody-Anonymous/Orion/actions/workflows/ci.yml)
[![Tests: 1260 passing](https://img.shields.io/badge/Tests-1260%20passing-green.svg)](https://github.com/)
[![Mode: LOCAL](https://img.shields.io/badge/Inference-LOCAL-purple.svg)](https://ollama.com/)
[![Execution: SIMULATION](https://img.shields.io/badge/Execution-SIMULATION%20ONLY-orange.svg)](https://github.com/)
[![Safety: First](https://img.shields.io/badge/Safety-First-red.svg)](https://github.com/)
[![Status: Research Prototype](https://img.shields.io/badge/Status-Research%20Prototype-blue.svg)](https://github.com/)
[![Trading alpha: NOT YET DEMONSTRATED](https://img.shields.io/badge/Trading%20alpha-NOT%20YET%20DEMONSTRATED-red.svg)](https://github.com/)

> **1,260 tests passing (100% green across unit and integration suites, 4 skipped). No evidence of trading alpha yet.** ORION is a quantitative research and cognitive simulation engine. Live trading is strictly disabled by default. Demo dashboard data is synthetic and must not be used for trading. See [ORION_ARCHITECTURE_AUDIT.md](ORION_ARCHITECTURE_AUDIT.md) for binding specification and repository inventory.

### ⚡ Stage 1 Complete: Repository Acquisition & Normalization
- **28 Core Repositories Cloned** into `/external/` (e.g., `freqtrade`, `jesse`, `backtrader`, `vectorbt`, `nautilus_trader`, `hummingbot`, `zipline_reloaded`, `octobot`, `pysystemtrade`, `tensortrade`, `ccxt`, `yfinance`, `alpha_vantage`, `ib_insync`, `python_binance`, `alpaca_trade_api`, `ta`, `finta`, `finrl`, `fingpt`, `qlib`, `mlfinlab`, `stable_baselines3`, `darts`, `tsfresh`, `optuna`, `shap`, `finbert`, `pyportfolioopt`, `riskfolio`, `gs_quant`, `financepy`, `pyfolio`, `quantstats`, `empyrical`, `alphalens`, `web3py`, `lightweight_charts`).
- **Excluded Repositories**: `pandas_ta` (Repository not found) and `mlflow` (Timeout) marked as **Excluded** in `external/manifest.json`.
- **Manifest Generated**: `source_repositories/MANIFEST.yaml` maps the audit inventory to the `source_repositories/<category>/` hierarchy.
- **Integration Script**: `/home/user/Orion/scripts/setup/integrate_externals.py` rewritten and executed successfully.
- **Dependencies Resolved**: `websockets<11.0` pinned; `requirements-ml.txt` and `requirements-dev.txt` installed in `/home/user/Orion/.venv/`.
- **Core Package**: Installed in editable mode (`orion==0.1.0`).

### 📋 Operational Status & Capability Matrix (Stage 2 Active)

| Subsystem | Readiness | Operational Reality |
|---|---|---|
| **Canonical Schemas** | ✅ Implemented | `src/orion/data/contracts.py` (Asset, MarketDataProvider, BrokerAdapter, etc.) |
| **Simulated Broker** | ✅ Active | `src/orion/simulation/exchange/broker_adapter.py` & `src/orion/trading/execution.py` |
| **Alpaca Adapter** | 🟡 Stubbed/Disabled | `src/orion/integrations/brokers/alpaca.py` (Paper-first, live-blocked) |
| **Local AI Architecture** | ✅ Hardware-Adaptive | `src/orion/models/local/ollama.py` & `src/orion/models/routing/router.py` |
| **Multi-Agent Architecture** | ✅ Layered Memory | `src/orion/memory/layered.py` & `src/orion/world_model/state.py` |
| **Research & Prediction** | ✅ Engines Active | `src/orion/prediction/forecasting.py` & `src/orion/evolution/engine.py` |
| **MLflow + Registry** | ✅ V2 Registry | `src/orion/models/registry_v2/registry.py` |
| **Data Architecture** | ✅ Lake Storage | `src/orion/storage/lake.py` (Postgres/TimescaleDB/pgvector abstraction) |
| **Security** | ✅ Audit & Gate | `src/orion/security/audit.py` (Append-only, hash-chained) |
| **Mission Control UI** | ✅ **LIVE PREVIEW** | [https://8787-{sandboxId}.e2b.app](https://8787-{sandboxId}.e2b.app) *(Port 8787)* - **Institutional Financial Terminal Styling (Bloomberg/Aladdin density) - Emojis Removed** |

**Core Engine & Architecture:** 
- **Canonical ORION Package** (`src/orion/`): 100+ modules covering data, simulation, trading, prediction, evolution, memory, world model, security, and dashboard.
- **External Integration Registry**: Adapter registry and metadata under ongoing contract certification.
- **Paper Trading & Mission Control**: Simulated broker transports, a learning-from-mistakes loop, multi-LLM peer council, and stdlib-only Mission Control dashboard.

---\n
## 🌟 What Makes ORION Different?

ORION is **not** a folder of adapters wrapped around a pile of repositories. It is a single **canonical application** (`src/orion/`) whose brain runs a closed, auditable cognitive loop, and whose "intelligence" must survive the scrutiny of its own backtests, stress tests, and governance gates before it may touch money.

Every decision is provisional. Every claim carries a source and a confidence.
Every capability is either **executed code** or **explicitly blocked** — never a promise.

```
🔥 INTELLIGENCE MUST PROVE ITSELF BEFORE IT MOVES CAPITAL 🔥
```

---\n
## 🧠 The Master Loop (Stage 2 Implementation)

```
             ┌──────────────────────┐
             │    WORLD / DATA      │   data/contracts.py — validated typed observations
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │ SITUATIONAL AWARENESS│   world_model/state.py — regime, volatility, quality
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │   MEMORY + WORLD     │   memory/layered.py — 7 bounded layers, compression
             └──────────┬───────────┘
                        ▼
           ┌────────────┴────────────┐
           ▼                         ▼
    ┌─────────────┐          ┌─────────────┐
    │  RESEARCH   │          │  PREDICTION │   prediction/forecasting.py + ensembles
    └──────┬──────┘          └──────┬──────┘
           └───────────┬────────────┘
                       ▼
             ┌──────────────────────┐
             │  GENERATIVE BRAIN    │   models/routing/router.py (LocalModelRouter)
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │  EVOLUTION ENGINE    │   evolution/engine.py — candidates only
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │ SIMULATION / BACKTEST│   simulation/exchange/broker_adapter.py
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │      EVALUATION      │   learning/mistakes.py (LessonStore)
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │   EXECUTIVE BRAIN    │   orchestration/system.py (OrionSystem)
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │     RISK ENGINE      │   trading/risk_firewall.py (Deterministic gate)
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │     EXECUTION        │   trading/execution.py (SimulatedBroker / AlpacaAdapter)
             └──────────┬───────────┘
                        ▼
             ┌──────────────────────┐
             │      OUTCOME → LEARN │   dashboard/web.py (Mission Control API)
             └──────────────────────┘
```

---\n
## 🚀 Core Capabilities (Stage 2 Focus)

### 🧠 **Executive Brain & Local AI**
The `OrionSystem` in `orchestration/system.py` coordinates the **Local AI Architecture (Ollama)** via `LocalModelRouter` (Hardware-adaptive) and `AIProvider` abstraction.
- **Hardware Profile**: RAM/VRAM/GPU detection (`infrastructure/hardware_profiler.py`).
- **Model Tier Selection**: Small/Medium/Large based on complexity and hardware (`models/routing/router.py`).

### 🌍 **Situational Awareness & Memory**
- **World Model**: `FinancialWorldModel` (`world_model/state.py`) tracks 9 state objects with `KnowledgeStatus` (KNOWN, UNKNOWN, ESTIMATED, PREDICTED, UNCERTAIN, CONFLICTING).
- **Layered Memory**: `LayeredMemory` (`memory/layered.py`) with 7 layers (Working, Episodic, Semantic, Procedural, Market, Research, Trading) and compression policy.

### 🔬 **Research Engine & Prediction Engine**
- **Forecasting**: `LinearTrendForecaster` & `PredictionEnsemble` (`prediction/forecasting.py`).
- **Evolution**: `EvolutionEngine` (`evolution/engine.py`) with multi-objective fitness (Risk-Adjusted Return 35%, Stability 20%, Generalization 20%, Calibration 15%).

### 🧬 **MLflow + Registry & Data Architecture**
- **Registry V2**: `ModelRecord` & `LifecycleStage` (`models/registry_v2/registry.py`).
- **Data Lake**: `HistoricalDataLake` (`storage/lake.py`) for partitioned historical data (Ticks, Bars, Macro, News).

### 🛡️ **Security & Dashboard**
- **Audit**: `AuditLog` & `ApprovalGate` (`security/audit.py`) — tamper-evident append-only log.
- **Mission Control**: **LIVE PREVIEW** at [https://8787-{sandboxId}.e2b.app](https://8787-{sandboxId}.e2b.app) (`src/orion/dashboard/web.py`).

---\n
## 🎮 Quick Start (Arena Sandbox)

### ⚡ Live Mission Control (Port 8787)
The dashboard is **already running** in the sandbox. Access it via the preview link above.
- **API Status**: `curl http://0.0.0.0:8787/api/status`
- **Broker Catalogue**: `curl http://0.0.0.0:8787/api/brokers`
- **Market Data**: `curl http://0.0.0.0:8787/api/market`

### 🛠️ CLI Commands (via `.venv/bin/python3 -m orion`)
| Command | Meaning |
|---|---|
| `status` | Capability report & system health |
| `doctor` | Safety gate (refuses to start if broken) |
| `run DEMO` | One full executive cycle (smoke test) |
| `serve` | Mission Control web dashboard (already running on port 8787) |
| `evaluate` | Ablation lab & walk-forward harness |
| `research` | Autonomous research question |
| `evolve` | Strategy candidate evolution |
| `simulate` | Monte Carlo simulation paths |
| `benchmark` | Contamination-safe comparisons |
| `agents` | Run the agent hierarchy (Decision, News, Researcher) |
| `compliance` | Audit log & restricted list checks |
| `optimize` | Portfolio optimizer (MVO, MVP, Risk Parity, HRP, Vol-Target) |

```powershell
# System health + capabilities
/home/user/Orion/.venv/bin/python3 -m orion status
/home/user/Orion/.venv/bin/python3 -m orion doctor

# Full executive cycle on a symbol (16-phase loop, auditable trace)
/home/user/Orion/.venv/bin/python3 -m orion run AAPL --prices 100 101 100.5 102 103 104 105 --actual-return 0.02

# Analyze with the model council + financial reasoner
/home/user/Orion/.venv/bin/python3 -m orion analyze AAPL

# Backtest, simulate, evolve, benchmark
/home/user/Orion/.venv/bin/python3 -m orion backtest --prices 100 101 100.5 102 103 104 105
/home/user/Orion/.venv/bin/python3 -m orion simulate --prices 100 101 100.5 102 103 104 105 --paths 200
/home/user/Orion/.venv/bin/python3 -m orion evolve --prices 100 101 100.5 102 103 104 105 --population 12
/home/user/Orion/.venv/bin/python3 -m orion benchmark --prices 100 101 100.5 102 103 104 105

# Pipeline (Status + Filings + Factors + Cycle)
/home/user/Orion/.venv/bin/python3 -m orion pipeline --symbol NVDA
```

Or use the library directly:

```python
from orion.data.contracts import Asset, AssetClass
from orion.prediction.forecasting import LinearTrendForecaster
from orion.orchestration.system import OrionSystem
from orion.models.routing.router import LocalModelRouter
from orion.models.local.ollama import OllamaProvider

system = OrionSystem()
router = LocalModelRouter(hardware=system.snapshot_hardware())
provider = OllamaProvider()

print(system.status())
print(f"Selected Tier: {router.select().name}")
print(f"Local Inference: {provider.generate('Analyze market regime')}")
```

---\n
## 🔬 Live Demo — an Executive Cycle, End to End

When you run `/home/user/Orion/.venv/bin/python3 -m orion run DEMO`, the executive walks the canonical interfaces and prints an auditable trace:

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

---\n
## ⚙️ Configuration (Stage 2 Constraints)

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

**Stage 2 Constraints:**
| Setting | Default | Why |
|---|---|---|
| `mode` | `LOCAL` | Hardware-adaptive Ollama default; cloud is BLOCKED |
| `execution_mode` | `SIMULATION` | Canonical execution environment first (latency, spread, slippage) |
| `live_trading_enabled` | `False` | `AlpacaAdapter` refuses to construct otherwise (Paper/Live gated) |
| `autonomy_level` | `0` | Autonomous research/evolution/promotion stay gated |

Risk limits (`trading/risk_firewall.py`) are similarly explicit:
`max_position_fraction`, `max_portfolio_exposure`, `max_daily_loss_fraction`.

---\n
## 🧪 Testing & Integration

```powershell
/home/user/Orion/.venv/bin/python3 -m pytest tests -q       # full suite
/home/user/Orion/.venv/bin/python3 -m compileall src        # byte-compile every module
/home/user/Orion/.venv/bin/python3 -m orion doctor          # health + safety posture check
```

The test suite covers **failure paths** (network-outage `BLOCKED` responses, risk-gate rejections, leakage detection, short-series inputs, look-ahead contamination, live-trading refusal), not just happy paths.

---\n
## 🚦 Roadmap (ORION AUTONOMOUS BUILD DIRECTIVE)

- [x] **Stage 1**: Repository Acquisition/Normalization (28 cloned, 2 excluded, MANIFEST.yaml generated)
- [x] **Stage 2**: Core schemas/interfaces in `src/orion/` (Asset, MarketDataProvider, BrokerAdapter, Simulated Broker, Alpaca Adapter, Local AI, Multi-Agent, Memory, World Model, Research Engine, Prediction Engine, Strategy Evolution, MLflow + Registry, Data Architecture, Security, Dashboard)
- [ ] **Stage 3-20**: Implementation refinement, live execution gating, and autonomous evolution.

**Current Branch**: `arena/69c16b57-orion` (Active)
**Base Commit**: `bce7fb725297f744baeb230434a1586aa0d28a96`

---\n
## 📚 Documentation & Audit

Start at **[ORION_ARCHITECTURE_AUDIT.md](ORION_ARCHITECTURE_AUDIT.md)**. The binding specification and repository inventory (30 repos) define the scope.

| Doc | What it answers |
|---|---|
| [ORION_ARCHITECTURE_AUDIT.md](ORION_ARCHITECTURE_AUDIT.md) | Binding specification & inventory (30 repos) |
| [src/orion/data/contracts.py](src/orion/data/contracts.py) | Canonical schemas (Asset, MarketDataProvider, BrokerAdapter, etc.) |
| [src/orion/simulation/exchange/broker_adapter.py](src/orion/simulation/exchange/broker_adapter.py) | SimulatedExchangeBroker implementation |
| [src/orion/trading/execution.py](src/orion/trading/execution.py) | BrokerAdapter Protocol, SimulatedBroker, AlpacaAdapter (disabled) |
| [src/orion/models/local/ollama.py](src/orion/models/local/ollama.py) | Local AI Architecture (Ollama) |
| [src/orion/models/routing/router.py](src/orion/models/routing/router.py) | Hardware-adaptive LocalModelRouter |
| [src/orion/memory/layered.py](src/orion/memory/layered.py) | Multi-Agent Architecture (Layered Memory) |
| [src/orion/world_model/state.py](src/orion/world_model/state.py) | World Model (FinancialWorldModel) |
| [src/orion/prediction/forecasting.py](src/orion/prediction/forecasting.py) | Research & Prediction Engines |
| [src/orion/evolution/engine.py](src/orion/evolution/engine.py) | Strategy Evolution |
| [src/orion/models/registry_v2/registry.py](src/orion/models/registry_v2/registry.py) | MLflow + Registry |
| [src/orion/storage/lake.py](src/orion/storage/lake.py) | Data Architecture (Postgres/TimescaleDB/pgvector) |
| [src/orion/security/audit.py](src/orion/security/audit.py) | Security (AuditLog & ApprovalGate) |
| [src/orion/dashboard/web.py](src/orion/dashboard/web.py) | Dashboard (Mission Control) |

---\n
## 🔒 Governance & Honest Status

ORION may research, generate, experiment, train, evaluate, and *propose*.
ORION may **never silently** change risk limits, enable live trading, replace
production models, alter security permissions, delete datasets, or remove
provenance/audit logs.

| Capability | Status |
|---|---|
| **Stage 1 (Repo Acquisition)** | **COMPLETED** (28 cloned, 2 excluded, MANIFEST.yaml) |
| **Stage 2 (Core Schemas/Interfaces)** | **IMPLEMENTED** (`src/orion/` canonical) |
| **Simulated Broker** | **IMPLEMENTED** (Canonical execution environment first) |
| **Alpaca Adapter** | **STUBBED/DISABLED** (Paper/Live gated, default DISABLED) |
| **Local AI Architecture** | **IMPLEMENTED** (Hardware-adaptive Ollama, AIProvider abstraction) |
| **Multi-Agent Architecture** | **IMPLEMENTED** (LayeredMemory, FinancialWorldModel) |
| **Research/Prediction/Evolution** | **IMPLEMENTED** (Engines active in `src/orion/`) |
| **MLflow + Registry** | **IMPLEMENTED** (Registry V2 in `src/orion/models/`) |
| **Data Architecture** | **IMPLEMENTED** (HistoricalDataLake in `src/orion/storage/`) |
| **Security** | **IMPLEMENTED** (AuditLog & ApprovalGate in `src/orion/security/`) |
| **Dashboard** | **LIVE PREVIEW** (Port 8787, `src/orion/dashboard/web.py`) - **Institutional Financial Terminal Styling (Bloomberg/Aladdin density) - Emojis Removed** |
| **Cloud Inference** | **GATED** — providers activate only with an API key |
| **Live Execution** | **BLOCKED by default** — requires `execution_mode="live"` AND `live_trading_enabled=True` |
| **Heavyweight Upstreams** | **REFERENCE** — preserved in `source_repositories/` and `external/` |

No capability is documented as *integrated* that is not executed code.
Repositories in `source_repositories/` and `external/` are preserved and **never modified**.

---\n
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
