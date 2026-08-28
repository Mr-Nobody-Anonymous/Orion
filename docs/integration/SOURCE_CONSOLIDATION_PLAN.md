# ORION Source Consolidation Plan

**Status:** Active implementation plan  
**Principle:** consolidate useful algorithms by capability; preserve legacy repositories for provenance and comparison.

| Source | Component identified from source | ORION destination | Action | Status |
| --- | --- | --- | --- | --- |
| Ollama | Local model HTTP runtime | `orion/models/local`, `orion/intelligence/llm` | Port provider contract; consume service API | In progress |
| FinGPT | Financial NLP, sentiment and LoRA recipes | `orion/intelligence/financial_reasoning`, `orion/intelligence/sentiment` | Adapt selected model/data workflows | Planned |
| AgenticTrading | Agent orchestration, decision/audit workflows | `orion/brain`, `orion/intelligence/agents` | Port patterns after license review | Planned |
| Vibe-Trading | Finance tools, MCP workflow, analytics | `orion/intelligence/research`, `orion/trading` | Selective port, capability-first | Planned |
| intelligent-trading-bot | Offline/online feature parity | `orion/learning`, `orion/trading/strategies` | Adapt tested principles | Planned |
| Kronos | Financial candlestick forecasting model | `orion/prediction/time_series` | Port model only after dependency and weight validation | Planned |
| Time-Series-Library | Forecasting architectures and experiments | `orion/prediction/time_series` | Port benchmark candidates | Planned |
| QLib | Data providers, factors, model research, backtesting | `orion/data`, `orion/prediction`, `orion/backtesting` | Selective port behind canonical schemas | Planned |
| NeuralProphet | Forecasting package | `orion/prediction/forecasting` | Re-clone and license-review first | Blocked: incomplete checkout |
| FinRL | RL algorithms and environments | `orion/learning/reinforcement_learning` | Port selected algorithms; replace legacy framework shell | Planned |
| FinRL-Meta | Market data processors and environments | `orion/data`, `orion/learning` | Adapt data/environment components | Planned |
| FinRL-Trading | Weight-centric strategy pipeline | `orion/trading/strategies`, `orion/backtesting` | Port strategy/data separation | Planned |
| vectorbt | Vectorized portfolio research | `orion/backtesting`, `orion/trading/strategies` | Consolidate compatible algorithms; review Commons Clause | Baseline implemented independently |
| backtrader | Event-driven simulation and broker patterns | `orion/backtesting/execution_simulation` | Port fill/event concepts selectively | Planned |
| Lean | Multi-asset engine capabilities | `orion/backtesting`, `orion/trading/execution` | Isolated service or selective port | Planned |
| QuantLib | Pricing and fixed-income mathematics | `orion/mathematics/pricing`, `orion/mathematics/derivatives` | Use bindings or port formulas with BSD provenance | Planned |
| py_vollib | Black/BS option pricing, IV and Greeks | `orion/mathematics/derivatives` | Port/test needed calculations | Planned |
| freqtrade | Crypto venue and FreqAI patterns | `orion/markets/crypto`, `orion/trading` | Isolate GPL code; port concepts only | Planned |
| jesse | Crypto strategy/backtest patterns | `orion/markets/crypto`, `orion/backtesting` | Selective port after review | Planned |
| Prediction-Markets-Trading-Bot-Toolkits | Rust venue execution | `orion/markets/prediction_markets` | Keep as isolated worker with ORION risk boundary | Planned |
| homerun | Prediction-market shadow fills and strategy workflows | `orion/markets/prediction_markets` | Adapt architecture; AGPL isolation required | Planned |
| polymarket-kalshi-weather-bot | Weather and prediction-market features | `orion/markets/prediction_markets` | Port domain logic selectively | Planned |
| a-evolve | Benchmark-driven candidate evolution | `orion/learning/self_improvement` | Adapt evaluation loop | Planned |
| evolver | Agent evolution concepts | `orion/learning/self_improvement` | Conceptual reference; GPL/Node isolation | Planned |
| hermes-agent | Skills, memory and tool runtime | `orion/intelligence/agents`, `orion/memory` | Port schemas/patterns after review | Planned |
| airllm | Large-model memory-saving inference | `orion/models/local`, `orion/models/routing` | Optional backend only if benchmark wins | Planned |
| kimi-k3-in-c | C inference runtime | `orion/models/local` | Keep isolated; checkpoint impractical | Planned |
| assume | Electricity-market simulation | None in financial core | Keep separate due to AGPL and domain | Rejected |
| Stock-Trading-Environment | Minimal Gym stock environment | None; superseded by ORION simulator | Replace with canonical environment | Rejected |
| QuantMuse | Mixed quant analytics and agents | `orion/research` candidates | Inspect and port only validated pieces | Planned |

## Consolidation gates

Every port must have: source file and commit recorded, license compatibility checked, canonical ORION data types, unit tests, workflow integration test, and benchmark evidence. No copied component may bypass the deterministic risk engine or model approval gate.
