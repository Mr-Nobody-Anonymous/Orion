# Risk

Risk is above intelligence. The deterministic risk engine gates every order and
never depends on a language model. Governance forbids autonomous mutation of
limits.

Modules: `trading/risk.py`; `trading/execution.py` (`LiveTradingDisabledError`);
`infrastructure/governance.py`; `security/`.

## Limits (`RiskLimits`)

- `max_order_notional`
- `max_position_fraction`
- `max_portfolio_exposure`
- `max_correlation`
- `min_model_confidence`
- `emergency_stop` (kill switch)

## Gate

`RiskEngine.assess(proposal, equity, exposure) -> RiskDecision(approved, reasons)`
rejects on any violation (no fill). `ExecutiveBrain` runs risk before execution;
the executive loop records `RISK_CHECK` in the `LoopTrace`.

## Governance

Research/learning/evolution/generated code **cannot** alter risk limits, enable
live trading, raise exposure caps, or change security permissions. Live trading
is BLOCKED by default (`LiveTradingDisabledError`).

## Blocker summary

| Capability | Status | Blocker |
|---|---|---|
| Deterministic pre-trade gate | IMPLEMENTED | — |
| Kill switch | IMPLEMENTED | `RiskLimits.emergency_stop` |
| Agent-kernel risk gate (Phase 31E) | IMPLEMENTED | `CapabilityExecutor.execute` raises `RiskGateError` for `HIGH`-risk tools without an `approver` in `CapabilityContext`. |
| Live execution | BLOCKED | requires explicit enablement + credential-isolated, audited adapter. |

See also [risk architecture](../architecture/RISK_ARCHITECTURE.md).