"""Base types for the ORION agent hierarchy (P2-2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class AgentRole(str, Enum):
    COMPLIANCE = "compliance"
    RISK = "risk"
    DECISION = "decision"
    RESEARCHER = "researcher"
    QUANT = "quant"
    NEWS = "news"
    STRATEGY = "strategy"


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Read-only input that an agent inspects to produce a decision."""

    symbol: str
    asset_class: str
    prices: Sequence[float]
    predictions: Sequence[Mapping[str, Any]] = ()
    signals: Sequence[Mapping[str, Any]] = ()
    news: Sequence[Mapping[str, Any]] = ()
    risk_limits: Mapping[str, float] = field(default_factory=dict)
    portfolio: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """A single agent's verdict on a candidate action."""

    role: AgentRole
    verdict: str  # "ALLOW" | "BLOCK" | "NEEDS_REVIEW" | "INFORM"
    reasons: tuple[str, ...]
    metrics: Mapping[str, float] = field(default_factory=dict)
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
            "notes": self.notes,
        }


class Agent:
    """Abstract agent: subclasses must implement :meth:`evaluate`."""

    role: AgentRole

    def evaluate(self, context: AgentContext) -> AgentDecision:
        raise NotImplementedError("subclasses must implement evaluate()")
