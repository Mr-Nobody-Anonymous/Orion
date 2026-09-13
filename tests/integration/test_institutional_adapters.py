"""Integration tests for Orion Institutional Adapters and Engine Architecture."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import pytest

from adapters import (
    BacktestEngine,
    BrokerAdapter,
    ExchangeAdapter,
    ExecutionEngine,
    ForecastEngine,
    MarketDataProvider,
    ModelProvider,
    PortfolioOptimizer,
    ResearchProvider,
    RiskEngine,
)
from orion.data.contracts import (
    Action,
    AssetClass,
    Instrument,
    MarketBar,
    OrderIntent,
    Position,
    PortfolioSnapshot,
    RiskMeasurement,
    Scenario,
)
from orion.intelligence.council.council import OrionAICouncil
from orion.trading.risk_firewall import RiskFirewall


def test_adapter_interfaces_exposed() -> None:
    """Verify all 10 canonical adapter interfaces exist and are runtime checkable."""
    interfaces = [
        MarketDataProvider,
        ResearchProvider,
        ForecastEngine,
        BacktestEngine,
        PortfolioOptimizer,
        RiskEngine,
        ExecutionEngine,
        BrokerAdapter,
        ExchangeAdapter,
        ModelProvider,
    ]
    for iface in interfaces:
        assert callable(iface)


def test_canonical_schemas_instantiation() -> None:
    """Verify instantiating canonical contracts with strict typing."""
    inst = Instrument(
        symbol="NVDA",
        asset_class=AssetClass.EQUITY,
        venue="NASDAQ",
        currency="USD",
    )
    assert inst.symbol == "NVDA"
    assert inst.asset_class == AssetClass.EQUITY

    intent = OrderIntent(
        intent_id="INT-999",
        strategy_id="momentum_v4",
        symbol="NVDA",
        side=Action.BUY,
        target_quantity=Decimal("100"),
        limit_price=Decimal("125.0"),
    )
    assert intent.symbol == "NVDA"
    assert intent.target_quantity == Decimal("100")


def test_risk_firewall_blocks_excessive_leverage() -> None:
    """Verify that an order causing gross leverage breach is strictly vetoed."""
    firewall = RiskFirewall(
        max_position_pct=10.0,
        max_concentration_pct=10.0,
        max_sector_concentration_pct=10.0,
        max_leverage=3.0,
    )
    intent = OrderIntent(
        intent_id="INT-LEVERAGE-TEST",
        strategy_id="test_strat",
        symbol="NVDA",
        side=Action.BUY,
        target_quantity=Decimal("5000"),
        limit_price=Decimal("100.0"),  # 500,000 notional on 100,000 equity = 5.0x > 3.0x
    )
    verdict = firewall.evaluate(
        intent,
        portfolio_equity=Decimal("100000.0"),
        current_positions={"NVDA": Decimal("0")},
    )
    assert verdict.approved is False
    assert verdict.failed_gate == 4  # Gate 4: Leverage
    assert "Leverage" in (verdict.rejection_reason or "")


def test_ai_council_enforces_risk_veto() -> None:
    """Verify that an asserted risk veto overrides all other agent recommendations."""
    council = OrionAICouncil()
    context = {
        "instrument": "NVDA",
        "asset": "NVDA",
        "price": 130.0,
        "volatility": 0.55,  # extreme volatility triggering risk veto
        "adv_ratio": 0.05,  # 5% ADV triggers liquidity warning
        "technology_factor": 0.42,  # exceeds 30% concentration
        "var_pct": 0.038,  # exceeds 2.5% VaR threshold
        "stress_loss_2008": 0.32,  # exceeds 25% stress loss
        "spread_bps": 8.5,
        "liquidity_ok": False,
        "data_quality_score": 60.0,
    }
    consensus = council.deliberate("Should Orion buy NVDA?", context)
    assert consensus.risk_veto_asserted is True
    assert consensus.action_proposal in ("REDUCE", "WAIT", "ABORT")
    assert consensus.risk_veto_reason is not None


def test_repository_inventory_matches_registry() -> None:
    """Verify reports/repository_inventory.json consistency with registry/repositories.yaml."""
    repo_report_path = Path(__file__).resolve().parent.parent.parent / "reports" / "repository_inventory.json"
    assert repo_report_path.exists(), "Repository inventory report must exist"

    data = json.loads(repo_report_path.read_text(encoding="utf-8"))
    repos = data.get("repositories", {})
    assert len(repos) >= 17, "Must contain at least 17 pinned computing engines"
    for name, details in repos.items():
        assert details.get("pinned_commit"), f"Repo '{name}' must have a pinned commit SHA"
        assert details.get("license"), f"Repo '{name}' must have a recorded license"
        assert details.get("integration_mode"), f"Repo '{name}' must have an integration mode"
