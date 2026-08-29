# Trading

Trading layer: strategies, portfolio construction, execution, brokers, risk
(the gate), and asset-class specialists.

Modules: `trading/` — `execution.py`, `risk.py`, `strategies/catalog.py`,
`portfolio/allocator.py`, `portfolio/constructor.py`, `brokers/`; `markets/`
(asset-class specialists).

## Capabilities

| Capability | Status | Entry points |
|---|---|---|
| Simulated execution | IMPLEMENTED | `SimulatedBroker`, `BrokerAdapter` protocol |
| Portfolio allocation | IMPLEMENTED | equal-weight, inverse-volatility, fractional-Kelly (`allocator.py`) |
| Portfolio construction | IMPLEMENTED | `constructor.py` |
| Strategy catalog | IMPLEMENTED | `strategies/catalog.py` |
| Risk gate | IMPLEMENTED | `RiskEngine`, `RiskLimits` |
| Asset-class specialists | IMPLEMENTED | `markets/*` specialists (equity, etf, crypto, futures, fx, commodity, fixed income, options, prediction markets) |
| Demo broker adapters (Alpaca, Binance, Kraken, Coinbase, OANDA, IBKR) | IMPLEMENTED | `integrations/brokers/*` — testnet/paper endpoints by default, env-discovered |
| Venue routing + kill switch | IMPLEMENTED | `integrations/brokers/registry.py` (`BrokerRegistry`, `KillSwitch`) |
| Live broker execution | BLOCKED by default | requires `execution_mode="live"` AND `live_trading_enabled=True` AND per-venue `*_MODE=live`; kill switch enforced |

## Design notes

- **Risk above execution.** `ExecutiveBrain` consults `RiskEngine` before any
  `place_order`; live paths are disabled by construction.
- **Asset-class agnostic core.** Common risk/portfolio/decision/memory are
  shared; `markets/specialist` contributes asset-specific parameters without
  overriding the risk engine.
- **Paper execution only** — live trading requires an explicit, deliberate
  configuration change and a credential-isolated adapter.
- **Exposure is market-value based.** `trading/exposure.py::compute_exposure`
  returns `sum(|qty × price|) / equity` — the dimensionally correct ratio.
  The earlier `sum(abs(quantity)) / equity` form (shares vs currency) was
  fixed in [PHASE_31C_REVIEW_RESPONSE.md §1.2](../architecture/PHASE_31C_REVIEW_RESPONSE.md).
- **Factor-neutral baseline.** A buy-and-hold, momentum, mean-reversion,
  factor-neutral, and random-null strategy are all available as comparison
  baselines via `src/orion/evaluation/baselines.py`. See
  [PHASE_31C_REVIEW_RESPONSE.md §3](../architecture/PHASE_31C_REVIEW_RESPONSE.md).

See also [risk](../risk/README.md) and
[risk architecture](../architecture/RISK_ARCHITECTURE.md).