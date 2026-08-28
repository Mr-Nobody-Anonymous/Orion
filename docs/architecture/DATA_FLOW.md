# Data Flow

ORION ingests validated market/quote data, builds scoped observations, and
propagates them through state, memory, forecasting, decision, risk, and
learning. Every step tagged with source/confidence/status.

Modules: `data/` (`contracts.py`, `validation.py`); `world_model/state.py`;
`memory/`; `infrastructure/provenance.py`, `event_bus.py`.

## Flow

```
  Market data / news / fundamentals
        │  data/contracts (Asset, MarketQuote, OHLCV, NewsEvent, FundamentalData ...)
        ▼
┌──────────────────────────────┐
│ DataQualityValidator         │  data/validation.py
│ (rejects invalid/stale)      │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ FinancialWorldModel state    │  world_model/state.py
│ MarketState (regime, vol)    │  StateValue{value,status,confidence,source}
│ PortfolioState, ModelState...│
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ LayeredMemory.remember(...)  │  memory/ (7 layers)
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Forecast (council/forecaster)│  prediction/
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Decision + Risk              │  brain/decision.py, trading/risk.py
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Execution (SimulatedBroker)  │  trading/execution.py → Fill
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Outcome → self-improvement → │  learning/, memory/
│ experience memory            │
└──────────────────────────────┘
```

## Contracts

`data/contracts.py` provides the canonical typed models:

- **Market data**: `MarketData`, `OHLCV`, `Quote`, `MarketQuote`, `Tick`,
  `OrderBook`, `OrderBookLevel`, `Order`, `OrderRequest`, `ExecutionReport`,
  `Trade`, `Position`, `Portfolio`.
- **Context**: `NewsEvent`, `EconomicEvent`, `FundamentalData`,
  `OptionContract`, `OptionChain`.
- **Symbols/prediction**: `Asset`, `AssetClass`, `Prediction`, `Signal`,
  `Strategy`, `TrainingExample`, `Experience`, `ModelArtifact`.
- **Decision**: `Action`, `Decision`, `RiskAssessment`, `RiskDecision`,
  `TradeProposal`, `ExecutionMode`.

## Validation

`DataQualityValidator` (data/validation.py) is the gate before data enters
state; a low-quality/stale input never reaches decision logic.

## State & provenance

- Every `StateValue` records `value/status/source/confidence/observed_at`, so
  an uncertain number is never presented as fact.
- `EventBus` (`infrastructure/event_bus.py`) carries structured events
  (`RiskAssessment`, `OrderFilled`, ...) for reactive coordination.
- `ProvenanceStore` (`infrastructure/provenance.py`) records immutable
  provenance for research claims and model artifacts.