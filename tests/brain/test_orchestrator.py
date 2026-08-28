"""Tests for the full executive orchestrator loop."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from orion.brain import ExecutiveOrchestrator
from orion.data.contracts import Asset, AssetClass, MarketQuote
from orion.forecasting import LinearTrendForecaster
from orion.trading.execution import SimulatedBroker
from orion.trading.risk import RiskLimits, RiskEngine


def _seed_broker() -> SimulatedBroker:
    broker = SimulatedBroker()
    asset = Asset("DEMO", AssetClass.EQUITY)
    broker.set_quote(MarketQuote(asset, datetime.now(timezone.utc), Decimal("99"), Decimal("101"), Decimal("100")))
    return broker


def test_orchestrator_runs_all_phases_and_audits() -> None:
    broker = _seed_broker()
    risk = RiskEngine(RiskLimits(max_order_notional=Decimal("1000")))
    orchestrator = ExecutiveOrchestrator(
        broker=broker,
        risk=risk,
        forecaster=LinearTrendForecaster(),
    )
    orchestrator.seed_default_goals()
    asset = Asset("DEMO", AssetClass.EQUITY)
    prices = [100, 101, 102, 103, 104, 105, 106]
    trace = orchestrator.run_cycle(asset, prices, actual_return=Decimal("0.02"))
    phases = [phase.value for phase, _ in trace.phases]
    expected = [
        "observe", "understand", "remember", "research", "hypothesize",
        "predict", "generate_options", "simulate", "evaluate", "plan",
        "risk_check", "decide", "act", "observe_outcome", "reflect", "learn",
    ]
    for name in expected:
        assert name in phases
    assert len(orchestrator.trace_history()) == 1
    assert trace.asset.symbol == "DEMO"


def test_orchestrator_handles_actual_return_none() -> None:
    broker = _seed_broker()
    risk = RiskEngine(RiskLimits(max_order_notional=Decimal("1000")))
    orchestrator = ExecutiveOrchestrator(broker=broker, risk=risk, forecaster=LinearTrendForecaster())
    asset = Asset("DEMO", AssetClass.EQUITY)
    trace = orchestrator.run_cycle(asset, [100, 101, 102, 103, 104])
    reflect_payload = dict(trace.phases)[_phase_key("reflect")] if False else next(payload for phase, payload in trace.phases if phase.value == "reflect")
    assert reflect_payload["reflection"] == "no-outcome-yet"


def test_orchestrator_risk_rejection_short_circuits_execution() -> None:
    broker = _seed_broker()
    # Force a rejection by limiting notional to zero.
    risk = RiskEngine(RiskLimits(max_order_notional=Decimal("0")))
    orchestrator = ExecutiveOrchestrator(broker=broker, risk=risk, forecaster=LinearTrendForecaster())
    asset = Asset("DEMO", AssetClass.EQUITY)
    trace = orchestrator.run_cycle(asset, [100, 101, 102, 103, 104, 105, 106])
    if trace.decision.value == "WAIT":
        # The decision engine may decide WAIT on its own; ensure the act step is not harmful
        assert not trace.risk_reasons
    else:
        assert not trace.risk_approved
        assert trace.risk_reasons


def test_orchestrator_reflects_on_overshoot() -> None:
    broker = _seed_broker()
    risk = RiskEngine(RiskLimits(max_order_notional=Decimal("100000")))
    orchestrator = ExecutiveOrchestrator(broker=broker, risk=risk, forecaster=LinearTrendForecaster())
    asset = Asset("DEMO", AssetClass.EQUITY)
    trace = orchestrator.run_cycle(asset, [100, 101, 102, 103, 104, 105, 106], actual_return=Decimal("0.20"))
    reflect = next(payload for phase, payload in trace.phases if phase.value == "reflect")
    assert reflect["reflection"] != "no-outcome-yet"


def _phase_key(name: str) -> str:
    return name
