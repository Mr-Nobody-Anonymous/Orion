from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..data.contracts import Asset


class KnowledgeStatus(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    ESTIMATED = "estimated"
    PREDICTED = "predicted"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


@dataclass(frozen=True, slots=True)
class StateValue:
    value: Any
    status: KnowledgeStatus
    source: str
    confidence: float
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Relationship:
    subject: str
    predicate: str
    object: str
    observed_at: datetime
    source: str
    confidence: float


@dataclass(slots=True)
class MarketState:
    regime: StateValue = field(default_factory=lambda: StateValue("unknown", KnowledgeStatus.UNKNOWN, "orion", 0.0))
    volatility: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "orion", 0.0))
    liquidity: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "orion", 0.0))
    data_quality: StateValue = field(default_factory=lambda: StateValue("unknown", KnowledgeStatus.UNKNOWN, "orion", 0.0))


@dataclass(slots=True)
class PortfolioState:
    equity: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "broker", 0.0))
    exposure: StateValue = field(default_factory=lambda: StateValue(0.0, KnowledgeStatus.ESTIMATED, "broker", 0.5))
    open_positions: StateValue = field(default_factory=lambda: StateValue({}, KnowledgeStatus.KNOWN, "broker", 1.0))


@dataclass(slots=True)
class AgentState:
    health: StateValue = field(default_factory=lambda: StateValue("healthy", KnowledgeStatus.KNOWN, "orion", 1.0))
    active_tools: StateValue = field(default_factory=lambda: StateValue((), KnowledgeStatus.KNOWN, "orion", 1.0))


@dataclass(slots=True)
class ResearchState:
    question: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "orion", 0.0))
    evidence_count: StateValue = field(default_factory=lambda: StateValue(0, KnowledgeStatus.KNOWN, "orion", 1.0))


@dataclass(slots=True)
class ModelState:
    confidence: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "orion", 0.0))
    disagreement: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "orion", 0.0))


@dataclass(slots=True)
class RiskState:
    approved: StateValue = field(default_factory=lambda: StateValue(False, KnowledgeStatus.UNKNOWN, "risk", 0.0))
    reasons: StateValue = field(default_factory=lambda: StateValue((), KnowledgeStatus.UNKNOWN, "risk", 0.0))


@dataclass(slots=True)
class DecisionState:
    action: StateValue = field(default_factory=lambda: StateValue("WAIT", KnowledgeStatus.KNOWN, "orion", 1.0))
    rationale: StateValue = field(default_factory=lambda: StateValue("", KnowledgeStatus.UNKNOWN, "orion", 0.0))


@dataclass(slots=True)
class LearningState:
    experience_count: StateValue = field(default_factory=lambda: StateValue(0, KnowledgeStatus.KNOWN, "orion", 1.0))
    last_error: StateValue = field(default_factory=lambda: StateValue(None, KnowledgeStatus.UNKNOWN, "orion", 0.0))


class FinancialWorldModel:
    """Explicit situational state; uncertainty is retained with every observation."""

    def __init__(self) -> None:
        self.assets: dict[str, Asset] = {}
        self.relationships: list[Relationship] = []
        self.state: dict[str, StateValue] = {}
        self.market = MarketState()
        self.portfolio = PortfolioState()
        self.agent = AgentState()
        self.research = ResearchState()
        self.models = ModelState()
        self.risk = RiskState()
        self.decision = DecisionState()
        self.learning = LearningState()

    def register_asset(self, asset: Asset) -> None:
        self.assets[asset.symbol] = asset

    def set_state(self, key: str, value: Any, *, status: KnowledgeStatus = KnowledgeStatus.KNOWN,
                  source: str = "orion", confidence: float = 1.0) -> StateValue:
        observation = StateValue(value, status, source, confidence)
        self.state[key] = observation
        return observation

    def relate(self, subject: str, predicate: str, object_: str, source: str, confidence: float) -> Relationship:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        relationship = Relationship(subject, predicate, object_, datetime.now(timezone.utc), source, confidence)
        self.relationships.append(relationship)
        return relationship

    def update_market(self, returns: list[float], *, quality: str, source: str) -> MarketState:
        if not returns:
            self.market.regime = StateValue("unknown", KnowledgeStatus.UNKNOWN, source, 0.0)
            return self.market
        average = sum(returns) / len(returns)
        variance = sum((item - average) ** 2 for item in returns) / len(returns)
        volatility = variance ** 0.5
        regime = "bull" if average > 0 and volatility < 0.03 else "bear" if average < 0 and volatility < 0.03 else "volatile"
        self.market.regime = StateValue(regime, KnowledgeStatus.ESTIMATED, source, min(0.9, 0.4 + len(returns) / 100))
        self.market.volatility = StateValue(volatility, KnowledgeStatus.ESTIMATED, source, self.market.regime.confidence)
        self.market.data_quality = StateValue(quality, KnowledgeStatus.KNOWN, source, 1.0)
        return self.market
