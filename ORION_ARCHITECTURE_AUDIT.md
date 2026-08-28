# ORION — Architectural Audit of Existing Repositories

**Date:** 2026-08-27
**Scope:** `C:\Users\hp\Desktop\Orion` — 30 repositories
**Status:** Phase 1 deliverable. No existing repository has been modified.
**Author:** ORION Lead Architect (autonomous analysis)

---

## 0. Executive Summary

The Orion workspace contains three rough categories of code:

1. **Core quantitative / ML libraries** (qlib, vectorbt, backtrader, Lean, QuantLib, py_vollib, Time-Series-Library, Kronos, FinGPT, FinRL family) — mature, reusable as _dependencies_, not as code to merge.
2. **Agent / LLM orchestration experiments** (AgenticTrading, Vibe-Trading, QuantMuse, hermes-agent, a-evolve, evolver, kimi-k3-in-c, airllm, ollama) — useful for interface patterns and local-inference strategy; mostly too application-specific to merge.
3. **Niche trading verticals** (freqtrade, jesse, intelligent-trading-bot, prediction-market projects, homerun, assume, Stock-Trading-Environment) — reference material for specific asset classes.

**Key finding:** there is heavy functional duplication across at least six backtesting engines, five RL-trade pipelines, four LLM-agent shells, and three prediction-market bots. The correct ORION move is **composition via interfaces and pip-installable dependencies**, never source-level merging.

Three repos are questionable/empty: `neural_prophet` is an empty checkout (only a `.git` folder); `kimi-k3-in-c` requires a 1.56 TB checkpoint (impractical locally); `airllm` targets very-large-model inference on constrained hardware — niche value only.

**Recommended posture:** ORION becomes the canonical Python package under `src/orion`, and it _imports_ qlib/vectorbt/backtrader/py_vollib/Ollama rather than embedding them. Legacy repos stay frozen in place as upstream references.

## 1. Repository Inventory

| Repo                                    | Lang     | Purpose                                                        | Backtest | Live       | RL  | LLM | DB                      | Verdict                                                    |
| --------------------------------------- | -------- | -------------------------------------------------------------- | -------- | ---------- | --- | --- | ----------------------- | ---------------------------------------------------------- |
| qlib                                    | Py       | MSRA quant platform: data, factors, models                     | ✔        | partial    | ✔   | –   | file/duckdb-style store | **Adopt** (research core)                                  |
| vectorbt                                | Py+Rust  | Vectorized portfolio backtesting                               | ✔        | –          | –   | –   | –                       | **Adopt**                                                  |
| backtrader                              | Py       | Event-driven backtester, live brokers                          | ✔        | ✔          | –   | –   | –                       | Adopt selectively                                          |
| Lean                                    | C#       | QuantConnect engine: institutional backtest/live               | ✔        | ✔          | ✔   | –   | custom file formats     | Keep isolated; wrap API                                    |
| QuantLib                                | C++      | Fixed-income derivatives pricing                               | –        | –          | –   | –   | –                       | **Adopt** via Python bindings                              |
| py_vollib                               | Py       | Option pricing/Greeks/IV                                       | –        | –          | –   | –   | –                       | **Adopt**                                                  |
| freqtrade                               | Py       | Crypto bot: ML (FreqAI), hyperopt, live                        | ✔        | ✔          | ✔   | –   | SQLite/PG               | Adopt FreqAI patterns; not the shell                       |
| jesse                                   | Py       | Crypto backtest framework                                      | ✔        | ✔          | –   | –   | PG                      | Reference only                                             |
| Time-Series-Library                     | Py       | THU: SOTA TS forecasting models zoo                            | –        | –          | –   | –   | –                       | **Adopt**                                                  |
| Kronos                                  | Py       | K-line (candlestick) foundation model                          | –        | –          | –   | –   | –                       | **Adopt** benchmark candidate                              |
| neural_prophet                          | Py       | Interpretable TS forecasting                                   | –        | –          | –   | –   | –                       | EMPTY checkout — re-clone or drop                          |
| FinGPT                                  | Py       | Financial-domain LLMs + LoRA finetune                          | –        | –          | –   | ✔   | HF hub                  | **Adopt** for sentiment/news tasks                         |
| FinRL                                   | Py       | DRL trading agents (PPO/A2C/DDPG…)                             | sim      | paper      | ✔   | –   | files                   | Adopt agent zoo concept                                    |
| FinRL-Meta                              | Py       | Market-environment generators for DRL                          | sim      | –          | ✔   | –   | –                       | Merge with FinRL usage                                     |
| FinRL-Trading                           | Py       | Stock-selection pipeline w/ deploy                             | ✔        | docker     | ✔   | –   | –                       | Superseded by FinRL-Meta                                   |
| AgenticTrading                          | Py       | LLM trading-agent playground + dashboard                       | ✔        | paper      | –   | ✔   | app-managed             | Adopt orchestration/UI ideas                               |
| Vibe-Trading                            | Py+React | Personal trading agent, MCP-ish tools                          | –        | –          | –   | ✔   | app                     | Reference for tool-calling UX                              |
| QuantMuse                               | Py+C++   | Full quant system w/ LLM analysis, factors, dashboards         | ✔        | partial    | –   | ✔   | heterogeneous           | Mine factor/risk modules                                   |
| hermes-agent                            | Py       | General autonomous CLI agent w/ memory, skills, MCP            | –        | –          | –   | ✔   | state schemas           | **Adopt patterns**: memory/state/skills                    |
| a-evolve                                | Py       | Framework to evolve agents against benchmarks                  | –        | –          | –   | ✔   | artifacts               | Adopt for strategy-evolution loop                          |
| evolver                                 | JS       | Agent self-evolution: memory/skill genes                       | –        | –          | –   | ✔   | own store               | Conceptual adopt only (Node.js)                            |
| ollama                                  | Go       | Local LLM runtime (llama.cpp based)                            | –        | –          | –   | ✔   | blob store              | **Adopt** as infra dependency                              |
| kimi-k3-in-c                            | C99      | CPU-only mega-model inference                                  | –        | –          | –   | ✔   | external ckpt           | NOT practical (1.56 TB model) — discard from core          |
| airllm                                  | Py       | Sequential-layer inference for giant models                    | –        | –          | –   | ✔   | –                       | Niche; discard unless RAM-bound need appears               |
| assume                                  | Py       | Electricity market agent-based simulation + DRL                | sim      | –          | ✔   | –   | influx/duckdb           | Domain-out-of-scope; keep isolated (energy markets)        |
| Stock-Trading-Environment               | Py       | Minimal Gym stock env                                          | env      | –          | ✔   | –   | csv                     | Trivial; superseded by FinRL-Meta                          |
| intelligent-trading-bot                 | Py       | Crypto ML signal service (offline train / online infer parity) | ✔        | telegram   | –   | –   | redis/sqlite            | **Adopt** feature-parity pattern                           |
| homerun                                 | Py+React | Prediction-market OS: strategies, shadow fills, dashboard      | ✔        | paper→live | –   | –   | PostgreSQL              | **Strong adopt patterns** for PM vertical & fill simulator |
| polymarket-kalshi-weather-bot           | Py       | Weather-driven PM arbitrage bot                                | partial  | ✔          | –   | –   | –                       | Vertical logic reference                                   |
| Prediction-Markets-Trading-Bot-Toolkits | Rust     | Multi-PM toolkit (Polymarket/Kalshi)                           | –        | ✔          | –   | –   | config                  | Use as-is behind adapter                                   |

---

## 2. Dependency Graph (High-Level)

```
                    ┌────────────────────────────────────┐
                    │   ORION (canonical package)        │
                    │   - executive, agents, world_model │
                    │   - memory, prediction, risk       │
                    └────────────────┬───────────────────┘
                                     │  imports (pip-style)
       ┌──────────────┬──────────────┼──────────────┬──────────────┐
       ▼              ▼              ▼              ▼              ▼
   ┌────────┐    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │  qlib  │    │ vectorbt │   │backtrader│   │QuantLib  │   │py_vollib │
   │  Kronos│    │   Lean   │   │ freqtrade│   │  jesse   │   │  airllm  │
   │FinRL-M │    │ FinGPT   │   │  Lean    │   │          │   │          │
   └────┬───┘    └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
        │             │              │              │              │
        └─────────────┴──────┬───────┴──────────────┴──────────────┘
                             ▼
                    ┌────────────────┐
                    │  DATA LAYER    │
                    │  (PostgreSQL + │
                    │   TimescaleDB) │
                    └────────┬───────┘
                             ▼
                    ┌────────────────┐
                    │  EXECUTION     │
                    │  (Broker APIs) │
                    └────────────────┘
```

**Dependency conflicts identified:**
- `backtrader`, `freqtrade`, `jesse` each define their own broker abstractions → ORION needs a single `BrokerAdapter` interface; only one of these should be the default execution engine.
- `FinRL-Trading` is superseded by `FinRL-Meta` (per FinRL docs) → import only `FinRL-Meta` and treat the former as deprecated.
- `Kronos` and `Time-Series-Library` (TSlib) both ship time-series transformer code with overlapping model families → pick Kronos for forecasting, TSlib for benchmarking/legacy models.
- `Ollama` is a Go binary daemon; it is consumed via HTTP API, not imported as Python.

---

## 3. Architecture Comparison

| Repo                  | Style                       | Data flow             | Extensibility | Notes                                                  |
| --------------------- | --------------------------- | --------------------- | ------------- | ------------------------------------------------------ |
| qlib                  | Pipeline + factor library   | File-based provider   | High          | Best research harness; reuse data + alpha modules      |
| vectorbt              | Vectorized pandas/numpy     | In-memory             | Medium        | Great for fast parameter sweeps                        |
| backtrader            | Event-driven OOP            | Line/Cerebro          | Medium        | Mature but slower; good for live trading parity        |
| Lean                  | Algorithm framework         | Lean Engine API       | High          | C# only; wrap as sidecar via REST or Docker            |
| FinRL-Meta            | DRL benchmark suite         | Gym envs              | High          | Reuse environments, not training code                  |
| AgenticTrading        | LLM tool-calling shell      | JSON tool I/O         | Low           | Copy UX patterns only                                  |
| hermes-agent          | Agent CLI w/ skills+memory  | YAML/JSON             | High          | Adopt skill registry, episodic memory schema           |
| QuantMuse             | Monolithic quant app        | Internal              | Low           | Mine specific modules (factor, risk), not whole        |
| ollama                | Daemon (Go)                 | HTTP                  | n/a           | Infrastructure, not a library                          |
| homerun               | FastAPI + React SPA         | REST + WS             | High          | Adopt shadow-fill simulator + strategy registry        |
| Kronos                | Pretrained TS foundation    | PyTorch               | Medium        | Inference wrapper only; fine-tune separately           |

---

## 4. Model Comparison (Forecasting & NLP)

| Model                | Family             | Best for                         | Weakness                       | ORION use              |
| -------------------- | ------------------ | -------------------------------- | ------------------------------ | ---------------------- |
| Kronos               | TS Transformer     | Multivariate price forecasting   | New, limited validation        | Default forecaster     |
| Time-Series-Library  | Many (Informer/Autoformer/PatchTST) | Long-horizon univariate | Hyperparam sensitive  | Benchmark suite        |
| neural_prophet       | (NOT PRESENT)      | Daily business metrics           | Empty repo                     | Skip                   |
| FinGPT               | LLM + LoRA         | Financial sentiment/news NLG     | Heavy GPU                      | Optional via cloud     |
| FinRL                | DRL (PPO/A2C/DDPG) | Portfolio allocation             | Sample inefficient             | RL strategy plugin     |
| QLib models          | LightGBM/MLP       | Alpha factors                     | Linear-style signals           | Factor research         |
| QuantMuse (internal) | Mixed              | Multi-asset signals              | Opaque                         | Mine selectively       |

**Rule:** no model is promoted without walk-forward OOS evaluation.

---

## 5. Trading-Engine Comparison

| Engine      | Speed  | Live trading | Broker support         | ORION verdict                         |
| ----------- | ------ | ------------ | ---------------------- | ------------------------------------- |
| vectorbt    | ★★★★★  | –         | –                      | Primary backtester for vector sweeps   |
| backtrader  | ★★     | ✔          | IB, Oanda, many        | Fallback engine; useful for live parity|
| Lean        | ★★★★   | ✔         | IB, brokerages         | Optional sidecar (C# service)          |
| freqtrade   | ★★★    | ✔          | Crypto exchanges       | Reference only; ORION stays broker-agnostic |
| jesse       | ★★★★   | ✔            | Crypto (limited)       | Reference only                         |
| FinRL-Meta  | n/a    | –            | –                      | Environments only                      |

---

## 6. Agent / LLM Framework Comparison

| Repo             | Strength                           | Weakness                    | ORION takeaway                       |
| ---------------- | ---------------------------------- | --------------------------- | ------------------------------------ |
| AgenticTrading   | Tool-calling pattern               | Single-app, no memory layer | Adopt tool schema                    |
| hermes-agent     | Skills + episodic memory + MCP     | General-purpose             | Adopt memory/skill interfaces        |
| a-evolve         | Evolve agents against benchmarks   | Benchmark-specific          | Adopt for strategy-evolution loop    |
| evolver (JS)     | Skill-genome concept               | Different language          | Conceptual only                      |
| QuantMuse        | LLM-assisted factor analysis       | Monolithic                  | Mine factor prompts                  |
| Vibe-Trading     | MCP-style tools                    | Personal-scale              | Reference UX                         |

---

## 7. Data Source Comparison

| Repo                          | Data handled          | Format       | ORION use                  |
| ----------------------------- | --------------------- | ------------ | -------------------------- |
| qlib                          | OHLCV, fundamentals   | binary       | Primary market data        |
| FinRL-Meta                    | OHLCV via Yahoo/Akshare| pandas     | Pipeline examples          |
| Polymarket/Kalshi bots        | Prediction markets    | REST JSON    | Adapter only               |
| intelligent-trading-bot       | Crypto                | csv/sqlite   | Parity pattern             |
| homerun                       | Prediction markets    | Postgres     | Schema ideas               |

**Gaps (not covered by any existing repo):**
- Order-book / microstructure data
- Options chains & IV surfaces
- Macroeconomic series (FRED, ECB)
- News NER/dedup at scale

ORION will need its own connectors for these.

---

## 8. Local-AI Capability Analysis

| Component   | Capability                                  | Limitation                              |
| ----------- | ------------------------------------------- | --------------------------------------- |
| Ollama      | LLM inference (Llama, Mistral, Qwen, Phi)   | RAM-bound; largest sensible model ~32B Q4 |
| airllm      | Sequential-layer loading of huge models     | Very slow; only justified for 70B+      |
| kimi-k3-in-c| Pure-C CPU inference                       | Needs 1.56 TB checkpoint — impractical |
| FinGPT      | LoRA-tuned financial LLM                   | Cloud/GPU heavy                         |

**Conclusion:** Ollama is the only realistic local-AI foundation for ORION. `airllm` and `kimi-k3-in-c` are kept on disk as reference but excluded from the default path.

---

## 9. Cloud-AI Integration Analysis

No existing repo provides a clean multi-provider abstraction. The closest is hermes-agent's skill concept. ORION will need to build a new `AIProvider` interface (OpenAI, Anthropic, Azure OpenAI, local Ollama, custom HTTP) with retry, token-budget, and PII redaction.

---

## 10. Reusable-Component Recommendations

**Adopt (import as dependency):**
- qlib, vectorbt, backtrader, QuantLib, py_vollib
- FinRL-Meta (envs only), FinGPT (optional), Kronos
- Ollama (HTTP daemon)
- hermes-agent (interface patterns, not code)
- homerun (Postgres schema + fill simulator)

**Adopt (pattern/idea, not code):**
- AgenticTrading tool-calling UX
- a-evolve benchmark-driven evolution
- intelligent-trading-bot offline/online parity
- QuantMuse risk prompts

**Do NOT merge into ORION source:**
- freqtrade, jesse (stay separate; ORION is broker-agnostic)
- Lean (different language; sidecar if needed)
- Stock-Trading-Environment, FinRL-Trading (superseded)
- assume (energy-market out of scope)
- evolver (Node.js; conceptual only)

**Discard from active path:**
- kimi-k3-in-c (impractical checkpoint size)
- airllm (niche; revisit only if a 70B+ model becomes a hard requirement)
- neural_prophet (empty checkout)

---

## 11. Proposed ORION Architecture

```
            ┌────────────────────────────────────────────┐
            │           ORION EXECUTIVE BRAIN            │
            │  (orchestrator, debate, final proposal)    │
            └────────────────────┬───────────────────────┘
                                 │
   ┌──────────────┬──────────────┼──────────────┬──────────────┐
   ▼              ▼              ▼              ▼              ▼
┌────────┐   ┌────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│Percept.│   │Reasoning│  │ Memory  │   │World    │   │Learning │
│Agents  │   │Engine   │  │ System  │   │Model    │   │Pipeline │
└───┬────┘   └────┬────┘  └────┬────┘   └────┬────┘   └────┬────┘
    │             │            │             │             │
    └─────────────┴──────┬─────┴─────────────┴─────────────┘
                         ▼
              ┌──────────────────────┐
              │   PREDICTION ENGINE  │
              │   (Kronos / TSlib /  │
              │    Qlib / FinRL)     │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   STRATEGY ENGINE    │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   PORTFOLIO + RISK   │
              │   (deterministic)    │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   DECISION ENGINE    │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   EXECUTION (Broker  │
              │   Adapter,paper→live)│
              └──────────────────────┘
```

---

## 12. Proposed Technology Stack

| Layer           | Technology                                 | Rationale                                |
| --------------- | ------------------------------------------ | ---------------------------------------- |
| Language        | Python 3.11+                               | Dominant in existing repos; ML ecosystem |
| Deep learning   | PyTorch                                    | Kronos/FinGPT/TSlib already use it       |
| Orchestration   | asyncio + internal event bus               | Avoid Celery weight; full control        |
| API services    | FastAPI                                    | Lightweight, type-hinted, async          |
| Time-series DB  | TimescaleDB (PostgreSQL extension)         | Native for OHLCV, compresses well        |
| Metadata DB     | PostgreSQL                                 | Models, experiments, decisions           |
| Cache / queue   | Redis                                      | Pub-sub, low-latency state               |
| Vector store    | pgvector (in Postgres) initially           | Avoid separate infra until proven needed |
| Experiment track| MLflow (or lightweight SQLite registry)    | Model registry + reproducibility         |
| Container       | Docker / docker-compose                    | Reproducible services                    |
| Dashboard       | React (Vite) + FastAPI                     | Same stack as homerun (familiar)         |
| Local LLM       | Ollama                                     | Already installed                        |

---

## 13. Proposed Database Architecture

**Three logical stores, all in Postgres for simplicity:**

1. `marketdata` (TimescaleDB hypertable)
   - Columns: ts, symbol, open, high, low, close, volume, source, quality
   - Continuous aggregates for daily/weekly rollups

2. `metadata` (regular tables)
   - `models`, `experiments`, `strategies`, `decisions`, `risk_events`, `agents`, `episodes`

3. `embeddings` (pgvector)
   - `documents` (news, filings), `episodes` (past decisions + outcomes)

**Why pgvector first:** avoids running a separate Qdrant/Weaviate until ORION actually needs million-scale vector recall.

---

## 14. Proposed Model-Training Architecture

```
   Historical data + features
            │
            ▼
   ┌─────────────────────┐
   │  Experiment Harness │  (deterministic splits, seeds, walk-forward)
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │  Candidate Models   │  (Kronos, TSlib, Qlib LGB, RL, LLM-as-feature)
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │  Validation Gate    │  (OOS, regime-stratified, statistical test)
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │  Model Registry     │  (versioned, immutable, signed)
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │  Approval (human)   │  (LEVEL ≥ 3 only)
   └──────────┬──────────┘
              ▼
   ┌─────────────────────┐
   │  Deployment         │  (hot-swap, canary, instant rollback)
   └─────────────────────┘
```

No model overwrites production silently. Every promotion writes a new immutable registry row.

---

## 15. Proposed Local / Cloud Architecture

```
   ┌──────────────────────┐        ┌──────────────────────┐
   │   LOCAL ORION        │        │   CLOUD ORION        │
   │                      │        │                      │
   │  - Ollama            │  sync  │  - OpenAI/Anthropic  │
   │  - Kronos inference  │ ◄────► │  - Heavy training    │
   │  - Risk + Execution  │        │  - Research agent    │
   │  - Paper / Shadow    │        │  - Backtest farms    │
   └──────────────────────┘        └──────────────────────┘
              │                              │
              └──────────┬───────────────────┘
                         ▼
              ┌──────────────────────┐
              │  SYNC LAYER          │
              │  - signed exports    │
              │  - anonymized metrics│
              │  - candidate models  │
              │  - validation gate   │
              └──────────────────────┘
```

**Rule:** cloud never directly drives execution. Cloud outputs are validated locally before any local use.

---

## 16. Security Architecture

- **Secrets:** OS keyring or `.env` (gitignored). No secrets in LLM prompts.
- **Sandboxing:** strategy code runs in a subprocess with a timeout and no network by default.
- **Prompt-injection defense:** external text (news, filings) is treated as data, never as instructions. A separate `UntrustedText` wrapper marks and isolates it.
- **Order signing:** every order requires a risk-engine signature; the broker adapter refuses unsigned orders.
- **Audit log:** every decision, hypothesis, and model change is appended to an immutable WORM store.
- **Dependency hygiene:** `pip-audit` in CI; pinned versions; vendored license notice.

---

## 17. Development Roadmap

| Phase | Theme                  | Deliverable                                                         | Status |
| ----- | ---------------------- | ------------------------------------------------------------------- | ------ |
| 1     | Audit                  | This document                                                       | ✔      |
| 2     | Core                   | Config, logging, event bus, schemas, agent/model interfaces         | ⏳     |
| 3     | Local Intelligence     | Ollama integration, memory, basic reasoning, market data connector  | ⏳     |
| 4     | Research Models        | Kronos, TSlib, Qlib — benchmark only                                | ⏳     |
| 5     | Quant Engine           | vectorbt primary, backtrader fallback, QuantLib, py_vollib          | ⏳     |
| 6     | Specialist Agents      | Market, Fundamental, Macro, News, Sentiment, Options, Crypto, etc.  | ⏳     |
| 7     | World Model + Memory   | Postgres schemas, pgvector, episodic store                          | ⏳     |
| 8     | Prediction + Decision  | End-to-end: perception → world → predict → hypothesize →risk→decide | ⏳     |
| 9     | Simulation             | Full simulated market, fill model, latency                          | ⏳     |
| 10    | Paper Trading          | Realistic paper broker adapter                                      | ⏳     |
| 11    | Learning Pipeline      | Outcome DB → training → validation → registry → approval → deploy   | ⏳     |
| 12    | Local/Cloud Sync       | Signed export/import, model promotion across envs                   | ⏳     |
| 13    | Dashboard              | React SPA on FastAPI                                                | ⏳     |
| 14    | Live Trading           | Only after Phase 13 sign-off, disabled by default                   | ⏳     |

**Autonomy levels** (default = 0):
- 0 Research only
- 1 Recommendations
- 2 Paper trading
- 3 Limited autonomous
- 4 Autonomous (strict risk limits)

---

## 18. Open Questions for Human Approval (before Phase 2)

1. Which broker/exchange to target first for paper trading? (IBKR, Alpaca, Binance testnet, all?)
2. Which initial asset universe? (US equities only, or include crypto + FX from day 1?)
3. Acceptable baseline hardware for local LLM? (decides Ollama model size cap)
4. Any data licensing constraints we should encode from the start?
5. Is MLflow acceptable, or do you prefer a custom registry?

---

## 19. Stop Condition

**Phase 1 complete.** No existing repository has been modified. Awaiting human approval before beginning Phase 2 (Core scaffolding).

---

## 20. Owner Decisions (Phase 2 Constraints)

Recorded 2026-08-27 in response to the Phase 2 questionnaire in Section 18. These four decisions are now **binding constraints** on Phase 2 onward. The audit is otherwise unchanged.

### 20.1 Broker strategy: Simulated broker first, Alpaca second, others later

- The **canonical** execution environment in Phase 2 is a fully simulated broker running locally. ORION can train/test thousands or millions of decisions without any external API dependency.
- The **first** real-API adapter is **Alpaca** (equities, ETFs, options, crypto via a single API; paper environment available; options including index options supported in paper as of July 2026).
- IBKR and Binance adapters are **deferred** until later phases (post-Phase 10).
- The simulated broker is **not** a paper-trading proxy — it must model market impact, latency-based slippage, queue position, price improvement, regulatory fees, and dividends, none of which Alpaca's paper environment simulates.
- Alpaca's free IEX-only real-time equity feed and OPRA-gated options feed are accepted limitations; the higher-tier data plan is **not** a Phase 2 dependency.
- The `BrokerAdapter` ABC from Section 12 of the brief is the only interface the rest of ORION sees. `SimulatedBroker` and `AlpacaAdapter` are two implementations of that interface. ORION's Executive Brain, agents, risk engine, decision engine, portfolio engine, and strategy engine must **never** import Alpaca-specific types.

### 20.2 Asset universe: US equities + ETFs, but every interface is asset-class agnostic

- Phase 2 implements data and execution for **US equities and US ETFs only**.
- However, the asset abstraction is **multi-asset from day 1**. No core component (Executive Brain, World Model, Memory, Risk Engine, Decision Engine, Execution Engine, Memory subsystem) may assume that an asset is an equity. Every interface must accept an `Asset` object with `asset_class`, not a stock-specific type.
- Expansion roadmap (not Phase 2 work, but the interfaces must not block it):

  | Phase | Asset class added | Reason it comes when it does |
  | ----- | ----------------- | ---------------------------- |
  | 3     | Crypto            | Forces 24/7, fragmented liquidity, funding handling |
  | 4     | Futures + commodities | Roll mechanics, contango/backwardation |
  | 5     | FX + fixed income | Session-based trading, term structure |
  | 6     | Options           | Greeks, IV surface, complex risk |
  | 7     | Prediction markets | Settlement, ambiguity, event-driven |
  | 8+    | Multi-broker / multi-venue | Aggregation, smart routing |

### 20.3 Local AI: heterogeneous, hardware-adaptive, never a single model

- ORION auto-detects hardware at startup: system RAM, GPU model, GPU VRAM, CPU, free disk, CUDA, Ollama availability, quantization support, current system load.
- A `LocalModelRouter` selects a model **tier** per task based on detected capability and the requested task's complexity. Small models handle routine tasks; larger models handle difficult research/reasoning when available.
- Default tier mapping (overridable in config, never hard-coded in code):

  | Hardware | Default local model tier |
  | -------- | ------------------------ |
  | 16 GB RAM, no discrete GPU | ~7B Q4 (e.g., Qwen2.5-7B, Llama-3.1-8B, Mistral-7B) |
  | 32 GB RAM, 8 GB VRAM | ~7–13B Q4 |
  | 64 GB RAM, 12–16 GB VRAM | ~13B Q4 |
  | 128 GB+ RAM, 24 GB VRAM | ~32B Q4 |
  | Server-class | Larger / specialized |

- `kimi-k3-in-c` (1.56 TB checkpoint per its README) and `airllm` are **off the critical path**. They remain on disk as reference and may be evaluated empirically later; they are not wired into the default inference path.
- The LLM is **one reasoning component** inside ORION, not the brain. The Executive Brain, all quantitative/ML prediction models, risk engine, decision engine, portfolio engine, and memory subsystems must function without the LLM being available. The LLM augments; it does not gate.
- ORION must support three operational modes — `LOCAL`, `HYBRID`, `CLOUD` — without any change to the rest of the architecture. Mode is configuration, not code.
- The `AIProvider` interface from Section 16 of the brief is the only interface ORION's brain sees. `OllamaProvider`, `OpenAIProvider`, `AnthropicProvider`, `AzureOpenAIProvider`, and `HttpProvider` are all implementations of it.

### 20.4 Tracking: MLflow + custom ORION strategy registry + optional DVC

- **MLflow** handles the conventional ML lifecycle: training runs, hyperparameters, metrics, model versions, dataset references, evaluation results, experiment comparisons, model promotion.
- A **custom ORION strategy registry**, backed by PostgreSQL, handles artifacts that are specifically trading-shaped and are not a natural fit for MLflow:
  - Strategy versions (immutable, append-only)
  - Entry/exit logic
  - Asset universe and time horizon
  - Risk parameters, position-sizing rules
  - Backtest results, walk-forward results
  - Transaction-cost and slippage assumptions
  - Market-regime tags where the strategy is validated
  - Paper and live performance
  - Strategy lineage (dataset → features → model → prediction system → strategy → risk config → backtest → paper → production)
  - Deployment status (`EXPERIMENTAL` / `VALIDATING` / `APPROVED` / `PRODUCTION` / `RETIRED` / `REJECTED`)
- **DVC** (or equivalent) is used for dataset versioning, but is **optional** in Phase 2. If dataset infrastructure becomes a blocker, a simpler Postgres-backed immutable dataset hash registry is acceptable as a stopgap. The non-negotiable requirement is **immutable, reproducible dataset versioning** — not DVC specifically.
- The immutable-append-only rule from Section 14 of the brief applies to all three: MLflow, the custom registry, and the dataset store. Nothing in production is ever overwritten in place; every change is a new version, and comparisons are always between two versions.
- Typical promotion record the registry must be able to answer:

  ```
  Strategy:    ORION-MOMENTUM-042
  Model:       Kronos-v17
  Dataset:     US-EQUITIES-2026-08  (DVC hash a3f1…)
  Regime:      HIGH_VOLATILITY
  Backtest:    +31.4%
  Walk-forward: +18.7%
  Max DD:      8.2%
  Sharpe:      1.71
  Slippage:    v3
  Risk model:  v12
  Status:      VALIDATING
  ```

---

## 21. Stop Condition (Updated)

Phase 1 complete. Phase 2 constraints above are now locked. **No existing repository has been modified, and no new directories or files have been created outside this addendum.** Awaiting explicit human approval to begin Phase 2 (Core scaffolding: configuration, logging, event bus, data schemas, agent interfaces, model interfaces, simulated `BrokerAdapter`, MLflow + custom registry + dataset-store stubs, hardware profiler + LocalModelRouter skeleton, asset-class-agnostic data layer for US equities + ETFs).
