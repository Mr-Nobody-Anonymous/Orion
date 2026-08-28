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

## Point-in-time data layer (P0-1)

The `data/market_data/` package added in [TODO P0-1](../../TODO.md)
provides a point-in-time (PIT) data layer with:

* `PointInTimeDataset` — bundles `(observation_time, value,
  vendor_release_time)`; `as_of(t)` returns the latest value whose
  `vendor_release_time <= t`.
* `TimestampNormalizer`, `BadTickFilter`, `MissingDataPolicy`
  (`ffill`/`bfill`/`drop`).
* `(vendor, vendor_series_id, as_of, fetch_time, hash)`
  provenance per datapoint.
* `DataVersion` (schema + checksum) and a `LocalMarketDataStore`
  parquet/CSV back-end keyed by `(symbol, date)`.
* `MarketDataProvider` protocol: `fetch_ohlcv`, `fetch_fundamentals`,
  `fetch_corporate_actions`, `fetch_news`.

This is the data layer the agent kernel's
`fetch.price` / `fetch.fundamentals` capabilities read from.
See the [capability registry](../architecture/CAPABILITY_REGISTRY.md)
for the full input / output contract of each tool.

See also [data flow](../architecture/DATA_FLOW.md).