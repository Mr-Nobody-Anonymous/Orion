"""Tests for Phase 6 Institutional Layer.

Covers:
- Market surveillance (spoofing, layering, wash trading)
- Multi-user RBAC/ABAC and maker-checker approval workflows
- Key vault, IP CIDR validation, TOTP (RFC 6238), and withdrawal timelocks
- Telemetry, Prometheus exposition, and W3C distributed trace context
- Low-latency fast-path ring buffer, order book, and tick routing
- AI safety guardrail, emergency shutdown, and dual-custody governance
"""

from __future__ import annotations

import time
import pytest

from orion.compliance.surveillance import MarketSurveillanceEngine
from orion.compliance.multi_user import (
    InstitutionalUserManager,
    InstitutionalRole,
    InstitutionalPermission,
)
from orion.security.key_vault import InstitutionalKeyVault, KeyStatus
from orion.ops.telemetry import PrometheusExporter, W3CTraceContext
from orion.ops.metrics import MetricsRegistry, Counter, Gauge, Histogram
from orion.infrastructure.fast_path import (
    RingBuffer,
    LowLatencyOrderBook,
    FastTickRouter,
    FastTick,
)
from orion.compliance.governance_guard import (
    AISafetyGuardrail,
    GovernedProposal,
    GovernanceActionType,
    GovernanceDecisionStatus,
)


def test_market_surveillance_spoofing_and_wash() -> None:
    surveillance = MarketSurveillanceEngine(
        spoofing_cancel_ratio_threshold=0.7,
        wash_trade_window_seconds=10.0,
    )
    now = time.time()

    # Feed 10 placed orders and 9 cancels -> 90% cancel ratio
    for i in range(10):
        surveillance.record_order("trader_1", "NVDA", "BUY", 100.0, 100.0, now + i * 0.1)
    for i in range(9):
        surveillance.record_cancel("trader_1", "NVDA", 100.0, now + 1.0 + i * 0.1)

    spoofing_alerts = surveillance.detect_spoofing("trader_1", "NVDA", now + 5.0)
    assert len(spoofing_alerts) >= 1
    assert spoofing_alerts[0].manipulation_type == "SPOOFING"

    # Wash trading: matched buy and sell for trader_2
    surveillance.record_trade("trader_2", "BTC/USDT", "BUY", 65000.0, 1.5, now + 10.0)
    surveillance.record_trade("trader_2", "BTC/USDT", "SELL", 65000.0, 1.5, now + 12.0)

    wash_alerts = surveillance.detect_wash_trading("trader_2", "BTC/USDT", now + 15.0)
    assert len(wash_alerts) >= 1
    assert wash_alerts[0].manipulation_type == "WASH_TRADING"


def test_multi_user_rbac_abac_and_maker_checker() -> None:
    mgr = InstitutionalUserManager()
    org = mgr.register_organization("Apex Quant", "apexquant.com")
    team = mgr.create_team(org.org_id, "Alpha Strategies", "Stat Arb")

    pm = mgr.create_user("alice_pm", "alice@apexquant.com", org.org_id, team.team_id, InstitutionalRole.PORTFOLIO_MANAGER, max_notional=500_000.0)
    trader = mgr.create_user("bob_trader", "bob@apexquant.com", org.org_id, team.team_id, InstitutionalRole.TRADER, max_notional=100_000.0, allowed_asset_classes=("EQUITY", "CRYPTO"))

    # Check Trader permissions
    auth_ok, _ = mgr.authorize(trader.user_id, InstitutionalPermission.EXECUTE_ORDER, asset_class="EQUITY", notional=50_000.0)
    assert auth_ok is True

    # Check exceeding notional limit
    auth_over, msg = mgr.authorize(trader.user_id, InstitutionalPermission.EXECUTE_ORDER, asset_class="EQUITY", notional=200_000.0)
    assert auth_over is False
    assert "exceeds user limit" in msg

    # Check unauthorized asset class
    auth_fx, msg_fx = mgr.authorize(trader.user_id, InstitutionalPermission.EXECUTE_ORDER, asset_class="FX", notional=10_000.0)
    assert auth_fx is False
    assert "not permitted" in msg_fx

    # Maker-Checker trade idea
    idea = mgr.submit_trade_idea(trader.user_id, "AAPL", "BUY", 75_000.0, "Strong earnings momentum")
    assert idea.status == "PROPOSED"

    # Author cannot approve own idea
    with pytest.raises(ValueError, match="Maker-checker violation"):
        mgr.review_trade_idea(trader.user_id, idea.idea_id, approved=True)

    # PM approves idea
    approved_idea = mgr.review_trade_idea(pm.user_id, idea.idea_id, approved=True)
    assert approved_idea.status == "APPROVED"
    assert approved_idea.approver_id == pm.user_id


def test_key_vault_rotation_totp_and_timelock() -> None:
    vault = InstitutionalKeyVault(timelock_delay_seconds=3600.0)
    key = vault.register_key("user_1", "BINANCE", "super_secret_api_key", ip_whitelist=["192.168.1.0/24", "10.0.0.5"])
    assert key.version == 1
    assert key.status == KeyStatus.ACTIVE

    # IP validation
    valid_ip, _ = vault.validate_access(key.key_id, "192.168.1.50")
    assert valid_ip is True

    invalid_ip, msg = vault.validate_access(key.key_id, "172.16.0.1")
    assert invalid_ip is False
    assert "not in authorized whitelist" in msg

    # Key rotation
    rotated = vault.rotate_key(key.key_id, "new_rotated_secret_key")
    assert rotated.version == 2
    assert rotated.key_digest != key.key_digest

    # TOTP RFC 6238
    totp_secret = vault.generate_totp_secret()
    now = time.time()
    code = vault.compute_totp(totp_secret, timestamp=now)
    assert len(code) == 6
    assert vault.verify_totp(totp_secret, code, timestamp=now) is True
    assert vault.verify_totp(totp_secret, "999999", timestamp=now) is False

    # Withdrawal timelock
    addr = vault.propose_withdrawal_address("user_1", "USDC", "0x1234567890abcdef1234567890abcdef12345678")
    allowed, msg = vault.check_withdrawal_authorization(addr.address_id, "USDC", "0x1234567890abcdef1234567890abcdef12345678")
    assert allowed is False
    assert "security timelock" in msg


def test_telemetry_and_w3c_tracing() -> None:
    registry = MetricsRegistry()
    c = Counter("orders_executed_total", labels={"venue": "binance", "symbol": "BTC"})
    c_series = (c.name, frozenset(c.labels.items()))
    registry._counters[c_series] += 42.0

    g = Gauge("portfolio_leverage", labels={"account": "fund_a"})
    g_series = (g.name, frozenset(g.labels.items()))
    registry._gauges[g_series] = 1.45

    exporter = PrometheusExporter(registry)
    text = exporter.export_text()
    assert "# TYPE orders_executed_total counter" in text
    assert 'orders_executed_total{symbol="BTC",venue="binance"} 42.0' in text
    assert "# TYPE portfolio_leverage gauge" in text
    assert 'portfolio_leverage{account="fund_a"} 1.45' in text

    # W3C Traceparent Header Parsing
    header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    ctx = W3CTraceContext.parse(header)
    assert ctx.version == "00"
    assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert ctx.parent_id == "00f067aa0ba902b7"
    assert ctx.to_header() == header


def test_fast_path_ring_buffer_and_order_book() -> None:
    # Ring buffer
    rb: RingBuffer[int] = RingBuffer(capacity=3)
    rb.push(1)
    rb.push(2)
    rb.push(3)
    assert rb.count == 3
    # Overwrite oldest (1 should be dropped)
    rb.push(4)
    assert rb.count == 3
    assert rb.to_list() == [2, 3, 4]
    assert rb.pop() == 2
    assert rb.to_list() == [3, 4]

    # Fast Order Book
    book = LowLatencyOrderBook("ETH/USD", "KRAKEN")
    book.update_level("BID", 3500.0, 10.0)
    book.update_level("BID", 3501.0, 5.0)
    book.update_level("ASK", 3502.0, 8.0)
    book.update_level("ASK", 3503.0, 15.0)

    assert book.best_bid == 3501.0
    assert book.best_ask == 3502.0
    assert book.spread == 1.0
    assert book.mid_price == 3501.5

    bids, asks = book.depth(levels=1)
    assert bids == [(3501.0, 5.0)]
    assert asks == [(3502.0, 8.0)]

    # Fast Tick Router
    router = FastTickRouter()
    received: list[FastTick] = []
    router.subscribe("ETH/USD", received.append)

    tick = FastTick(
        symbol="ETH/USD",
        venue="KRAKEN",
        timestamp_ns=time.time_ns(),
        bid_price=3501.0,
        bid_size=5.0,
        ask_price=3502.0,
        ask_size=8.0,
        last_price=3501.5,
        last_volume=1.2,
    )
    dispatched = router.route_tick(tick)
    assert dispatched == 1
    assert len(received) == 1
    assert received[0].symbol == "ETH/USD"


def test_ai_safety_governance_and_emergency_shutdown() -> None:
    guard = AISafetyGuardrail(
        min_confidence_threshold=0.70,
        max_autonomous_notional=100_000.0,
        max_daily_spend_limit=500_000.0,
    )

    # 1. Low confidence rejection
    low_conf = GovernedProposal("prop_1", "model_lstm", GovernanceActionType.PROPOSE_ORDER, "AAPL", 50_000.0, 0.60, "Weak signal")
    eval_1 = guard.evaluate_proposal(low_conf)
    assert eval_1.status == GovernanceDecisionStatus.REJECTED
    assert "below threshold" in eval_1.reasons[0]

    # 2. Autonomous approval for acceptable confidence & notional
    ok_prop = GovernedProposal("prop_2", "model_transformer", GovernanceActionType.PROPOSE_ORDER, "AAPL", 50_000.0, 0.85, "Strong breakout")
    eval_2 = guard.evaluate_proposal(ok_prop)
    assert eval_2.status == GovernanceDecisionStatus.APPROVED

    # 3. High notional requires human approval (dual custody)
    high_prop = GovernedProposal("prop_3", "model_transformer", GovernanceActionType.PROPOSE_ORDER, "TSLA", 250_000.0, 0.90, "Catalyst event")
    eval_3 = guard.evaluate_proposal(high_prop)
    assert eval_3.status == GovernanceDecisionStatus.REQUIRES_HUMAN_APPROVAL
    assert eval_3.requires_signatures == 2

    # First officer signs
    s1 = guard.sign_proposal(high_prop.proposal_id, "officer_alice")
    assert s1.status == GovernanceDecisionStatus.REQUIRES_HUMAN_APPROVAL

    # Second officer signs -> auto approved
    s2 = guard.sign_proposal(high_prop.proposal_id, "officer_bob")
    assert s2.status == GovernanceDecisionStatus.APPROVED

    # 4. Emergency shutdown
    guard.trigger_emergency_shutdown("ciso", "Suspected network anomaly")
    assert guard.is_emergency_shutdown is True

    blocked_prop = GovernedProposal("prop_4", "model_transformer", GovernanceActionType.PROPOSE_ORDER, "NVDA", 10_000.0, 0.95, "Safe trade")
    eval_4 = guard.evaluate_proposal(blocked_prop)
    assert eval_4.status == GovernanceDecisionStatus.BLOCKED_EMERGENCY

    # Lift shutdown with dual signoff
    guard.lift_emergency_shutdown("ciso", "coo")
    assert guard.is_emergency_shutdown is False
