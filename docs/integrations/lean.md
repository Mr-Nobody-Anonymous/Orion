# QuantConnect LEAN Integration Guide

## Overview & Role
QuantConnect LEAN is an institutional-grade event-driven algorithmic trading engine. In Orion, LEAN functions as the **multi-asset event-driven backtesting and live venue bridge engine**.

- **Category**: Execution & Event-Driven Backtesting
- **License**: Apache-2.0 (Permissive)
- **Integration Mode**: Level 3 Service / Subprocess (`adapters/lean/`)
- **Pinned Commit**: `c4b192e85a73e6b1293a61dfb6088e89571fa08d`

---

## Capabilities Provided

1. `event_driven_backtest`: Accurate tick, second, and minute multi-asset event simulation.
2. `multi_asset_execution`: Order routing and custody synchronization across equities, options, futures, and FX.
3. `order_book_simulation`: Realistic bid/ask queue modeling and liquidity exhaustion simulation.

---

## Data Contract & Process Isolation

LEAN runs as a decoupled CLI / Docker service communicating via JSON over pipes:

```
Canonical ExecutionPlan (plan_id, intent, slices, router)
      │
      ▼
adapters.lean.LeanServiceAdapter.submit_order()
      │
      ▼
LEAN Engine (Interactive Brokers / Venue Bridge)
      │
      ▼
Canonical ExecutionReport (report_id, fills, slippage_bps, commission)
```

**Risk Safeguard:**
LEAN may never place a broker order without passing through Orion's 12-Gate Risk Firewall. The firewall verdict is validated before dispatch to LEAN.
