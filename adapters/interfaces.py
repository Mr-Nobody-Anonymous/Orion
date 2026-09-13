"""ORION Canonical Adapter Interfaces and Contracts.

Defines the formal abstract contracts (Protocols) that all external computing engine
adapters must implement to plug into the Orion financial operating system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from orion.data.contracts import (
    BacktestResult,
    ExecutionPlan,
    ExecutionReport,
    Forecast,
    Instrument,
    MarketBar,
    MarketSnapshot,
    ModelPrediction,
    OrderBook,
    OrderIntent,
    PortfolioSnapshot,
    Position,
    ResearchDocument,
    RiskMeasurement,
    Scenario,
    ScenarioResult,
)


@runtime_checkable
class MarketDataProvider(Protocol):
    """Interface for real-time and historical market data adapters."""

    def get_bars(
        self,
        instrument: Instrument,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> Sequence[MarketBar]:
        """Fetch normalized OHLCV market bars."""
        ...

    def get_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        """Fetch top-of-book market snapshot."""
        ...

    def get_order_book(self, instrument: Instrument, depth: int = 50) -> OrderBook:
        """Fetch depth-of-book order book."""
        ...


@runtime_checkable
class ResearchProvider(Protocol):
    """Interface for fundamental research, SEC filings, and alternative data."""

    def ingest_documents(
        self,
        symbol: str,
        doc_type: str = "10-K",
        limit: int = 5,
    ) -> Sequence[ResearchDocument]:
        """Ingest and normalize company filings or earnings transcripts."""
        ...

    def search_news(self, query: str, limit: int = 10) -> Sequence[ResearchDocument]:
        """Search and extract news articles with sentiment tagging."""
        ...


@runtime_checkable
class ForecastEngine(Protocol):
    """Interface for statistical, machine learning, and time-series forecasting engines."""

    def generate_forecast(
        self,
        instrument: Instrument,
        history: Sequence[MarketBar],
        horizon_bars: int = 5,
    ) -> Forecast:
        """Generate a probabilistic return forecast with confidence bounds."""
        ...


@runtime_checkable
class BacktestEngine(Protocol):
    """Interface for event-driven, vector, and simulation backtesting engines."""

    def run_backtest(
        self,
        strategy_id: str,
        universe: Sequence[Instrument],
        start: datetime,
        end: datetime,
        params: Mapping[str, Any] | None = None,
    ) -> BacktestResult:
        """Execute a rigorous backtest run with transaction costs and slippage."""
        ...


@runtime_checkable
class PortfolioOptimizer(Protocol):
    """Interface for portfolio construction and mathematical optimization engines."""

    def optimize_weights(
        self,
        expected_returns: Mapping[str, float],
        covariance: Mapping[str, Mapping[str, float]],
        method: str = "max_sharpe",
        constraints: Mapping[str, Any] | None = None,
    ) -> Mapping[str, float]:
        """Compute optimal asset target weights subject to institutional constraints."""
        ...


@runtime_checkable
class RiskEngine(Protocol):
    """Interface for multi-factor, parametric, historical, and stress risk engines."""

    def calculate_risk(self, portfolio: PortfolioSnapshot) -> RiskMeasurement:
        """Calculate VaR, CVaR, factor exposures, and portfolio volatility."""
        ...

    def stress_test(
        self,
        portfolio: PortfolioSnapshot,
        scenario: Scenario,
    ) -> ScenarioResult:
        """Evaluate portfolio loss and margin impact under severe stress scenarios."""
        ...


@runtime_checkable
class ExecutionEngine(Protocol):
    """Interface for algorithmic trade planning and smart order routing."""

    def plan_execution(self, intent: OrderIntent) -> ExecutionPlan:
        """Translate pre-trade intent into a staged multi-tranche execution plan."""
        ...


@runtime_checkable
class BrokerAdapter(Protocol):
    """Interface for broker venue order placement, fills, and account balances."""

    def submit_order(self, plan: ExecutionPlan) -> ExecutionReport:
        """Submit an order to a broker venue (dry-run or live)."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open resting order."""
        ...

    def get_positions(self) -> Sequence[Position]:
        """Fetch current open broker positions."""
        ...


@runtime_checkable
class ExchangeAdapter(Protocol):
    """Interface for direct exchange and crypto liquidity venues (e.g., CCXT)."""

    def fetch_ticker(self, symbol: str) -> MarketSnapshot:
        """Fetch 24-hour ticker snapshot."""
        ...

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
    ) -> ExecutionReport:
        """Place a limit order directly on venue matching engine."""
        ...


@runtime_checkable
class ModelProvider(Protocol):
    """Interface for financial NLP, foundation models, and neural network inference."""

    def predict(self, inputs: Mapping[str, Any]) -> ModelPrediction:
        """Execute forward inference and return prediction with confidence interval."""
        ...

    def get_model_metadata(self) -> Mapping[str, Any]:
        """Return model version, training cutoff date, and latency benchmarks."""
        ...
