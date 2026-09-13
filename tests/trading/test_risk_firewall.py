"""Tests for the 12-Gate Deterministic Risk Firewall."""

from decimal import Decimal
from orion.data.contracts import Action, OrderIntent
from orion.trading.risk_firewall import RiskFirewall


def test_risk_firewall_approves_safe_order() -> None:
    firewall = RiskFirewall()
    intent = OrderIntent(
        intent_id="intent-001",
        strategy_id="momentum_v4",
        symbol="NVDA",
        side=Action.BUY,
        target_quantity=Decimal("50"),
        limit_price=Decimal("120.0"),
    )
    verdict = firewall.evaluate(
        intent,
        portfolio_equity=Decimal("100000.0"),
        current_positions={"NVDA": Decimal("0")},
    )
    assert verdict.approved is True
    assert verdict.failed_gate is None
    assert len(verdict.gate_results) == 12
    assert all(g.passed for g in verdict.gate_results)


def test_risk_firewall_blocks_excessive_position_limit() -> None:
    firewall = RiskFirewall(max_position_pct=0.10)
    intent = OrderIntent(
        intent_id="intent-002",
        strategy_id="momentum_v4",
        symbol="NVDA",
        side=Action.BUY,
        target_quantity=Decimal("200"),
        limit_price=Decimal("120.0"),  # 24,000 notional on 100,000 equity = 24% > 10%
    )
    verdict = firewall.evaluate(
        intent,
        portfolio_equity=Decimal("100000.0"),
        current_positions={"NVDA": Decimal("0")},
    )
    assert verdict.approved is False
    assert verdict.failed_gate == 2
    assert "Position Limit" in str(verdict.rejection_reason)


def test_risk_firewall_blocks_when_kill_switch_engaged() -> None:
    firewall = RiskFirewall()
    intent = OrderIntent(
        intent_id="intent-003",
        strategy_id="momentum_v4",
        symbol="AAPL",
        side=Action.BUY,
        target_quantity=Decimal("10"),
        limit_price=Decimal("150.0"),
    )
    verdict = firewall.evaluate(
        intent,
        portfolio_equity=Decimal("100000.0"),
        current_positions={},
        kill_switch_engaged=True,
    )
    assert verdict.approved is False
    assert verdict.failed_gate == 12
    assert "Kill Switch" in str(verdict.rejection_reason)
