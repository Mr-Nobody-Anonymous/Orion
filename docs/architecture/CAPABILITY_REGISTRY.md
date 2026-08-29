# ORION Capability Registry

This registry records the audit of preserved repositories and the executable ORION destination for each useful capability. `INTEGRATED` means ORION runs the implementation. `WORKER` means the upstream repository is preserved and may only run from an isolated, configured environment. `REFERENCE` means it informs design but ORION does not import or invoke it. `BLOCKED` identifies a specific missing condition.

| Repository | Audited path | Capability | Status | ORION destination | Dependencies / license | Tests / integration method |
|---|---|---|---|---|---|---|
| ORION | `src/orion/world_model/state.py` | Explicit world, market, portfolio, research, model, risk, decision, learning state with confidence | INTEGRATED | `orion.world_model` | stdlib / ORION | `tests/world_model/test_state.py` |
| ORION | `src/orion/prediction/ensembles/model_council.py` | Context-dependent weighted model council with disagreement tracking and outlier detection | INTEGRATED | `orion.prediction.ensembles` | stdlib / ORION | `tests/prediction/test_model_council.py` |
| ORION | `src/orion/prediction/statistical/descriptive.py` | Dependency-free statistics: percentiles, skewness, kurtosis, Jarque-Bera normality, correlation, rolling stats, drawdown, confidence intervals | INTEGRATED | `orion.prediction.statistical` | stdlib / ORION | `tests/prediction/test_statistical_and_portfolio_and_memory.py` |
| ORION | `src/orion/trading/portfolio/allocator.py` | Equal-weight, inverse-volatility, fractional-Kelly allocation with cap/floor constraints and lot-rounded position sizing | INTEGRATED | `orion.trading.portfolio` | stdlib / ORION | `tests/prediction/test_statistical_and_portfolio_and_memory.py` |
| ORION | `src/orion/memory/working.py` | Bounded salience-based working memory with compression of evicted items into episodic memory | INTEGRATED | `orion.memory` | stdlib / ORION | `tests/prediction/test_statistical_and_portfolio_and_memory.py` |
| ORION | `src/orion/memory/layered.py` | Working, episodic, semantic, procedural, market, research, trading memory and bounded compression | INTEGRATED | `orion.memory` | stdlib / ORION | `tests/memory/test_layered_memory.py` |
| ORION | `src/orion/research/discovery.py` | Public scholarly metadata discovery and provenance-ready reports | INTEGRATED | `orion.research` | OpenAlex network access / ORION | `tests/research/test_discovery.py`; reports `BLOCKED` on outage |
| ORION | `src/orion/evolution/engine.py` | Deterministic multi-objective candidate evolution | EXPERIMENTAL | `orion.evolution` | stdlib / ORION | `tests/evolution/test_engine.py` |
| ORION | `src/orion/simulation/market.py` | Seeded historical-return bootstrap market simulation | INTEGRATED | `orion.simulation` | stdlib / ORION | CLI and deterministic unit coverage |
| ORION | `src/orion/backtesting/evaluation.py` | Performance metrics and walk-forward evaluation | INTEGRATED | `orion.backtesting` | stdlib / ORION | `tests/backtesting/test_evaluation.py` |
| ORION | `src/orion/benchmarking/suite.py` | Contamination-safe walk-forward model and strategy comparison with deterministic scoring and head-to-head directional comparison | INTEGRATED | `orion.benchmarking` | stdlib / ORION | `tests/benchmarks/test_suite.py`; exercised by `python -m orion benchmark` |
| ORION | `src/orion/infrastructure/governance.py` | Candidate promotion gate requiring explicit approval | INTEGRATED | `orion.infrastructure` | stdlib / ORION | exercised by `evaluate` |
| ORION | `src/orion/coding/verification.py` | Static rejection of unsafe generated-code constructs | INTEGRATED | `orion.coding` | stdlib / ORION | static gate; sandbox execution remains BLOCKED |
| `prediction/qlib` | `qlib/workflow`, `qlib/contrib` | Quant research workflows, datasets, model evaluation | WORKER | future `workers/qlib` | Python ML stack / MIT | Requires isolated environment and dataset configuration |
| `prediction/Kronos` | `model`, `finetune` | Time-series foundation-model inference and fine tuning | WORKER | future `workers/kronos` | PyTorch/model weights / MIT | Blocked until compatible checkpoint is configured |
| `prediction/Time-Series-Library` | model and experiment modules | Deep forecasting model implementations | WORKER | future `workers/time_series` | PyTorch / MIT | Preserve as benchmark worker candidate |
| `trading/backtrader` | `backtrader`, `tests` | Event-driven backtesting and broker abstractions | REFERENCE | `orion.backtesting` | Python / GPL | Native lightweight engine is used to avoid license coupling |
| `trading/vectorbt` | `vectorbt`, `tests`, `benchmarks` | Vectorized strategy research and portfolio analytics | REFERENCE | `orion.backtesting` | NumPy stack / Commons Clause | Cannot be bundled without license review |
| `trading/FinRL` | `finrl`, `unit_tests` | Reinforcement-learning trading environments | WORKER | future `workers/finrl` | Gym/RL dependencies / MIT | Requires reproducible environment and leakage audit |
| `trading/FinRL-Meta` | data and environment modules | Market-data engineering and RL market environments | WORKER | future `workers/finrl_meta` | external data / MIT | Data licensing and credentials required |
| `trading/FinRL-Trading` | training and strategy modules | FinRL application workflows | REFERENCE | `orion.learning` | RL dependencies / Apache-2.0 | Consolidate only proven methods after controlled benchmark |
| `trading/freqtrade` | `freqtrade` | Crypto execution, exchange adapters, strategy testing | WORKER | future `workers/freqtrade` | exchange credentials / GPL | Paper-only worker; live mode remains disabled |
| `trading/jesse` | package modules | Crypto strategy, exchange, optimization components | REFERENCE | `orion.trading` | Python services / MIT | Evaluate under isolated worker before any use |
| `trading/Lean` | `Algorithm`, `Brokerages`, `Tests` | Multi-asset research, algorithms, broker backtesting | WORKER | future `workers/lean` | .NET + data / Apache-2.0 | Requires Lean runtime and data subscription configuration |
| `trading/Stock-Trading-Environment` | Python environment modules | Simple stock market RL environment | REFERENCE | `orion.simulation` | Python / MIT | Superseded by controlled ORION simulation baseline |
| `mathematics/py_vollib` | `py_vollib`, `tests` | Implied volatility and options pricing | WORKER | future `workers/options_math` | SciPy stack / MIT | Candidate only after numerical validation |
| `mathematics/QuantLib` | source tree | Quantitative finance pricing and risk analytics | WORKER | future `workers/quantlib` | C++ bindings / QuantLib license | Requires compiled binding and numeric regression suite |
| `llm/FinGPT` | `fingpt`, `tests` | Financial language models and instruction workflows | WORKER | future `workers/fingpt` | model weights/GPU / MIT | Requires model card, weights and evaluation dataset |
| `agents/AgenticTrading` | `orchestration`, `dashboard` | Agent orchestration patterns | REFERENCE | `orion.orchestration` | OpenMDW-1.0 | License review required before code reuse |
| `agents/hermes-agent` | Python agent modules | Agent/tool-use infrastructure | REFERENCE | `orion.intelligence` | Python / MIT | Root duplicate retained as preservation checkout |
| `infrastructure/airllm` | Python modules | Local LLM inference support | WORKER | `orion.models.local` | model/GPU / Apache-2.0 | Hardware and compatible model required |
| `infrastructure/ollama` | upstream source | Local model serving | ADAPTER | `orion.models.local.ollama` | local service / MIT | ORION calls configured local service only |
| `agents/QuantMuse` | Python modules | Finance-oriented agent patterns | REFERENCE | `orion.intelligence` | Python / MIT | Assess methods with reproducible tests first |
| `agents/Vibe-Trading` | Python modules | Trading agents, prompts and experiments | REFERENCE | `orion.research` | Python / MIT | No production import |
| `trading/intelligent-trading-bot` | Python modules | Trading bot examples | REFERENCE | `orion.trading` | Python / MIT | No production import |
| `infrastructure/kimi-k3-in-c` | C/Python files | Local inference experimentation | BLOCKED | `orion.models.local` | toolchain/model assets / license review | No verified runtime configuration |
| `markets/homerun` | source and tests | Market data / trading application concepts | REFERENCE | `orion.markets` | AGPL | Preserve only; code reuse requires AGPL decision |
| `markets/polymarket-kalshi-weather-bot` | project files | Prediction-market automation patterns | BLOCKED | future `workers/prediction_markets` | credentials, no root license | Licensing and venue policy review required |
| `markets/Prediction-Markets-Trading-Bot-Toolkits` | project files | Prediction-market toolkits | REFERENCE | `orion.markets` | MIT | No production execution without venue adapter controls |
| `agents/a-evolve` | `agent_evolve`, `tests` | Agent evolution and experiment artifacts | REFERENCE | `orion.evolution` | no root license | License clarification required before reuse |
| `research/assume` | `assume`, `tests` | Energy-market simulation patterns | REFERENCE | `orion.simulation` | AGPL | Preserve only; isolated comparison possible |
| `agents/evolver` | project files | Evolution concepts | REFERENCE | `orion.evolution` | GPL | Native ORION implementation avoids coupling |
| `root_checkouts/*` | preserved checkout roots | Historical duplicate checkouts for provenance | REFERENCE | `source_repositories/root_checkouts` | inherited / mixed | Never imported by ORION |

## Technical blockers

- Cloud inference and distributed training require user-configured providers, credentials, model cards, budget controls, and per-provider evaluation. ORION intentionally has no implicit cloud calls.
- Live execution is deliberately disabled. It cannot be enabled by research, learning, or generated code.
- Upstream GPL/AGPL/Commons-Clause code is retained for audit and worker/reference analysis, not copied into the canonical package.
- Generated code passes static verification only. A dedicated process/container sandbox is required before execution can be marked implemented.

## From catalogue to callable (Phase 31D / 31E)

The table above is the audit. The **runtime** that turns
this catalogue into a callable surface is the
`CapabilityRegistry` and the `CapabilityExecutor`. The
registry is the static type catalogue of every tool
ORION knows about; the executor is the function that
checks permission, checks risk, runs the registered
implementation, and returns a structured
`CapabilityResult`. The persistent agent kernel
([`src/orion/agent/kernel.py`](../../src/orion/agent/kernel.py))
is the loop that calls the executor and writes the
result back to the agent's self-model.

* Registry module: `src/orion/intelligence/capability_registry.py`
  — 23 tools (14 internal, 9 reference upstream), 22 tests.
* Executor module: `src/orion/agent/executor.py` — permission
  check + risk gate + honest "no implementation" result for
  advertised-but-unwired tools.
* Kernel module: `src/orion/agent/kernel.py` — closed loop.
* Audit: [PHASE_31D_AUDIT.md](PHASE_31D_AUDIT.md) for the
  registry; [PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md) for the kernel.
