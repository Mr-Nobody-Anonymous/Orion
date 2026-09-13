"""Tests for Phase 4: Aladdin Layer.

Covers:
- Aladdin-style Parametric, Historical, Monte Carlo VaR/CVaR, and Historical Crisis Stress Tests
- Fixed income bond pricing, Macaulay/Modified duration, DV01, convexity, and CDS default intensity
- Cryptographically chained immutable double-entry accounting ledger
- Tax-lot relief strategies (FIFO, HIFO) and IRS wash sale loss disallowance
- Automated multi-venue position and cash reconciliation
- Multi-asset market regime classification
- Black-Litterman Bayesian portfolio optimization
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from orion.data.contracts import Asset, AssetClass
from orion.markets.fixed_income.pricing import FixedIncomeEngine
from orion.markets.regime.classifier import (
    MarketRegimeEngine,
    MarketTrendRegime,
    VolatilityRegime,
)
from orion.portfolio.ledger import DoubleEntryLedger, JournalLine
from orion.portfolio.optimizer.black_litterman import BlackLittermanEngine
from orion.portfolio.reconciliation import ReconciliationEngine
from orion.portfolio.tax import TaxDisposalStrategy, TaxLotManager
from orion.trading.aladdin_risk import AladdinRiskEngine


# ---------------------------------------------------------------------------
# 1. Aladdin-Class Risk Engine & Stress Testing
# ---------------------------------------------------------------------------

def test_aladdin_var_and_stress_testing() -> None:
    portfolio_val = Decimal("1000000.00")  # $1M portfolio
    # 250 daily return observations (mean ~0.0004, stdev ~0.012)
    daily_returns = [0.0004 + 0.012 * ((-1) ** i) * (0.8 + 0.4 * (i % 5) / 5) for i in range(250)]

    var_metrics = AladdinRiskEngine.calculate_var_metrics(
        portfolio_value=portfolio_val,
        daily_returns=daily_returns,
        confidence_level=0.95,
        horizon_days=1,
    )

    assert var_metrics.parametric_var > Decimal("10000")
    assert var_metrics.parametric_cvar > var_metrics.parametric_var
    assert var_metrics.historical_var > 0
    assert var_metrics.monte_carlo_var > 0
    assert var_metrics.liquidity_adjusted_var > var_metrics.parametric_var

    # Stress testing: 2008 Lehman Crisis
    allocations = {"equity": Decimal("0.70"), "crypto": Decimal("0.10"), "bond": Decimal("0.20")}
    res_2008 = AladdinRiskEngine.run_stress_test(portfolio_val, allocations, "2008_LEHMAN_CRISIS")
    assert res_2008.percentage_loss > Decimal("20.0")  # Substantial drawdown
    assert res_2008.dollar_loss > Decimal("200000")
    assert res_2008.liquidity_shortfall_risk is False

    # Stress testing: 2020 COVID Crash
    res_covid = AladdinRiskEngine.run_stress_test(portfolio_val, allocations, "2020_COVID_CRASH")
    assert res_covid.percentage_loss > Decimal("25.0")
    assert res_covid.liquidity_shortfall_risk is True


# ---------------------------------------------------------------------------
# 2. Fixed Income Pricing, Duration, and CDS
# ---------------------------------------------------------------------------

def test_fixed_income_engine() -> None:
    # 10-year Treasury, $1,000 par, 4% annual coupon (semi-annual), 4.5% YTM
    bond = FixedIncomeEngine.price_coupon_bond(
        par_value=Decimal("1000"),
        annual_coupon_rate=Decimal("0.04"),
        ytm=Decimal("0.045"),
        years_to_maturity=Decimal("10"),
        frequency=2,
    )

    # Trading at discount since coupon 4.0% < YTM 4.5%
    assert bond.clean_price < Decimal("1000")
    assert bond.clean_price > Decimal("900")
    # Modified duration for 10-yr bond is typically between 7 and 9
    assert Decimal("7.0") < bond.modified_duration < Decimal("9.0")
    assert bond.dv01 > Decimal("0.60")
    assert bond.convexity > 0

    # CDS Spread metrics: 120 bps spread, 40% recovery
    cds = FixedIncomeEngine.calculate_cds_metrics(spread_bps=Decimal("120"), recovery_rate=Decimal("0.40"))
    # Hazard rate lambda = 0.0120 / (1 - 0.40) = 0.0200 (2.0% annual default intensity)
    assert cds.hazard_rate == Decimal("0.0200")
    assert Decimal("0.97") < cds.survival_prob_1y < Decimal("0.99")
    assert Decimal("0.89") < cds.survival_prob_5y < Decimal("0.92")


# ---------------------------------------------------------------------------
# 3. Double-Entry Accounting Ledger
# ---------------------------------------------------------------------------

def test_double_entry_ledger() -> None:
    ledger = DoubleEntryLedger()

    # Initial funding: Debit Cash $100k, Credit Capital $100k
    t1 = ledger.record_transaction(
        tx_id="tx_001",
        description="Capital Contribution",
        lines=[
            JournalLine(account="ASSETS:CASH", debit=Decimal("100000")),
            JournalLine(account="EQUITY:CAPITAL", credit=Decimal("100000")),
        ],
    )
    assert ledger.get_account_balance("ASSETS:CASH") == Decimal("100000")
    assert ledger.get_account_balance("EQUITY:CAPITAL") == Decimal("-100000")  # Credit balance
    assert ledger.check_trial_balance() is True
    assert ledger.verify_integrity() is True

    # Purchase AAPL: Debit AAPL $20k, Credit Cash $20k
    t2 = ledger.record_transaction(
        tx_id="tx_002",
        description="Buy 100 AAPL @ $200",
        lines=[
            JournalLine(account="ASSETS:EQUITY:AAPL", debit=Decimal("20000")),
            JournalLine(account="ASSETS:CASH", credit=Decimal("20000")),
        ],
    )
    assert ledger.get_account_balance("ASSETS:CASH") == Decimal("80000")
    assert ledger.get_account_balance("ASSETS:EQUITY:AAPL") == Decimal("20000")
    assert ledger.check_trial_balance() is True
    assert ledger.verify_integrity() is True

    # Unbalanced transaction rejected
    with pytest.raises(ValueError, match="Unbalanced transaction"):
        ledger.record_transaction(
            tx_id="tx_003",
            description="Broken entry",
            lines=[
                JournalLine(account="ASSETS:CASH", debit=Decimal("5000")),
                JournalLine(account="EQUITY:CAPITAL", credit=Decimal("4000")),
            ],
        )


# ---------------------------------------------------------------------------
# 4. Tax Engine & Lot Relief (FIFO / Wash Sale)
# ---------------------------------------------------------------------------

def test_tax_engine_and_wash_sale() -> None:
    mgr = TaxLotManager(strategy=TaxDisposalStrategy.FIFO)
    asset = Asset(symbol="NVDA", asset_class=AssetClass.EQUITY)

    t0 = datetime(2025, 1, 15, tzinfo=timezone.utc)
    t1 = datetime(2026, 2, 1, tzinfo=timezone.utc)  # > 1 year (Long-term)
    t2 = datetime(2026, 3, 1, tzinfo=timezone.utc)  # Within 30 days of purchase below (Wash sale)
    t3 = datetime(2026, 3, 10, tzinfo=timezone.utc) # Repurchase within 30 days

    # Lot 1: 50 shares @ $100
    mgr.add_lot(asset, Decimal("50"), Decimal("100"), t0)
    # Lot 2: 50 shares @ $150
    mgr.add_lot(asset, Decimal("50"), Decimal("150"), t1)

    # Sale 1 (FIFO matches Lot 1): Sell 50 @ $180 (Gain: ($180 - $100) * 50 = +$4,000, Long-term)
    sale1 = mgr.match_sale(asset, Decimal("50"), Decimal("180"), sale_timestamp=t1 + timedelta(days=20))
    assert len(sale1) == 1
    assert sale1[0].realized_gain_loss == Decimal("4000")
    assert sale1[0].is_long_term is True
    assert sale1[0].is_wash_sale is False

    # Repurchase 20 shares at t3
    mgr.add_lot(asset, Decimal("20"), Decimal("110"), t3)

    # Sale 2: Sell remaining Lot 2 (50 shares @ $150) at $120 -> Loss of -$30/share = -$1500
    # Because t3 repurchase was within 30 days, wash sale rule triggers!
    sale2 = mgr.match_sale(asset, Decimal("50"), Decimal("120"), sale_timestamp=t2)
    assert len(sale2) == 1
    assert sale2[0].is_wash_sale is True
    assert sale2[0].disallowed_loss == Decimal("1500")


# ---------------------------------------------------------------------------
# 5. Automated Multi-Venue Reconciliation
# ---------------------------------------------------------------------------

def test_reconciliation_engine() -> None:
    int_pos = {"AAPL": Decimal("100"), "MSFT": Decimal("200"), "NVDA": Decimal("50")}
    brk_pos = {"AAPL": Decimal("100"), "MSFT": Decimal("200"), "NVDA": Decimal("45")}  # NVDA broke by 5

    report = ReconciliationEngine.reconcile(
        venue="Alpaca",
        internal_positions=int_pos,
        broker_positions=brk_pos,
        internal_cash=Decimal("50000.00"),
        broker_cash=Decimal("50000.00"),
    )

    assert report.is_clean is False
    assert len(report.breaks) == 1
    assert report.breaks[0].identifier == "NVDA"
    assert report.breaks[0].discrepancy == Decimal("-5")
    assert report.breaks[0].severity == "CRITICAL"
    assert report.matched_positions_count == 2
    assert report.matched_cash_accounts_count == 1


# ---------------------------------------------------------------------------
# 6. Market Regime Engine
# ---------------------------------------------------------------------------

def test_market_regime_engine() -> None:
    # 30 days of rising prices with low volatility
    bull_prices = [100.0 * (1.0 + 0.005 * i) for i in range(30)]
    regime = MarketRegimeEngine.classify_regime(bull_prices, high_yield_spread_bps=280.0)

    assert regime.trend_regime == MarketTrendRegime.BULL
    assert regime.volatility_regime == VolatilityRegime.LOW_VOLATILITY
    assert regime.macro_regime.value == "RISK_ON"
    assert regime.recommended_leverage_multiplier >= Decimal("1.0")


# ---------------------------------------------------------------------------
# 7. Black-Litterman Portfolio Optimizer
# ---------------------------------------------------------------------------

def test_black_litterman_engine() -> None:
    assets = ["SPY", "TLT", "GLD"]
    caps = [1000.0, 300.0, 200.0]  # Market cap weights: SPY 66.7%, TLT 20%, GLD 13.3%
    cov = [
        [0.04, 0.005, 0.002],
        [0.005, 0.02, 0.001],
        [0.002, 0.001, 0.03],
    ]

    # Without views: weights reflect market cap weights
    base_res = BlackLittermanEngine.optimize(assets, caps, cov)
    assert base_res.optimal_weights["SPY"] > base_res.optimal_weights["TLT"]

    # With strong bullish view on GLD (expected return 20% with 90% confidence)
    views = {"GLD": 0.20}
    confs = {"GLD": 0.90}
    bl_res = BlackLittermanEngine.optimize(assets, caps, cov, views=views, view_confidences=confs)

    # GLD weight should expand significantly
    assert bl_res.posterior_expected_returns["GLD"] > bl_res.equilibrium_returns["GLD"]
    assert bl_res.optimal_weights["GLD"] > base_res.optimal_weights["GLD"]
