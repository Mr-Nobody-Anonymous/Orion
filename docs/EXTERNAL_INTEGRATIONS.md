# ORION — External Repository Integration Matrix

This document is the authoritative audit and integration specification for all 30 repositories preserved under `source_repositories/`.

Each repository is cataloged across 16 formal attributes to ensure zero uncontrolled runtime imports, zero license contamination, and predictable multi-tier fallback behavior.

---

## 1. Provenance & Integration Matrix (All 30 Repositories)

| # | Repository | Category | Current Mode | Actual Current Usage | Proposed Mode | Capabilities Provided | Dependencies | License | Runtime Reqs | GPU Reqs | Isolation Reqs | Current Orion Replacement | Missing Adapter | Native Fallback | Tests Required | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **AgenticTrading** | `agents` | `reference` | Architecture blueprint | `adapter` | Multi-agent coordination, tool-calling UX | Python $\ge$3.9, LangChain | MIT | Python stdlib / process | None | In-process adapter | `src/orion/agent/` | `AgenticTradingAdapter` | `OrionNativeAgent` | Unit, health | ACTIVE |
| 2 | **QuantMuse** | `agents` | `reference` | Alpha research reference | `adapter` | Factor discovery, financial reasoning | Python $\ge$3.10 | Apache-2.0 | Python runtime | Optional (LLM) | In-process adapter | `src/orion/research/` | `QuantMuseAdapter` | `OrionNativeResearch` | Unit, health | ACTIVE |
| 3 | **Vibe-Trading** | `agents` | `reference` | Tool dispatch reference | `adapter` | MCP tool protocol, agent interaction | Python $\ge$3.10 | MIT | In-process | None | In-process adapter | `src/orion/intelligence/tool_registry.py` | `VibeTradingAdapter` | `OrionToolRegistry` | Unit, health | ACTIVE |
| 4 | **a-evolve** | `agents` | `reference` | Mutation mechanics reference | `adapter` | Benchmark-driven agent/strategy evolution | Python $\ge$3.10 | MIT | Python runtime | Optional | In-process adapter | `src/orion/evolution/` | `AEvolveAdapter` | `OrionGeneticEvolver` | Unit, health | ACTIVE |
| 5 | **evolver** | `agents` | `conceptual` | Lineage design reference | `conceptual` | Skill genome, strategy lineage tracking | Node.js | MIT | Conceptual / Node | None | Sandboxed / schema only | `src/orion/strategies/registry.py` | `EvolverSchemaAdapter` | `OrionStrategyRegistry` | Schema, health | ACTIVE |
| 6 | **hermes-agent** | `agents` | `reference` | Memory loop reference | `adapter` | Multi-layer episodic memory, reflection | Python $\ge$3.10 | MIT | In-process | None | In-process adapter | `src/orion/memory/` | `HermesMemoryAdapter` | `OrionLayeredMemory` | Unit, health | ACTIVE |
| 7 | **ollama** | `infrastructure` | `dependency` | Local model serving | `dependency` | High-throughput local LLM serving | Ollama binary, HTTP API | MIT | Local daemon (11434) | Recommended | Subprocess / HTTP | `src/orion/models/cloud/` | `OllamaInferenceProvider` | `OrionCloudFactory` | API health, ping | ACTIVE |
| 8 | **airllm** | `infrastructure` | `reference` | Low-VRAM design reference | `optional` | Layer-by-layer sequential CPU/GPU inference | PyTorch, Transformers | Apache-2.0 | Python runtime | Optional (Low VRAM) | Memory isolation | `src/orion/infrastructure/hardware_router.py` | `AirLLMAdapter` | `OrionStandardInference` | Unit, fallback | ACTIVE |
| 9 | **kimi-k3-in-c** | `infrastructure` | `excluded` | C-inference provenance | `isolated` | Pure C low-level inference engine | C11 compiler, 1.56TB weights | Apache-2.0 | Native binary | High VRAM / RAM | Complete isolation | `src/orion/models/` | `KimiIsolatedProvider` | `OrionNativeModel` | Config check | ISOLATED |
| 10 | **FinGPT** | `llm` | `optional` | Sentiment model reference | `optional` | Financial NLP, sentiment, entity impact | PyTorch, HuggingFace | MIT | Python runtime | Optional | In-process provider | `src/orion/intelligence/sentiment_reasoning_ml.py` | `FinGPTProvider` | `OrionRuleSentiment` | Unit, health | ACTIVE |
| 11 | **Prediction-Markets-Trading-Bot-Toolkits** | `markets` | `reference` | Venue schema reference | `adapter` | Multi-PM connectivity (Polymarket / Kalshi) | Rust / Python | MIT | Python / Subprocess | None | In-process adapter | `src/orion/markets/prediction_markets/` | `PMToolkitAdapter` | `OrionKalshiEngine` | Unit, health | ACTIVE |
| 12 | **homerun** | `markets` | `reference` | Fill simulator reference | `adapter` | Prediction market fill simulation, order books | Python, Postgres | MIT | Python runtime | None | In-process adapter | `src/orion/markets/prediction_markets/` | `HomerunSimulatorAdapter` | `OrionOrderMatching` | Unit, health | ACTIVE |
| 13 | **polymarket-kalshi-weather-bot** | `markets` | `reference` | Causal arbitrage reference | `adapter` | Event arbitrage, econometric edge detection | Python $\ge$3.9 | MIT | Python runtime | None | In-process adapter | `src/orion/intelligence/causal/` | `WeatherArbitrageAdapter` | `OrionCausalAIEngine` | Unit, health | ACTIVE |
| 14 | **QuantLib** | `mathematics` | `dependency` | Term structure math reference | `dependency` | Fixed income, yield curves, bond pricing | QuantLib C++/Python | BSD-3-Clause | C extension | None | In-process provider | `src/orion/markets/fixed_income/pricing.py` | `QuantLibFixedIncomeProvider` | `OrionNativeBondPricer` | Unit, fallback | ACTIVE |
| 15 | **py_vollib** | `mathematics` | `dependency` | Black-Scholes math reference | `dependency` | Options pricing, Greeks (Δ, Γ, ν, θ), IV | py_vollib, Numba | MIT | Python runtime | None | In-process provider | `src/orion/markets/options/analytics.py` | `PyVollibOptionsProvider` | `OrionNativeBlackScholes` | Unit, fallback | ACTIVE |
| 16 | **Kronos** | `prediction` | `adapter` | Deep forecasting candidate | `adapter` | K-line foundation temporal forecasting | PyTorch, NumPy | MIT | Python runtime | Recommended | In-process adapter | `src/orion/models/sklearn_forecaster.py` | `KronosForecasterAdapter` | `OrionEnsembleForecaster` | Unit, fallback | ACTIVE |
| 17 | **Time-Series-Library** | `prediction` | `benchmark` | SOTA benchmark suite | `benchmark` | Benchmark evaluation (Informer, PatchTST, DLinear) | PyTorch, SciPy | MIT | Python runtime | Recommended | Evaluation lab | `src/orion/evaluation/lab.py` | `TSLibBenchmarkAdapter` | `OrionEvaluationLab` | Unit, health | ACTIVE |
| 18 | **neural_prophet** | `prediction` | `reference` | Decomposition reference | `adapter` | Interpretable trend & seasonality decomposition | PyTorch, Pandas | Apache-2.0 | Python runtime | None | In-process provider | `src/orion/models/volatility.py` | `NeuralProphetAdapter` | `OrionTrendDecomposition` | Unit, fallback | ACTIVE |
| 19 | **qlib** | `prediction` | `dependency` | Alpha factor reference | `dependency` | Factor engineering (Alpha158/360), datasets | Qlib, LightGBM | MIT | Python runtime | None | In-process provider | `src/orion/data/features/` | `QlibFactorProvider` | `OrionFactorPipeline` | Unit, fallback | ACTIVE |
| 20 | **vectorbt** | `trading` | `adapter` | Fast backtesting reference | `adapter` | High-speed vectorized parameter sweeps | NumPy, Numba, Pandas | Apache-2.0 | Python runtime | None | In-process provider | `src/orion/backtesting/` | `VectorBTBacktestProvider` | `OrionNativeBacktester` | Unit, fallback | ACTIVE |
| 21 | **backtrader** | `trading` | `fallback` | Event backtesting reference | `fallback` | Bar-by-bar event-driven backtesting | backtrader, Python | GPL-3.0 (Clean-room API) | Python runtime | None | Process / API boundary | `src/orion/evaluation/baselines_strategies.py` | `BacktraderProvider` | `OrionEventBacktester` | Unit, fallback | ACTIVE |
| 22 | **freqtrade** | `trading` | `reference` | Crypto bot reference | `adapter` | Crypto strategy execution, trailing stop limits | Python $\ge$3.10 | GPL-3.0 (API isolated) | Python runtime | None | Process / API boundary | `src/orion/trading/strategies.py` | `FreqtradeStrategyAdapter` | `OrionCryptoExecution` | Unit, health | ACTIVE |
| 23 | **jesse** | `trading` | `reference` | Crypto risk reference | `adapter` | Crypto position sizing, liquidation modeling | Python $\ge$3.9 | MIT | Python runtime | None | In-process adapter | `src/orion/trading/exposure.py` | `JesseRiskAdapter` | `OrionExposureGuard` | Unit, health | ACTIVE |
| 24 | **Lean** | `trading` | `sidecar` | Institutional execution ref | `sidecar` | Multi-asset institutional simulation / live broker | .NET 8 / C# | Apache-2.0 | External service | None | Isolated sidecar (HTTP/gRPC) | `src/orion/integrations/brokers/` | `LeanSidecarClient` | `OrionSimulatedBroker` | Sidecar health | ACTIVE |
| 25 | **FinRL** | `trading` | `research` | DRL agent reference | `research` | Deep RL policy benchmarks (PPO, A2C, DDPG) | PyTorch, Stable-Baselines3 | MIT | Python runtime | Recommended | RL Lab isolation | `src/orion/learning/learner.py` | `FinRLProvider` | `OrionPolicyLearner` | Unit, health | ACTIVE |
| 26 | **FinRL-Meta** | `trading` | `reference` | Market environment ref | `adapter` | Market environment generator for Gym/Gymnasium | Gymnasium, Pandas | MIT | Python runtime | None | In-process adapter | `src/orion/simulation/exchange.py` | `FinRLMetaEnvironmentAdapter` | `OrionMarketEnvironment` | Unit, health | ACTIVE |
| 27 | **FinRL-Trading** | `trading` | `deprecated` | Historical stock pipeline | `deprecated` | Stock-selection pipeline (superseded by FinRL-Meta) | Python | MIT | None | None | Historical provenance | `src/orion/simulation/` | `FinRLTradingProvenance` | `FinRL-Meta` | Metadata | DEPRECATED |
| 28 | **intelligent-trading-bot** | `trading` | `reference` | Drift detection reference | `adapter` | Online continual learning & drift detection | Python $\ge$3.9 | MIT | Python runtime | None | In-process adapter | `src/orion/learning/online.py` | `OnlineLearnerAdapter` | `OnlineContinualLearner` | Unit, health | ACTIVE |
| 29 | **Stock-Trading-Environment** | `experimental` | `deprecated` | Legacy 5-file Gym stub | `deprecated` | Basic Gym trading environment stub | Gym | MIT | None | None | Historical provenance | `src/orion/simulation/exchange.py` | `StockEnvProvenance` | `FinRL-Meta` | Metadata | DEPRECATED |
| 30 | **assume** | `research` | `isolated` | Energy market simulation | `isolated` | Agent-based electricity and grid power modeling | Python, Mesa | MIT | Python runtime | None | Isolated research lab | `src/orion/simulation/` | `AssumePowerMarketAdapter` | `OrionMarketSimulator` | Schema, health | ISOLATED |

---

## 2. Integration Modes Summary

```text
Total Curated Repositories: 30
├── Active In-Process Adapters (adapter):     13
├── Direct Dependencies (dependency):         4
├── Isolated Sidecars (sidecar):              1
├── Pluggable Providers (optional / research): 3
├── Benchmark / Evaluation (benchmark):       1
├── Resilient Fallbacks (fallback):           1
├── Conceptual / Schema (conceptual):         1
├── Isolated Research Labs (isolated):        2
└── Historical Provenance (deprecated):       4
```

---

## 3. Fallback Hierarchy Guarantee

Every active capability adheres to the strict 3-tier fallback chain:

$$\text{Primary Engine (Adapter/Sidecar)} \xrightarrow{\text{on failure}} \text{Secondary Engine} \xrightarrow{\text{on failure}} \text{Orion Native Resilient Implementation}$$

Orion will **never** raise an unhandled exception or crash due to an uninstalled or failing external library.
