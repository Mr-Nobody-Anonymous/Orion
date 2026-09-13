"""Tests for Phase 2: Bloomberg Layer.

Covers:
- DCF, DDM, and Comparable Company Analysis valuation
- DuPont ROE decomposition, Piotroski F-score, and Altman Z-score
- Corporate credit metrics (Net Debt / EBITDA, Interest Coverage)
- Macroeconomic surprise analysis and central bank stance
- Financial Knowledge Graph supply-chain shock propagation
- Event Graph news-to-asset causal impact
- Event Study market model, Abnormal Returns (AR), and CAR
- Multi-asset quantitative screening and Natural-Language Query parser
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from orion.data.contracts import Asset, AssetClass, EconomicEvent, NewsEvent
from orion.evaluation.event_study import EventStudyEngine
from orion.intelligence.fundamental import (
    CompanyIntelligenceEngine,
    FinancialQualityEngine,
    ValuationEngine,
)
from orion.intelligence.macro import (
    CentralBankStance,
    EconomicIntelligenceEngine,
    MacroSurpriseDirection,
)
from orion.intelligence.screener import (
    NaturalLanguageScreener,
    ScreenFilter,
    ScreenerEngine,
)
from orion.world_model.event_graph import EventGraphEngine
from orion.world_model.knowledge_graph import (
    FinancialKnowledgeGraph,
    RelationType,
)


# ---------------------------------------------------------------------------
# 1. Fundamental Valuation Engine
# ---------------------------------------------------------------------------

def test_dcf_valuation() -> None:
    fcf = [Decimal("100"), Decimal("110"), Decimal("121"), Decimal("133"), Decimal("146")]
    wacc = Decimal("0.08")  # 8%
    g = Decimal("0.02")  # 2%
    net_debt = Decimal("200")
    shares = Decimal("50")

    result = ValuationEngine.dcf(
        projected_fcf=fcf,
        wacc=wacc,
        terminal_growth_rate=g,
        net_debt=net_debt,
        shares_outstanding=shares,
    )

    assert result.enterprise_value > 0
    assert result.equity_value == result.enterprise_value - net_debt
    assert result.implied_share_price == result.equity_value / shares
    assert result.pv_terminal_value > result.pv_projected_cash_flows


def test_ddm_gordon_growth() -> None:
    d1 = Decimal("3.00")
    r = Decimal("0.09")
    g = Decimal("0.03")

    # P0 = 3.00 / (0.09 - 0.03) = 3.00 / 0.06 = 50.00
    p0 = ValuationEngine.ddm_gordon_growth(d1, r, g)
    assert p0 == Decimal("50.00")


def test_comparable_multiples() -> None:
    target = {"pe_ratio": Decimal("10.0"), "ev_to_ebitda": Decimal("50.0")}
    peers = {
        "pe_ratio": [Decimal("18.0"), Decimal("20.0"), Decimal("22.0")],  # Median: 20
        "ev_to_ebitda": [Decimal("10.0"), Decimal("12.0"), Decimal("14.0")],  # Median: 12
    }
    comps = ValuationEngine.comparable_multiples(target, peers)

    assert comps["pe_ratio"]["peer_median"] == Decimal("20.0")
    assert comps["pe_ratio"]["implied_valuation"] == Decimal("200.0")  # 10 * 20
    assert comps["ev_to_ebitda"]["peer_median"] == Decimal("12.0")
    assert comps["ev_to_ebitda"]["implied_valuation"] == Decimal("600.0")  # 50 * 12


# ---------------------------------------------------------------------------
# 2. Financial Quality & Solvency
# ---------------------------------------------------------------------------

def test_dupont_analysis() -> None:
    dupont = FinancialQualityEngine.dupont_3stage(
        net_income=Decimal("20"),
        revenue=Decimal("100"),
        total_assets=Decimal("200"),
        shareholders_equity=Decimal("50"),
    )
    # Net margin = 20 / 100 = 0.20
    # Asset turnover = 100 / 200 = 0.50
    # Equity multiplier = 200 / 50 = 4.0
    # ROE = 0.20 * 0.50 * 4.0 = 0.40 (40%)
    assert dupont.net_profit_margin == Decimal("0.20")
    assert dupont.asset_turnover == Decimal("0.50")
    assert dupont.equity_multiplier == Decimal("4.0")
    assert dupont.roe == Decimal("0.40")


def test_piotroski_f_score() -> None:
    res = FinancialQualityEngine.piotroski_f_score(
        net_income_curr=Decimal("15"),
        net_income_prior=Decimal("10"),
        operating_cfo_curr=Decimal("20"),
        total_assets_curr=Decimal("100"),
        total_assets_prior=Decimal("100"),
        long_term_debt_curr=Decimal("30"),
        long_term_debt_prior=Decimal("40"),
        current_ratio_curr=Decimal("2.0"),
        current_ratio_prior=Decimal("1.5"),
        shares_curr=Decimal("50"),
        shares_prior=Decimal("50"),
        gross_margin_curr=Decimal("0.45"),
        gross_margin_prior=Decimal("0.40"),
        asset_turnover_curr=Decimal("1.2"),
        asset_turnover_prior=Decimal("1.0"),
    )
    # Pristine improvement across all metrics -> F-score = 9
    assert res.f_score == 9
    assert res.profitability_score == 4
    assert res.leverage_liquidity_score == 3
    assert res.operating_efficiency_score == 2


def test_altman_z_score() -> None:
    safe_co = FinancialQualityEngine.altman_z_score(
        working_capital=Decimal("40"),
        total_assets=Decimal("100"),
        retained_earnings=Decimal("30"),
        ebit=Decimal("25"),
        market_value_equity=Decimal("200"),
        total_liabilities=Decimal("50"),
        sales=Decimal("150"),
    )
    assert safe_co.z_score > Decimal("2.99")
    assert safe_co.classification == "SAFE"


# ---------------------------------------------------------------------------
# 3. Company Intelligence & Credit
# ---------------------------------------------------------------------------

def test_credit_metrics() -> None:
    metrics = CompanyIntelligenceEngine.calculate_credit_metrics(
        total_debt=Decimal("250"),
        cash=Decimal("50"),
        ebitda=Decimal("100"),
        interest_expense=Decimal("15"),
    )
    # Net debt = 200. Net debt / EBITDA = 2.0. Interest coverage = 100 / 15 = 6.67
    assert metrics.net_debt == Decimal("200")
    assert metrics.net_debt_to_ebitda == Decimal("2.0")
    assert metrics.interest_coverage > Decimal("6.6")
    assert metrics.is_investment_grade_estimate is True


# ---------------------------------------------------------------------------
# 4. Economic Intelligence & Macro
# ---------------------------------------------------------------------------

def test_macro_surprise_and_central_bank_stance() -> None:
    now = datetime.now(timezone.utc)
    event_beat = EconomicEvent(
        name="US Nonfarm Payrolls",
        timestamp=now,
        actual=Decimal("250"),
        forecast=Decimal("180"),
    )
    analysis = EconomicIntelligenceEngine.analyze_event(event_beat, historical_stdev=Decimal("30"))
    assert analysis.surprise == Decimal("70")
    assert analysis.surprise_direction == MacroSurpriseDirection.BEAT
    assert analysis.expected_volatility_impact == "HIGH"

    stance_hawk = EconomicIntelligenceEngine.classify_central_bank_stance(rate_change_bps=25, forward_guidance_score=0.4)
    stance_dov = EconomicIntelligenceEngine.classify_central_bank_stance(rate_change_bps=-25, forward_guidance_score=-0.5)
    assert stance_hawk == CentralBankStance.HAWKISH
    assert stance_dov == CentralBankStance.DOVISH


# ---------------------------------------------------------------------------
# 5. Knowledge Graph & Event Graph
# ---------------------------------------------------------------------------

def test_knowledge_graph_supply_chain_shock() -> None:
    kg = FinancialKnowledgeGraph()
    # ASML -> TSM -> NVDA
    kg.add_relation("ASML", RelationType.SUPPLIER_TO, "TSM", weight=Decimal("0.8"))
    kg.add_relation("TSM", RelationType.SUPPLIER_TO, "NVDA", weight=Decimal("0.9"))
    kg.add_relation("NVDA", RelationType.COMPETITOR_OF, "AMD", weight=Decimal("1.0"))

    shocks = kg.propagate_supply_chain_shock("ASML", initial_shock=Decimal("1.0"), max_depth=2, damping_factor=Decimal("0.7"))
    assert len(shocks) == 2
    # Tier 1: TSM (1.0 * 0.8 * 0.7 = 0.56)
    assert shocks[0].entity_id == "TSM"
    assert shocks[0].impact_magnitude == Decimal("0.56")
    # Tier 2: NVDA (0.56 * 0.9 * 0.7 = 0.3528)
    assert shocks[1].entity_id == "NVDA"
    assert shocks[1].impact_magnitude == Decimal("0.3528")


def test_event_graph_impact() -> None:
    asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
    news = NewsEvent(
        headline="Apple reports record iPhone revenue and raised guidance",
        body="...",
        published_at=datetime.now(timezone.utc),
        asset=asset,
        sentiment=Decimal("0.80"),
    )
    node = EventGraphEngine.map_news_to_event(news, category="earnings")
    impact = EventGraphEngine.estimate_asset_impact(node, asset, correlation_or_beta=Decimal("1.1"))

    assert impact.direction == "BULLISH"
    assert impact.expected_price_move_pct > 0


# ---------------------------------------------------------------------------
# 6. Event Study Engine
# ---------------------------------------------------------------------------

def test_event_study_engine() -> None:
    # 50 estimation periods where asset tracks market with beta=1.2, alpha=0.001
    est_m = [0.005 * ((-1) ** i) for i in range(50)]
    est_a = [0.001 + 1.2 * m + 0.0002 for m, i in zip(est_m, range(50))]

    # Event window: positive earnings jump in asset while market is flat
    evt_m = [0.0, 0.0, 0.0]
    evt_a = [0.01, 0.04, 0.02]

    res = EventStudyEngine.run_event_study(
        event_id="AAPL_2026Q2",
        symbol="AAPL",
        estimation_asset_returns=est_a,
        estimation_market_returns=est_m,
        event_asset_returns=evt_a,
        event_market_returns=evt_m,
    )

    assert abs(res.beta - 1.2) < 0.05
    assert res.car > 0.06  # Positive cumulative abnormal return
    assert res.t_statistic > 2.0
    assert res.is_statistically_significant is True


# ---------------------------------------------------------------------------
# 7. Multi-Asset Screener & Natural Language Query
# ---------------------------------------------------------------------------

def test_screener_engine_and_natural_language() -> None:
    universe = [
        {"symbol": "AAPL", "roic": 0.28, "pe_ratio": 28.0, "debt_to_equity": 0.40, "revenue_growth": 0.12},
        {"symbol": "MSFT", "roic": 0.24, "pe_ratio": 32.0, "debt_to_equity": 0.35, "revenue_growth": 0.16},
        {"symbol": "GOOGL", "roic": 0.19, "pe_ratio": 22.0, "debt_to_equity": 0.10, "revenue_growth": 0.14},
        {"symbol": "SPEC_TECH", "roic": 0.05, "pe_ratio": 80.0, "debt_to_equity": 1.50, "revenue_growth": 0.02},
    ]

    # Query: roic > 15%, debt_to_equity < 0.5, pe_ratio <= 30
    query = "roic > 15%, debt_to_equity < 0.5 and pe_ratio <= 30"
    results = NaturalLanguageScreener.execute_query(query, universe, sort_by="roic")

    symbols = [r.symbol for r in results]
    assert "AAPL" in symbols
    assert "GOOGL" in symbols
    assert "MSFT" not in symbols  # PE is 32 > 30
    assert "SPEC_TECH" not in symbols  # ROIC is 5% < 15%
