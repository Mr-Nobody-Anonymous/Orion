# ORION — Capability Layer & Integration Architecture

This document specifies the end-to-end architecture of Orion's **External Capability Layer**. It governs how the 30 external repositories in `source_repositories/` are unified, routed, and exposed safely into Orion's core decision loop and Mission Control frontend.

---

## 1. High-Level Architectural Flow

```text
                               ┌─────────────────────────┐
                               │   USER / MISSION CTRL   │
                               │   FRONTEND / REST API   │
                               └────────────┬────────────┘
                                            │
                                            ▼
                               ┌─────────────────────────┐
                               │    CAPABILITY ROUTER    │
                               │ (Intent, Health, Route) │
                               └────────────┬────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
   ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
   │  FORECASTING COUNCIL  │   │   BACKTESTING ENGINE  │   │   OPTIONS & RISK HUB  │
   │  (Weights & Concord.) │   │  (Sweep / Event Mode) │   │ (Greeks / Factor Dec) │
   └──────────┬────────────┘   └───────────┬───────────┘   └───────────┬───────────┘
              │                            │                           │
   ┌──────────┴────────────┐   ┌───────────┴───────────┐   ┌───────────┴───────────┐
   │ Capability Interfaces │   │ Capability Interfaces │   │ Capability Interfaces │
   │ (ForecastingProvider) │   │   (BacktestProvider)  │   │   (OptionsProvider)   │
   └──────────┬────────────┘   └───────────┬───────────┘   └───────────┬───────────┘
              │                            │                           │
    ┌─────────┴─────────┐        ┌─────────┴─────────┐       ┌─────────┴─────────┐
    ▼                   ▼        ▼                   ▼       ▼                   ▼
┌──────────────┐ ┌────────────┐┌──────────────┐ ┌──────────┐┌──────────────┐ ┌────────────┐
│ KronosAdapter│ │OrionNative ││VectorBTAdapt │ │Backtrader││PyVollibAdapt │ │OrionNative │
│ (PyTorch/GPU)│ │ (Ensemble) ││(Vectorized)  │ │ (Event)  ││ (Greeks/IV)  │ │(BS Formula)│
└──────────────┘ └────────────┘└──────────────┘ └──────────┘└──────────────┘ └────────────┘
```

---

## 2. Core Principles

1. **Replaceable Engines, Governed Contracts**:
   - External projects (VectorBT, Kronos, QuantLib, py_vollib, Lean) are **replaceable calculation engines**.
   - Orion code **never directly couples** to third-party APIs. All components interact through pure Orion-owned interfaces in `src/orion/capabilities/`.
2. **Resilient Fallback Chains**:
   - Every capability provider guarantees a fallback hierarchy:
     $$\text{Primary External Engine} \xrightarrow{\text{fallback}} \text{Secondary Engine} \xrightarrow{\text{fallback}} \text{Orion Native Implementation}$$
   - If an optional library (e.g. `numba`, `py_vollib`, `quantlib`, `torch`) is missing or encounters a runtime failure, execution transparently switches to native Python algorithms.
3. **Multi-Engine Councils**:
   - For creative or stochastic tasks (like temporal forecasting and strategy generation), outputs are not evaluated in isolation.
   - The `ForecastCouncil` and `StrategyCouncil` run multiple providers in parallel, score historical performance weights, detect divergence, and compute ensemble concordance.
4. **Plane Separation & Governance Guard**:
   - Capability execution respects the immutable architecture plane hierarchy:
     $$\text{Intelligence Plane} \longrightarrow \text{Truth Plane} \longrightarrow \text{Control Plane} \longrightarrow \text{Capital}$$
   - External engines cannot directly execute trades or access capital; all proposed actions flow through the Control Plane Risk Gate.

---

## 3. Capability Modules & Provider Tree

| Capability Domain | Orion Interface | Primary Engine | Secondary Engine | Native Resilient Fallback |
| :--- | :--- | :--- | :--- | :--- |
| **Forecasting** | `ForecastingProvider` | `KronosForecasterAdapter` | `NeuralProphetAdapter` | `OrionEnsembleForecaster` |
| **Backtesting** | `BacktestProvider` | `VectorBTBacktestProvider` | `BacktraderProvider` / `Lean` | `OrionNativeBacktester` |
| **Options & Greeks** | `OptionsProvider` | `PyVollibOptionsProvider` | `QuantLibFixedIncomeProvider` | `OrionNativeBlackScholes` |
| **Fixed Income** | `FixedIncomeProvider` | `QuantLibFixedIncomeProvider` | `OrionCurveInterpolator` | `OrionNativeBondPricer` |
| **Prediction Markets** | `PredictionMarketProvider` | `HomerunSimulatorAdapter` | `PMToolkitAdapter` | `OrionKalshiEngine` |
| **RL Exploration** | `RLProvider` | `FinRLProvider` | `FinRLMetaEnvironmentAdapter` | `OrionPolicyLearner` |
| **Financial Sentiment**| `SentimentProvider` | `FinGPTProvider` | `OrionNLPTransformer` | `OrionRuleSentiment` |
| **Model Inference** | `InferenceProvider` | `OllamaInferenceProvider` | `AirLLMAdapter` | `OrionCloudFactory` |
| **Execution Routing** | `ExecutionProvider` | `AlpacaAdapter` / `Binance` | `LeanSidecarClient` | `OrionSimulatedExchange` |
| **Agent Memory** | `AgentMemoryProvider` | `HermesMemoryAdapter` | `OrionMistakeAnalyzer` | `OrionLayeredMemory` |

---

## 4. Observability & Health Monitoring

Every integration adapter implements the standard observability contract:
```python
@dataclass(frozen=True, slots=True)
class IntegrationHealth:
    name: str
    status: ProviderHealthStatus  # AVAILABLE | DEGRADED | UNAVAILABLE | ISOLATED
    version: str
    latency_ms: float
    last_error: str | None
    capabilities: tuple[str, ...]
    provenance: dict[str, Any]
```

All integration health snapshots are aggregated and exposed in real-time on the **Mission Control Terminal** via the `/api/integrations/health` endpoint.
