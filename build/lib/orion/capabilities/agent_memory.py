"""Agent memory, reflection, and skill retrieval capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class MemoryRetrievalRequest:
    """Request to search memory stores for similar historical regimes/mistakes."""

    query: str
    symbol: str | None = None
    regime: str | None = None
    top_k: int = 5


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A stored unit of experience or rule."""

    record_id: str
    kind: str  # lesson, pattern, trade_mistake, market_regime
    summary: str
    similarity_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryStoreResult:
    """Result of querying memory."""

    provider_name: str
    total_records: int
    matches: tuple[MemoryRecord, ...]


class AgentMemoryProvider(BaseCapabilityProvider):
    """Abstract interface for episodic and reflection memory (Hermes / Orion native)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.AGENT_MEMORY

    @abstractmethod
    def search_memory(self, request: MemoryRetrievalRequest) -> MemoryStoreResult:
        """Retrieve relevant past lessons or market regimes."""

    @abstractmethod
    def record_experience(self, record: MemoryRecord) -> bool:
        """Store a new trading lesson or reflection."""
