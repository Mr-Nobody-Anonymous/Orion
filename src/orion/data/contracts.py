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


OrderRequest = Order
RiskDecision = RiskAssessment
