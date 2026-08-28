# ORION Component Integration Matrix

**Date:** 2026-08-27 (original); cross-walk added 2026-08-28
**Scope:** 30 legacy checkouts under `C:\Users\hp\Desktop\Orion`, plus the ORION core.
**Method:** targeted inspection of repository manifests, READMEs, entry points, and license files. This matrix is an engineering decision record, not a claim that every upstream feature has been validated in production.

**Current state (2026-08-28):** 711 tests passing, all three
ORION quality gates green. The capability registry
([PHASE_31D_AUDIT.md](../architecture/PHASE_31D_AUDIT.md)) and
the persistent agent kernel
([PHASE_31E_AUDIT.md](../architecture/PHASE_31E_AUDIT.md)) are
the runtime layer that wraps the per-repository decisions in
this matrix. See [CHANGELOG.md](../architecture/CHANGELOG.md)
for the documentation cross-walk.

## Canonical ORION Layers

| Component | Status | Notes |
| --- | --- | --- |
| `src/orion/data` | [INTEGRATED] | Canonical asset, market data, order, portfolio, risk, execution, and training contracts |
| `src/orion/infrastructure` | [INTEGRATED] | Configuration, event bus, and hardware detection |
| `src/orion/brain` | [INTEGRATED] | Executive, decision, reasoning, planning, and hypothesis layers |
| `src/orion/prediction` | [INTEGRATED] | Baseline forecasting and ensemble prediction |
| `src/orion/trading` | [INTEGRATED] | Simulated broker, risk gates, and portfolio boundary |
| `src/orion/learning` | [INTEGRATED] | Training, experience capture, and candidate evaluation |
| `src/orion/models/local` | [ADAPTER] | Ollama HTTP integration for local inference |
| `src/orion/models/cloud` | [BLOCKED] | Explicitly rejects requests until a credential-isolated provider, budget, and evaluation policy are configured |
| `source_repositories/*` | [REFERENCE] | Preserved upstream sources and checkouts |

| Repository | Purpose / useful components | Models / training / inference / backtest / live | Key dependencies | License | Performance / difficulty | ORION destination | Decision and reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| a-evolve | Benchmark-driven agent evolution | Agent evaluation and candidate generation; no trading engine | Python, PyYAML, optional LLM/MCP | MIT | Experiment-oriented / Medium | `learning/evolution` | Adapt: use candidate/benchmark concepts, isolate generated changes |
| AgenticTrading | LLM trading platform, orchestration, REST and dashboard | Inference, backtest, paper/live hooks; limited training | FastAPI, A2A/MCP, broker and LLM SDKs | OpenMDW-1.0 | Broad but coupled / High | `agents`, `audit`, `execution` | Adapt: mine contracts and audit patterns; review license before redistribution |
| airllm | Layer-wise large-model inference | Inference only; training-adjacent tooling | PyTorch, Transformers, PEFT, Accelerate | Apache-2.0 | RAM-saving but slow / Medium | `models/runtime` | Adapt: optional backend for oversized local models |
| assume | Electricity-market agent simulation | Training/simulation; no financial live path | Pyomo, PyPSA, SQLAlchemy, PyTorch | AGPL-3.0 | Domain-specific / High | Isolated research only | Reject: incompatible license and energy-market scope |
| backtrader | Event-driven strategy engine | Backtest and live broker adapters | pandas, optional TA-Lib, IB/Oanda | GPLv3+ | Mature, slower / Medium | `backtest/event_driven` | Adapt: optional engine, never core contract |
| evolver | JavaScript self-evolving agent CLI | Agent inference/evolution; no trading | Node 22, Bedrock, GEP/ATP | GPL-3.0-or-later | Separate runtime / High | `learning/evolution` | Adapt conceptually: keep Node sidecar only if benchmark proves value |
| FinGPT | Financial LLM and LoRA workflows | Training and inference for sentiment/finance text | PyTorch, Transformers, PEFT, datasets | MIT | GPU/model dependent / Medium | `models/financial_language` | Adapt: use datasets/model recipes behind AI provider |
| FinRL | Original RL trading framework | RL training, simulation, backtest, limited live | ElegantRL, SB3, Ray, Gym, Alpaca, CCXT | MIT | Research-heavy / High | `training/rl` | Replace: prefer newer FinRL-Trading contracts and own safety gates |
| FinRL-Meta | Data processors and Gym-style market environments | Training/simulation/backtest | pandas, Gym, provider SDKs | MIT | Useful environments / Medium | `data/environments` | Adapt: reuse environment ideas and provider normalization |
| FinRL-Trading | Weight-centric stock selection pipeline | Training, inference, backtest, paper/live | pandas, bt, Pydantic, Alpaca, Torch | Apache-2.0 | Focused / Medium | `strategy`, `backtest`, `brokers` | Adapt: strongest stock workflow source; wrap with ORION contracts |
| freqtrade | Production crypto trading bot and FreqAI | Training, backtest, paper/live | CCXT, pandas, TA-Lib, Optuna, ML/RL libs | GPLv3 | Mature but crypto-coupled / High | `adapters/crypto` | Adapt selectively: crypto connector patterns only; license review |
| hermes-agent | General agent runtime, tools, memory, scheduling | Inference and trajectory generation | Python, Pydantic, MCP/provider SDKs | MIT | General-purpose / Medium | `agents/runtime`, `memory` | Adapt: runtime and memory patterns, not application shell |
| homerun | Full-stack prediction-market strategy platform | Training/inference, backtest, shadow/paper/live | FastAPI, React, PostgreSQL, FAISS, venue APIs | AGPL | Domain-specific / High | `prediction_markets` | Adapt behind isolated service; do not copy AGPL code into core without review |
| intelligent-trading-bot | Offline/online ML crypto signal pipeline | Training, inference, backtest, live hooks | pandas, sklearn, LightGBM, TensorFlow, Binance | MIT | Practical parity pattern / Medium | `models/signals`, `adapters/crypto` | Adapt: reuse offline/online feature parity principles |
| jesse | Crypto strategy framework | Training, inference, backtest, paper/live | NumPy, pandas, Optuna, Ray, Rust indicators | MIT | Fast but crypto-specific / High | `backtest/crypto` | Adapt selectively: reference crypto testing and indicators |
| kimi-k3-in-c | Portable C99 inference runtime | Inference only; no training | C99, AVX2/FMA, OpenMP | Apache-2.0 | Checkpoint impractical / High | `models/runtime/edge` | Keep isolated: optional experimental backend, not default |
| Kronos | Financial candlestick foundation model | Fine-tuning and inference; no trading engine | PyTorch, Transformers-style code, HF, safetensors | MIT | GPU/model dependent / Medium | `models/forecasting/financial` | Adapt: first specialized forecasting candidate, benchmark against baseline |
| Lean | Professional multi-asset trading engine | Backtest, optimization, live brokerage | .NET/C#, plugins, Docker | Apache-2.0 | Powerful, separate runtime / Very high | `adapters/lean` | Adapt as optional sidecar after Python workflow is stable |
| neural_prophet | Incomplete checkout | Not verifiable | No manifest found | No license found | Not assessable | None | Reject: re-clone and license-review before consideration |
| ollama | Local model server and runtime | Local inference and embeddings through HTTP | Go, llama.cpp/MLX, SQLite | MIT | Production service / High | `models/providers/ollama` | Adapt: consume HTTP API; never import runtime internals |
| polymarket-kalshi-weather-bot | Weather/BTC prediction-market application | Inference, simulation/paper path | FastAPI, schedulers, venue/data/LLM APIs | MIT | Narrow vertical / Medium | `prediction_markets/weather` | Adapt: weather features and venue lessons only |
| Prediction-Markets-Trading-Bot-Toolkits | Rust prediction-market execution toolkit | Dry-run, paper, live execution | Tokio, Reqwest, WebSockets, Serde, Alloy | MIT | Low-latency, separate runtime / High | `adapters/prediction_markets` | Adapt as isolated Rust adapter; ORION risk gate remains authoritative |
| py_vollib | Option pricing, IV, Greeks | Analytics only | NumPy, pandas, SciPy | MIT | Focused and fast / Low | `analytics/options` | Adapt: direct dependency candidate for options analytics |
| qlib | Quant research/data/factors/models/backtest | Training, inference/serving, backtest | pandas, MLflow, LightGBM, CVXPY, Redis, MongoDB | MIT | Broad, dependency-heavy / High | `research/qlib` | Adapt: use data/factor/research components after dependency isolation |
| QuantLib | Derivatives, fixed-income and risk mathematics | Analytics only | C++, Boost/CMake | BSD-3-Clause | Mature native library / High | `analytics/quantlib` | Adapt: Python bindings or sidecar for pricing/risk |
| QuantMuse | Broad quant platform with Python/C++ services | Claimed training, inference, backtest, live, risk | pandas, NumPy, Binance, FastAPI, Redis, optional LLM | MIT | Maturity requires validation / High | Selected analytics only | Adapt cautiously: inspect implementation before reuse |
| Stock-Trading-Environment | Minimal Gym stock environment | Simulation/backtest only | Gym/OpenAI Gym | MIT | Simple / Low | `training/environments` | Replace: use richer FinRL-Meta/ORION simulator |
| Time-Series-Library | Forecasting/anomaly/classification model zoo | Training and inference | PyTorch, Transformers, JAX, Lightning, GluonTS | MIT | Broad benchmark suite / Medium | `models/forecasting/general` | Adapt: benchmark candidate models, no blind promotion |
| vectorbt | Vectorized research/backtesting and parameter sweeps | Backtest and optimization; no live execution | NumPy, pandas, SciPy, Numba, Plotly | Apache-2.0 + Commons Clause | Very fast / Medium | `backtest/vectorized` | Adapt with commercial-use review: useful research engine, license is not plain Apache |
| Vibe-Trading | Natural-language finance agent, MCP, analytics, backtests | Training hooks, inference, backtest, paper/live | LangGraph, FastAPI, DuckDB, pandas, CCXT, broker SDKs | MIT | Broad, application-coupled / High | `agents`, `research`, `analytics` | Keep/adapt: strongest broad source; select modules only |
| ORION | Canonical application package | Simulation, risk, registry, memory; no external integration yet | Python stdlib, pytest | Project-local, review before publication | Small and testable / Low | Core runtime | Keep: authoritative contracts and safety gates |

## Integration policy

1. ORION owns domain contracts, risk approval, decision audit, model promotion, and execution authorization.
2. Upstream code is imported only through tested adapters, subprocesses, or services. It never gets to bypass deterministic risk controls.
3. GPL/AGPL/OpenMDW/Commons Clause components require a distribution and deployment review before source integration. A compatible service boundary is preferred where appropriate.
4. Model quality is established by reproducible out-of-sample and regime-stratified benchmarks, not repository reputation.
5. The first local workflow uses Ollama when available, but remains functional without it through deterministic structured reasoning and local quantitative models.
6. Heavyweight or incomplete checkouts remain references until their artifacts, licenses, and runtime requirements are verified.
