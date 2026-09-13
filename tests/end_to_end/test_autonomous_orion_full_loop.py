"""End-to-End Integration Test for ORION Autonomous Financial Operating System.

Validates the full 7-phase institutional pipeline:
Phase 1: Real-time Data Foundations & Lake
Phase 2: Bloomberg-grade Valuation, Quality & Macro Intelligence
Phase 3: Binance & Kalshi OMS/EMS & Derivatives Engines
Phase 4: Aladdin Institutional Risk, Fixed Income & Double-Entry Ledger
Phase 5: AI Copilot, Causal Reasoning & Strategy Lab
Phase 6: Multi-User RBAC, Surveillance, Telemetry & AI Safety
Phase 7: Complete 16-Phase End-to-End Cognitive Operating Loop
"""

from __future__ import annotations

from decimal import Decimal
import tempfile
import pytest

from orion.orchestration.operating_system import AutonomousFinancialOS
from orion.compliance.multi_user import InstitutionalRole, InstitutionalPermission


def test_autonomous_financial_os_full_loop() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        os_platform = AutonomousFinancialOS(data_root_path=tmp_dir)

        # 1. Execute full autonomous decision loop on NVDA
        prices = [120.0, 121.5, 123.0, 122.0, 125.0, 126.5, 128.0]
        financial_statements = {
            "net_income": 15.0,
            "cfo": 18.0,
            "assets_curr": 100.0,
            "assets_prev": 90.0,
            "debt_curr": 15.0,
            "debt_prev": 20.0,
            "ca_curr": 60.0,
            "ca_prev": 50.0,
            "cl_curr": 25.0,
            "cl_prev": 25.0,
            "margin_curr": 0.55,
            "margin_prev": 0.50,
        }
        macro_events = [("CPI", 3.1, 3.2)]  # Surprises to the downside (favorable)

        res = os_platform.run_autonomous_cycle(
            symbol="NVDA",
            prices=prices,
            financial_statements=financial_statements,
            macro_events=macro_events,
            account_id="apex_fund",
        )

        # Assert cycle outcomes across the 16 phases
        assert res.symbol == "NVDA"
        assert res.observed_bar["close"] == 128.0
        assert res.fundamental_quality_f_score >= 7  # Strong Piotroski quality
        assert res.economic_sentiment in ("DOVISH", "NEUTRAL", "HAWKISH")
        assert len(res.copilot_rationale) > 10
        assert res.regime in ("BULL", "BEAR", "SIDEWAYS")
        assert abs(sum(res.portfolio_weights.values()) - 1.0) < 1e-4
        assert res.var_95_pct >= 0.0
        assert res.stress_loss_2008 < 0.0  # Loss scenario is negative
        assert res.governance_status == "APPROVED"
        assert res.executed_order_id is not None
        assert res.ledger_balanced is True
        assert res.reconciliation_clean is True
        assert res.surveillance_alerts_count == 0


def test_cross_engine_institutional_capabilities() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        os_platform = AutonomousFinancialOS(data_root_path=tmp_dir)

        # 1. Options Platform
        opt_analytics = os_platform.options.black_scholes(
            spot=100.0,
            strike=100.0,
            time_to_expiry_years=1.0,
            risk_free_rate=0.05,
            volatility=0.20,
            is_call=True,
        )
        assert 10.0 < opt_analytics.price < 11.0
        assert 0.60 < opt_analytics.delta < 0.68

        # 2. Kalshi Prediction Market Engine
        implied_prob = os_platform.kalshi.calculate_implied_probability(
            yes_bid=Decimal("0.58"),
            yes_ask=Decimal("0.62"),
        )
        assert implied_prob == Decimal("0.60")

        calibrated = os_platform.kalshi.calibrate_probability(
            market_implied=implied_prob,
            ai_model_prob=Decimal("0.70"),
            ai_confidence=Decimal("0.80"),
        )
        assert calibrated.calibrated_probability == Decimal("0.68")
        assert calibrated.model_edge == Decimal("0.08")
        assert calibrated.kelly_fraction > Decimal("0")

        # 3. Fixed Income Pricing & Duration
        bond_pr = os_platform.fixed_income.price_coupon_bond(
            par_value=Decimal("1000.0"),
            annual_coupon_rate=Decimal("0.06"),
            ytm=Decimal("0.05"),
            years_to_maturity=Decimal("5.0"),
            frequency=2,
        )
        assert bond_pr.clean_price > Decimal("1000.0")  # Premium bond
        assert bond_pr.modified_duration > Decimal("0")
        assert bond_pr.convexity > Decimal("0")

        # 4. Natural Language Screener
        universe = [
            {
                "symbol": "AAPL",
                "pe_ratio": 18.5,
                "pb_ratio": 8.0,
                "roe": 0.35,
                "debt_to_equity": 0.8,
                "revenue_growth": 0.15,
                "asset_class": "EQUITY",
            },
            {
                "symbol": "EXPENSIVE_CO",
                "pe_ratio": 45.0,
                "pb_ratio": 12.0,
                "roe": 0.05,
                "debt_to_equity": 2.5,
                "revenue_growth": -0.05,
                "asset_class": "EQUITY",
            },
        ]
        screen_results = os_platform.screen("pe < 25 and roe > 0.20", universe)
        assert [r.symbol for r in screen_results] == ["AAPL"]

        # 5. Multi-User RBAC & Dual-Custody Approval
        org = os_platform.user_manager.register_organization("Institutional Alpha", "alpha.com")
        team = os_platform.user_manager.create_team(org.org_id, "Quant Trading", "Systematic")
        trader = os_platform.user_manager.create_user(
            "trader_dan", "dan@alpha.com", org.org_id, team.team_id, InstitutionalRole.TRADER, max_notional=250_000.0
        )
        pm = os_platform.user_manager.create_user(
            "pm_sarah", "sarah@alpha.com", org.org_id, team.team_id, InstitutionalRole.PORTFOLIO_MANAGER, max_notional=1_000_000.0
        )

        idea = os_platform.user_manager.submit_trade_idea(
            author_id=trader.user_id, symbol="NVDA", action="BUY", notional=150_000.0, thesis="Strong AI capex"
        )
        approved_idea = os_platform.user_manager.review_trade_idea(
            reviewer_id=pm.user_id, idea_id=idea.idea_id, approved=True
        )
        assert approved_idea.status == "APPROVED"

        # 6. Telemetry & Prometheus Exposition
        prom_text = os_platform.telemetry.exporter.export_text()
        assert isinstance(prom_text, str)
