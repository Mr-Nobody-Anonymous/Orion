# Orion Execution Architecture & Smart Order Routing

This document details the order execution lifecycle, broker abstractions, smart order routing algorithms, transaction cost models, and venue safety boundaries.

---

## 1. End-to-End Execution Flow

Strategies **NEVER** place orders directly with broker APIs. The entire lifecycle flows through strict intermediate contracts:

```
[Strategy / Portfolio Engine]
              │
              ▼ (Emits)
       [OrderIntent]
              │
              ▼ (Audited by)
   [12-Gate Risk Firewall]
              │
              ▼ (If Approved)
    [Execution Planner]
              │
              ▼ (Emits)
      [ExecutionPlan]
              │
              ▼ (Optimized by)
   [Smart Order Router]
              │
              ▼ (Dispatched to)
       [BrokerAdapter]
    (LEAN / CCXT / Alpaca)
              │
              ▼
    [Execution Venue]
  (NASDAQ / NYSE / Binance)
              │
              ▼ (Returns)
     [ExecutionReport]
```

---

## 2. Supported Execution Algorithms

Depending on the `urgency` field specified in `OrderIntent`, the `ExecutionPlanner` selects an appropriate execution algorithm:

1. **TWAP (Time-Weighted Average Price)**:
   Slices an order into equally spaced time buckets over a specified horizon. Minimizes price disruption for medium-urgency institutional rebalances.
2. **VWAP (Volume-Weighted Average Price)**:
   Dynamically weights child orders according to the historical intraday volume profile of the asset. Minimizes overall market impact.
3. **POV (Percentage of Volume / Participation Rate)**:
   Places child orders to match a constant fraction of real-time market tape volume (e.g., participate at 1.5% of volume). Prevents order detection and adverse selection.
4. **Implementation Shortfall (IS)**:
   Balances market impact against the opportunity cost of delaying execution using an Almgren-Chriss optimal execution trajectory.
5. **Iceberg Orders**:
   Displays only a small fraction of the total order size on the public order book, replenishing the visible tip as fills occur.
6. **Passive / Aggressive Pegging**:
   Rests orders at the national best bid/offer (NBBO) for maker rebates, crossing the spread only when urgency escalates.

---

## 3. Venue & Broker Connectivity Matrix

| Adapter | Engine / Backend | Supported Asset Classes | Key Capabilities | Notes & Restrictions |
| :--- | :--- | :--- | :--- | :--- |
| **QuantConnect LEAN** | C# Engine / Docker CLI | Equities, Futures, Options, FX, Crypto | Multi-venue institutional broker bridging, tick-level order book simulation | Runs as an isolated service process |
| **CCXT** | Python / AsyncIO | Crypto Spot, Swaps, Futures | 100+ cryptocurrency exchanges, WebSocket private order feeds | Uses pinned commit; strict API key isolation |
| **Alpaca-py** | Official SDK | US Equities, Options, Crypto | Commission-free US equity execution, paper trading accounts | Level 1 / Level 2 integration |
| **IBKR Gateway** | Interactive Brokers | Equities, Bonds, FX, Futures, Options | Institutional global custody and clearing | Routed via LEAN's native InteractiveBrokers gateway rather than archived libraries |

> **Architectural Note on `ib_insync`:**  
> The third-party `ib_insync` library was archived by its original maintainers in March 2024. To prevent supply-chain security and maintenance risks, Orion routes Interactive Brokers connectivity through QuantConnect LEAN's maintained C#/Python gateway or the official IBKR Client Portal REST API.

---

## 4. Strict State Separation

Orion enforces total process and memory separation between execution states:
- **Simulation State**: Operates entirely in memory or temporary fixtures with zero external network connectivity.
- **Paper State**: Submits mock orders to authenticated sandbox endpoints with synthetic fills.
- **Live State**: Requires explicitly confirmed environment secrets, dual-key human authorization for initial deployment, and active kill-switch monitoring.

A simulation or backtest run can **never** mutate live portfolio state or access production broker credentials.
