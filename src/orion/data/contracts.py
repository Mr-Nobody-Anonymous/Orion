from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping
from uuid import UUID, uuid4


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    BOND = "bond"
    FUTURE = "future"
    COMMODITY = "commodity"
    FOREX = "forex"
    CRYPTO = "crypto"
    OPTION = "option"
    VOLATILITY = "volatility"
    PREDICTION_MARKET = "prediction_market"
    ALTERNATIVE = "alternative"


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    HOLD = "HOLD"
    HEDGE = "HEDGE"
    CLOSE = "CLOSE"
    WAIT = "WAIT"
    DO_NOTHING = "DO_NOTHING"


class ExecutionMode(str, Enum):
    BACKTEST = "backtest"
    SIMULATION = "simulation"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class Asset:
    symbol: str
    asset_class: AssetClass
    venue: str | None = None
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class MarketData:
    asset: Asset
    timestamp: datetime
    source: str = "unknown"
    quality: str = "unknown"


@dataclass(frozen=True, slots=True)
class Tick:
    asset: Asset
    timestamp: datetime
    price: Decimal
    size: Decimal = Decimal("0")
    source: str = "unknown"
    quality: str = "unknown"


@dataclass(frozen=True, slots=True)
class MarketQuote:
    asset: Asset
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal = Decimal("0")
    source: str = "unknown"
    quality: str = "unknown"


Quote = MarketQuote


@dataclass(frozen=True, slots=True)
class OHLCV:
    asset: Asset
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    source: str = "unknown"
    quality: str = "unknown"


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    price: Decimal
    quantity: Decimal
    side: Action


@dataclass(frozen=True, slots=True)
class OrderBook:
    asset: Asset
    timestamp: datetime
    bids: tuple[OrderBookLevel, ...] = ()
    asks: tuple[OrderBookLevel, ...] = ()
    source: str = "unknown"
    quality: str = "unknown"


@dataclass(frozen=True, slots=True)
class Trade:
    asset: Asset
    timestamp: datetime
    quantity: Decimal
    price: Decimal
    side: Action
    fee: Decimal = Decimal("0")
    venue: str | None = None
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class FundamentalData:
    asset: Asset
    timestamp: datetime
    fields: Mapping[str, Any]
    source: str = "unknown"
    quality: str = "unknown"


@dataclass(frozen=True, slots=True)
class NewsEvent:
    headline: str
    body: str
    published_at: datetime
    asset: Asset | None = None
    source: str = "unknown"
    sentiment: Decimal | None = None


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    name: str
    timestamp: datetime
    actual: Decimal | None = None
    forecast: Decimal | None = None
    previous: Decimal | None = None
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class OptionContract:
    underlying: Asset
    strike: Decimal
    expiry: datetime
    right: str
    multiplier: Decimal = Decimal("100")


@dataclass(frozen=True, slots=True)
class OptionChain:
    underlying: Asset
    timestamp: datetime
    contracts: tuple[OptionContract, ...] = ()
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class Prediction:
    asset: Asset
    horizon: str
    expected_return: Decimal
    probability_bull: Decimal
    probability_neutral: Decimal
    probability_bear: Decimal
    interval_low: Decimal | None = None
    interval_high: Decimal | None = None
    confidence: Decimal = Decimal("0")
    model_name: str = "unknown"


@dataclass(frozen=True, slots=True)
class Signal:
    name: str
    score: Decimal
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Strategy:
    name: str
    description: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
    universe: tuple[str, ...] = ()
    horizon: str = "1d"


@dataclass(frozen=True, slots=True)
class Order:
    asset: Asset
    quantity: Decimal
    side: Action
    order_type: str = "market"
    limit_price: Decimal | None = None
    client_order_id: str = field(default_factory=lambda: str(uuid4()))
    time_in_force: str = "GTC"


@dataclass(frozen=True, slots=True)
class Position:
    asset: Asset
    quantity: Decimal
    average_price: Decimal = Decimal("0")
    mark_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Portfolio:
    cash: Decimal
    equity: Decimal
    positions: tuple[Position, ...] = ()
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    approved: bool
    reasons: tuple[str, ...] = ()
    approved_quantity: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class Decision:
    action: Action
    rationale: str = ""
    confidence: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    order_id: str
    asset: Asset
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    status: str = "filled"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class Experience:
    asset: str
    prediction: Decimal
    actual_return: Decimal
    model: str
    confidence: Decimal
    regime: str
    features: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class TrainingExample:
    features: dict[str, Any]
    target: Decimal
    asset: str
    regime: str = "unclassified"
    source: str = "orion"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    name: str
    version: str
    kind: str
    dataset_version: str
    metrics: Mapping[str, float] = field(default_factory=dict)
    registry_status: str = "EXPERIMENTAL"
    source: str = "orion"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class TradeProposal:
    order: Order
    prediction: Prediction | None = None
    rationale: str = ""
    correlation: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    payload: Mapping[str, Any]
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    asset_class: AssetClass
    venue: str
    tick_size: Decimal = Decimal("0.01")
    lot_size: Decimal = Decimal("1")
    contract_multiplier: Decimal = Decimal("1")
    currency: str = "USD"
    expiry: datetime | None = None
    strike: Decimal | None = None
    underlying_symbol: str | None = None
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Venue:
    venue_id: str
    name: str
    mic_code: str = ""
    timezone: str = "UTC"
    maker_fee_bps: Decimal = Decimal("10")
    taker_fee_bps: Decimal = Decimal("20")
    is_active: bool = True
    supports_websockets: bool = True
    supports_fix: bool = False


class MarketStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    HALTED = "HALTED"
    AUCTION = "AUCTION"
    PRE_MARKET = "PRE_MARKET"
    POST_MARKET = "POST_MARKET"


@dataclass(frozen=True, slots=True)
class Market:
    market_id: str
    asset: Asset
    venue: str
    status: MarketStatus = MarketStatus.OPEN
    last_price: Decimal = Decimal("0")
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    volume_24h: Decimal = Decimal("0")
    circuit_breaker_active: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class Company:
    symbol: str
    name: str
    cik: str = ""
    lei: str = ""
    sector: str = "General"
    industry: str = "General"
    country: str = "US"
    currency: str = "USD"
    fiscal_year_end_month: int = 12
    description: str = ""


@dataclass(frozen=True, slots=True)
class Security:
    symbol: str
    name: str
    asset_class: AssetClass
    isin: str = ""
    cusip: str = ""
    sedol: str = ""
    figi: str = ""
    primary_exchange: str = ""
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class PredictionMarketContract:
    contract_id: str
    ticker: str
    title: str
    outcome: str
    settlement_source: str
    settlement_time: datetime | None = None
    status: str = "ACTIVE"
    last_price: Decimal = Decimal("0.50")
    bid: Decimal = Decimal("0.49")
    ask: Decimal = Decimal("0.51")


@dataclass(frozen=True, slots=True)
class PredictionMarket:
    market_id: str
    title: str
    category: str
    contracts: tuple[PredictionMarketContract, ...] = ()
    expiration: datetime | None = None
    status: str = "ACTIVE"
    rules: str = ""
    source: str = "kalshi"


@dataclass(frozen=True, slots=True)
class YieldCurvePoint:
    tenor: str
    maturity_years: Decimal
    rate: Decimal
    discount_factor: Decimal = Decimal("1")


@dataclass(frozen=True, slots=True)
class YieldCurve:
    name: str
    currency: str
    timestamp: datetime
    points: tuple[YieldCurvePoint, ...] = ()
    interpolation: str = "cubic_spline"


@dataclass(frozen=True, slots=True)
class FactorExposure:
    factor_name: str
    beta: Decimal
    t_stat: Decimal = Decimal("0")
    p_value: Decimal = Decimal("0")
    specific_risk: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    entry_id: str
    transaction_id: str
    timestamp: datetime
    account_id: str
    debit_account: str
    credit_account: str
    amount: Decimal
    currency: str = "USD"
    description: str = ""
    hash: str = ""


@dataclass(frozen=True, slots=True)
class TaxLot:
    lot_id: str
    asset: Asset
    open_timestamp: datetime
    quantity: Decimal
    cost_basis: Decimal
    remaining_quantity: Decimal
    closed_quantity: Decimal = Decimal("0")
    realized_gain: Decimal = Decimal("0")
    is_short: bool = False


@dataclass(frozen=True, slots=True)
class ResearchDocument:
    doc_id: str
    title: str
    author: str
    symbol: str
    thesis: str
    price_target: Decimal | None = None
    bull_case: str = ""
    bear_case: str = ""
    confidence: Decimal = Decimal("0.5")
    sources: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class AlertNotification:
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    category: str = "system"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    venue: str
    currency: str = "USD"
    cash: Decimal = Decimal("0")
    buying_power: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    margin_type: str = "standard"
    status: str = "ACTIVE"


OrderRequest = Order
RiskDecision = RiskAssessment
MarketBar = OHLCV
Forecast = Prediction
ModelPrediction = Prediction


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Canonical point-in-time cross-asset market snapshot."""

    timestamp: datetime
    quotes: Mapping[str, MarketQuote] = field(default_factory=dict)
    bars: Mapping[str, MarketBar] = field(default_factory=dict)
    order_books: Mapping[str, OrderBook] = field(default_factory=dict)
    regime: str = "unknown"
    data_quality_score: Decimal = Decimal("1.0")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Canonical whole-portfolio snapshot across all asset classes."""

    timestamp: datetime
    cash: Decimal
    equity: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    leverage: Decimal
    positions: tuple[Position, ...] = ()
    currency: str = "USD"
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class RiskMeasurement:
    """Canonical multi-factor risk and tail-loss measurement."""

    timestamp: datetime
    portfolio_id: str
    var_95_pct: Decimal
    cvar_99_pct: Decimal
    volatility_ann_pct: Decimal
    beta: Decimal
    sharpe_ratio: Decimal
    max_drawdown_pct: Decimal
    factor_exposures: Mapping[str, Decimal] = field(default_factory=dict)
    liquidity_days_to_liquidate: Decimal = Decimal("1.0")
    stress_losses: Mapping[str, Decimal] = field(default_factory=dict)
    risk_score: int = 50
    breached_limits: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Scenario:
    """Historical or synthetic macroeconomic crisis scenario."""

    scenario_id: str
    name: str
    description: str
    shocks: Mapping[str, Decimal]  # asset/factor -> percentage shock (e.g. {"equity": -0.30})
    category: str = "historical"  # historical, synthetic, regulatory


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Calculated portfolio stress loss under a scenario."""

    scenario_id: str
    portfolio_loss_pct: Decimal
    portfolio_loss_amount: Decimal
    worst_hit_assets: tuple[str, ...] = ()
    liquidity_impact_pct: Decimal = Decimal("0")
    margin_breach: bool = False


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Pre-trade intention before passing through the 12-Gate Risk Firewall."""

    intent_id: str
    strategy_id: str
    symbol: str
    side: Action
    target_quantity: Decimal
    urgency: str = "medium"  # low, medium, high
    max_slippage_bps: Decimal = Decimal("15")
    limit_price: Decimal | None = None
    venue: str | None = None
    order_type: str = "market"
    rationale: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Algorithmic execution schedule chosen by the Smart Order Router."""

    plan_id: str
    order_intent_id: str
    algorithm: str  # TWAP, VWAP, POV, ICEBERG, DIRECT
    venue: str
    child_slices: int = 1
    slice_interval_seconds: int = 60
    participation_rate: Decimal = Decimal("0.05")
    approved_by_risk_firewall: bool = False
    firewall_trace_id: str = ""


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Deterministic, out-of-sample backtest report."""

    strategy_id: str
    start_date: str
    end_date: str
    cagr_pct: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    max_drawdown_pct: Decimal
    win_rate_pct: Decimal
    profit_factor: Decimal
    total_trades: int
    turnover: Decimal
    slippage_cost_total: Decimal = Decimal("0")
    walk_forward_verified: bool = False
    equity_curve: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class Experiment:
    """Scientific research experiment for alphas, signals, or models."""

    experiment_id: str
    name: str
    hypothesis: str
    model_family: str
    dataset_version: str
    status: str = "COMPLETED"  # RUNNING, COMPLETED, FAILED, PROMOTED
    metrics: Mapping[str, float] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    promoted_to_validation: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """Immutable audit trail for every autonomous decision."""

    decision_id: str
    timestamp: datetime
    strategy_id: str
    model_id: str
    model_version: str
    data_snapshot_id: str
    inputs: Mapping[str, Any]
    outputs: Mapping[str, Any]
    confidence: Decimal
    risk_checks_passed: bool
    compliance_checks_passed: bool
    portfolio_state_summary: Mapping[str, Any] = field(default_factory=dict)
    evidence_citations: tuple[str, ...] = ()
