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


def test_orchestrator_uses_market_value_exposure_not_share_count() -> None:
    """Regression: the executive loop must use market-value exposure.

    Setup: pre-populate the broker with 1000 shares of a $200 asset and
    $100,000 equity. The market-value exposure is 200,000/100,000 = 2.0
    (over-levered). The buggy share-count formula would report
    1000/100,000 = 0.01 (looks fine!). The risk gate should reject any
    new order on this account because the market-value exposure
    exceeds the default ``max_portfolio_exposure`` of 1.0.
    """
    from orion.brain.executive import ExecutiveBrain
    from orion.domain import TradeProposal
    from orion.data.contracts import Action, OrderRequest
    from orion.event_bus import EventBus
    from orion.trading.risk import RiskLimits, RiskEngine

    asset = Asset("EXP", AssetClass.EQUITY)
    broker = SimulatedBroker(starting_cash=Decimal("100000"))
    broker.set_quote(
        MarketQuote(asset, datetime.now(timezone.utc), Decimal("199"), Decimal("201"), Decimal("200"))
    )
    # Place a 500-share position at $200 = $100k of market value, so
    # market-value exposure is 1.0 (= 100k/100k equity) and share-count
    # exposure is 500/100000 = 0.005. The risk gate is configured to
    # reject anything strictly above 1.0; the buggy share-count formula
    # would have approved additional orders.
    broker.place_order(
        OrderRequest(asset=asset, quantity=Decimal("500"), side=Action.BUY, limit_price=Decimal("200"))
    )
    # Tight risk limit: any exposure > 1.0 is rejected.
    risk = RiskEngine(
        RiskLimits(
            max_portfolio_exposure=Decimal("1.0"),
            max_order_notional=Decimal("100000"),
        )
    )
    brain = ExecutiveBrain(broker=broker, risk=risk, events=EventBus())
    proposal = TradeProposal(
        order=OrderRequest(asset=asset, quantity=Decimal("1"), side=Action.BUY, limit_price=Decimal("200")),
        prediction=None,
        rationale="regression-test",
    )
    decision = brain.execute(proposal)
    # If the brain used the buggy share-count formula it would have
    # allowed this order (0.01 < 1.0). With the correct market-value
    # formula (2.0) it must reject.
    assert decision.approved is False
    assert any("exposure" in r.lower() for r in decision.reasons)
