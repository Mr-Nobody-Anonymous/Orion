from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryLayer(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    MARKET = "market"
    RESEARCH = "research"
    TRADING = "trading"


@dataclass(frozen=True, slots=True)
class MemoryItem:
    layer: MemoryLayer
    content: dict[str, Any]
    summary: str
    tags: frozenset[str] = frozenset()
    importance: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not 0 <= self.importance <= 1:
            raise ValueError("importance must be between 0 and 1")


class LayeredMemory:
    """Bounded semantic retrieval over concise observations, not raw-data hoarding."""

    def __init__(self, working_limit: int = 32) -> None:
        self.working_limit = working_limit
        self._items: dict[MemoryLayer, list[MemoryItem]] = {layer: [] for layer in MemoryLayer}

    def remember(self, layer: MemoryLayer, content: dict[str, Any], *, summary: str,
                 tags: set[str] | None = None, importance: float = 0.5) -> MemoryItem:
        item = MemoryItem(layer, dict(content), summary, frozenset(tags or set()), importance)
        items = self._items[layer]
        items.append(item)
        if layer is MemoryLayer.WORKING and len(items) > self.working_limit:
            oldest = items.pop(0)
            self._items[MemoryLayer.EPISODIC].append(
                MemoryItem(MemoryLayer.EPISODIC, oldest.content, oldest.summary, oldest.tags, oldest.importance)
            )
        return item

    def retrieve(self, query: str, *, layers: tuple[MemoryLayer, ...] | None = None, limit: int = 5) -> tuple[MemoryItem, ...]:
        query_terms = {term.lower() for term in query.split() if term}
        candidates = [item for layer in (layers or tuple(MemoryLayer)) for item in self._items[layer]]
        def score(item: MemoryItem) -> tuple[float, datetime]:
            haystack = f"{item.summary} {' '.join(item.tags)}".lower()
            matched = sum(term in haystack for term in query_terms)
            return (matched * 2 + item.importance, item.created_at)
        return tuple(sorted(candidates, key=score, reverse=True)[:limit])

    def counts(self) -> dict[str, int]:
        return {layer.value: len(items) for layer, items in self._items.items()}
