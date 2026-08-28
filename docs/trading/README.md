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
| Live broker (Alpaca) | BLOCKED | `AlpacaAdapter` raises `LiveTradingDisabledError` |

## Design notes

- **Risk above execution.** `ExecutiveBrain` consults `RiskEngine` before any
  `place_order`; live paths are disabled by construction.
- **Asset-class agnostic core.** Common risk/portfolio/decision/memory are
  shared; `markets/specialist` contributes asset-specific parameters without
  overriding the risk engine.
- **Paper execution only** — live trading requires an explicit, deliberate
  configuration change and a credential-isolated adapter.

See also [risk](../risk/README.md) and
[risk architecture](../architecture/RISK_ARCHITECTURE.md).