"""Test suite for the Orion Capability Layer, Router, Councils, and Contracts."""

from __future__ import annotations

import pytest

from orion.capabilities.backtesting import (
    BacktestProvider,
    BacktestRequest,
    BacktestResult,
    ParameterSweepRequest,
)
from orion.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from orion.capabilities.councils import (
    CouncilForecastResult,
    ForecastCouncil,
    RiskCouncil,
    RiskCouncilResult,
)
from orion.capabilities.execution import ExecutionRequest, ExecutionResponse
from orion.capabilities.fixed_income import (
    BondPricingRequest,
    YieldCurveRequest,
)
from orion.capabilities.forecasting import (
    ForecastRequest,
    ForecastResult,
    ForecastingProvider,
)
from orion.capabilities.options import (
    OptionPricingRequest,
)
from orion.capabilities.prediction_markets import PMDiscoveryRequest
from orion.capabilities.reinforcement_learning import RLPolicyRequest
from orion.capabilities.router import CapabilityRouter
from orion.capabilities.sentiment import SentimentAnalysisRequest
from orion.integrations.financial_llm.fingpt import OrionNativeSentimentAnalyzer
from orion.integrations.forecasting.kronos import OrionNativeForecaster
from orion.integrations.mathematics.py_vollib import OrionNativeBlackScholes
from orion.integrations.mathematics.quantlib import OrionNativeBondPricer
from orion.integrations.prediction_markets.toolkit import OrionNativePMOrderBook
from orion.integrations.trading.finrl import OrionNativeRLBenchmark
from orion.integrations.trading.vectorbt import OrionNativeBacktester


class FailingProvider(ForecastingProvider):
    """Simulated failing provider to test fallback guarantee."""

    @property
    def name(self) -> str:
        return "mock_failing_provider"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.ADAPTER

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="1.0.0",
            latency_ms=1.0,
        )

    def capabilities(self) -> tuple[str, ...]:
        return ("failing_forecast",)

    def forecast(self, request: ForecastRequest) -> ForecastResult:
        raise RuntimeError("External network connection timed out")


def test_capability_router_fallback_guarantee():
    """Verify that an error in a primary provider triggers the native fallback transparently."""
    router = CapabilityRouter()
    failing = FailingProvider()
    native = OrionNativeForecaster()

    router.register_provider(failing)
    router.register_provider(native)

    req = ForecastRequest(
        symbol="NVDA",
        prices=[100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        horizon_steps=5,
    )

    # Executing preferred failing provider must fall back to native without crashing
    res, audit = router.execute_with_fallback(
        category=CapabilityCategory.FORECASTING,
        preferred_provider_name="mock_failing_provider",
        operation=lambda p: p.forecast(req),  # type: ignore
    )

    assert res is not None
    assert res.predicted_return != 0.0 or res.confidence > 0.0
    assert audit.fallback_used is True
    assert audit.selected_provider == "orion_native_forecast"
    assert audit.success is True


def test_forecast_council_consensus():
    """Verify Forecast Council combines multi-engine predictions with concordance weights."""
    router = CapabilityRouter()
    native_fc = OrionNativeForecaster()
    router.register_provider(native_fc)

    council = ForecastCouncil(router)

    req = ForecastRequest(
        symbol="BTC",
        prices=[60000.0, 61000.0, 62000.0, 63000.0, 64000.0],
        horizon_steps=3,
    )

    delib = council.deliberate(req)
    assert delib.symbol == "BTC"
    assert delib.ensemble_confidence >= 0.0
    assert delib.model_concordance_pct >= 0.0
    assert len(delib.contributing_models) >= 1
    assert delib.contributing_models[0]["engine"] == "orion_native_forecast"


def test_risk_council_deliberation():
    """Verify Risk Council evaluates VaR, CVaR, and risk limits."""
    router = CapabilityRouter()
    council = RiskCouncil(router)

    assessment = council.evaluate_risk(
        portfolio_value=100_000.0,
        equity_series=[100_000.0, 101_000.0, 99_500.0, 102_000.0, 103_500.0],
    )
    assert assessment.portfolio_risk_score >= 0.0
    assert assessment.var_95 >= 0.0
    assert assessment.cvar_99 >= assessment.var_95


def test_native_backtester_metrics():
    """Verify OrionNativeBacktester computes Sharpe, Sortino, Drawdown, and Equity curve."""
    backtester = OrionNativeBacktester()
    prices = [100.0, 102.0, 101.0, 105.0, 107.0, 106.0, 110.0, 112.0, 115.0]
    signals = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]

    req = BacktestRequest(
        strategy_name="TrendFollowing",
        symbol="SPY",
        prices=prices,
        signals=signals,
        initial_capital=100_000.0,
    )

    result = backtester.run_backtest(req)
    assert result.provider_name == "orion_native_backtest"
    assert result.total_return_pct > 0.0
    assert result.cagr_pct > 0.0
    assert result.sharpe_ratio > 0.0
    assert len(result.equity_curve) == len(prices)


def test_native_black_scholes():
    """Verify OrionNativeBlackScholes computes call/put prices and Greeks."""
    pricer = OrionNativeBlackScholes()
    req = OptionPricingRequest(
        underlying_price=100.0,
        strike_price=100.0,
        time_to_expiry_years=1.0,
        volatility=0.20,
        risk_free_rate=0.05,
        is_call=True,
    )

    greeks = pricer.calculate_greeks(req)
    assert 0.0 < greeks.price < 100.0
    assert 0.5 < greeks.delta < 0.7
    assert greeks.gamma > 0.0
    assert greeks.vega > 0.0

    iv = pricer.calculate_implied_volatility(
        market_price=greeks.price,
        underlying_price=100.0,
        strike=100.0,
        time_to_expiry=1.0,
        risk_free_rate=0.05,
        is_call=True,
    )
    assert abs(iv.implied_vol - 0.20) < 0.01


def test_native_bond_pricer():
    """Verify OrionNativeBondPricer calculates bond duration and yield curves."""
    pricer = OrionNativeBondPricer()
    req = BondPricingRequest(
        face_value=1000.0,
        coupon_rate_pct=5.0,
        years_to_maturity=10.0,
        yield_to_maturity_pct=5.0,
        frequency=2,
    )

    res = pricer.price_bond(req)
    assert abs(res.clean_price - 1000.0) < 0.01
    assert 7.0 < res.macaulay_duration_years < 8.5
    assert res.convexity > 0.0
