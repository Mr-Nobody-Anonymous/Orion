# Data

The asset-class-agnostic data layer: canonical contracts, validation gate, and
asset-class specialists. All downstream computation consumes validated, typed
data.

Modules: `data/` — `contracts.py`, `validation.py`; `markets/` (specialists).

## Contracts (`data/contracts.py`)

- **Market**: `MarketData`, `OHLCV`, `Quote`, `MarketQuote`, `Tick`, `OrderBook`,
  `OrderBookLevel`, `Trade`.
- **Orders/execution**: `Order`, `OrderRequest`, `ExecutionReport`, `Position`,
  `Portfolio`, `ExecutionMode`, `Action`.
- **Context**: `NewsEvent`, `EconomicEvent`, `FundamentalData`, `OptionContract`,
  `OptionChain`.
- **Intelligence**: `Asset`, `AssetClass`, `Prediction`, `Signal`, `Strategy`,
  `ModelArtifact`, `TrainingExample`, `Experience`.
- **Decision**: `Decision`, `RiskAssessment`, `RiskDecision`, `TradeProposal`.

## Validation

`DataQualityValidator` (`data/validation.py`) rejects invalid or stale data
before it enters world state. Data quality is tracked in `MarketState.data_quality`
with explicit `KnowledgeStatus`.

## Specialists

`markets/specialist.py` (`specialist_for`, `default_specialist`) returns
asset-class-specific parameters and constraints for equities, ETFs, crypto,
futures, FX, commodities, fixed income, options, and prediction markets. These
specialists contribute parameters only — they never override the risk engine.

## Market data sources

Historical price feeds for the CLI are supplied as explicit inputs
(`--prices`). Broader market/fundamental/news ingestion to databases is
**BLOCKED** until a user-configured data provider is present (see
[capability registry](../architecture/CAPABILITY_REGISTRY.md)). Research
metadata is ingested via the public OpenAlex API in `research/`.

See also [data flow](../architecture/DATA_FLOW.md).