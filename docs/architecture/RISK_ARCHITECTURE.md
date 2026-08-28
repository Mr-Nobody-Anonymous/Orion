# Risk Architecture

Risk is above intelligence. The execution path is always
**AI → decision → risk → execution**, with risk deterministic and independent
of language models.

Modules: `trading/risk.py` (`RiskEngine`, `RiskLimits`), `brain/executive.py`
(`ExecutiveBrain`), `trading/execution.py` (`SimulatedBroker`,
`LiveTradingDisabledError`), `infrastructure/governance.py`, `security/`.

## Path

```
      AI / council prediction (may be unavailable — not required)
                     │
                     ▼
   ┌──────────────────────────────┐
   │  DECISION  (DECIDE/PLAN)     │  brain/decision.py → Action
   └──────────────┬───────────────┘
                  │  TradeProposal
                  ▼
   ┌──────────────────────────────┐
   │  RISK ENGINE (deterministic) │  RiskEngine.assess()
   │  RiskLimits:                 │
   │   max_order_notional         │
   │   max_position_fraction      │
   │   max_portfolio_exposure     │
   │   max_correlation            │
   │   min_model_confidence       │
   │   emergency_stop             │
   └──────────────┬───────────────┘
                  │ approved?
                  ▼
   ┌─── approved ─────┴────── rejected ───┐
   ▼                                      ▼
   EXECUTION (SimulatedBroker)         Record rejection + reasons;
   publish OrderFilled event           NO fill.
```

## Deterministic gate

`RiskEngine.assess(proposal, equity, exposure)` returns a `RiskDecision`
(`approved`, `reasons`). It rejects when:

- the emergency stop is active;
- equity is non-positive;
- order notional exceeds `max_order_notional`;
- portfolio exposure would exceed `max_portfolio_exposure` (including the
  incoming order);
- trade correlation exceeds `max_correlation`;
- model confidence is below `min_model_confidence` (when a prediction exists).

## Executive enforcement

`ExecutiveBrain.execute(proposal)` consults risk **before** any
`broker.place_order`; a rejected proposal never reaches the broker. The
executive loop (`ExecutiveOrchestrator`) treats a risk rejection as
`DECIDE: WAIT` / `ACT: not acted`.

## Simulated execution only

- `SimulatedBroker` is the canonical execution simulator (paper).
- `AlpacaAdapter` raises `LiveTradingDisabledError` unless live trading is
  explicitly enabled — including its own construction.
- Live buying never bypasses the risk gate; the architecture is layered so
  `ExecutiveBrain` and `RiskEngine` are the only order entry points.

## Governance

`PromotionGate` (infrastructure/governance.py) is deny-by-default. Research,
learning, and generated code **cannot** modify risk limits, enable live
trading, raise exposure caps, or change security permissions. Kill-switch
support is expressed as `RiskLimits.emergency_stop`.