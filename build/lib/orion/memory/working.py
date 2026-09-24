"""Working memory: the executive's short-lived, bounded attention buffer.

Working memory holds what the executive brain is reasoning about *right now*.
When it overflows, the least salient items are compressed into summaries and
handed to episodic memory rather than being silently dropped, so no
observation ever disappears without leaving a trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .layered import LayeredMemory, MemoryItem, MemoryLayer

__all__ = ["WorkingItem", "WorkingMemory"]


@dataclass(frozen=True, slots=True)
class WorkingItem:
    key: str
    content: dict[str, Any]
    summary: str
    importance: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def salience(self, now: datetime | None = None) -> float:
        """Importance decaying with age: newer, more important items win."""
        now = now or datetime.now(timezone.utc)
        age_seconds = max(0.0, (now - self.created_at).total_seconds())
        decay = 0.5 ** (age_seconds / 900.0)  # 15-minute half-life
        return self.importance * decay


class WorkingMemory:
    """A bounded attention buffer with salience-based eviction.

    Eviction policy: the lowest-salience item is demoted to episodic memory
    (compressed to its summary) whenever the buffer exceeds `capacity`.
    """

    def __init__(
        self,
        capacity: int = 16,
        episodic: LayeredMemory | None = None,
        compressor: Callable[[WorkingItem], str] | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._episodic = episodic
        self._compressor = compressor or (lambda item: item.summary)
        self._items: dict[str, WorkingItem] = {}

    def push(self, key: str, content: dict[str, Any], summary: str, importance: float = 0.5) -> WorkingItem:
        if not 0 <= importance <= 1:
            raise ValueError("importance must be between 0 and 1")
        item = WorkingItem(key=key, content=dict(content), summary=summary, importance=importance)
        self._items[key] = item  # re-push refreshes timestamp and salience
        while len(self._items) > self.capacity:
            self._evict_one()
        return item

    def get(self, key: str) -> WorkingItem | None:
        return self._items.get(key)

    def focus(self, limit: int = 5) -> tuple[WorkingItem, ...]:
        """The most salient items, in descending order of salience."""
        now = datetime.now(timezone.utc)
        ranked = sorted(self._items.values(), key=lambda i: i.salience(now), reverse=True)
        return tuple(ranked[:limit])

    def recall(self, query: str, limit: int = 5) -> tuple[WorkingItem, ...]:
        """Keyword-relevant items from the current buffer only."""
        terms = {t.lower() for t in query.split() if t}
        scored: list[tuple[float, WorkingItem]] = []
        for item in self._items.values():
            haystack = f"{item.summary} {item.key}".lower()
            matched = sum(t in haystack for t in terms)
            if matched:
                scored.append((matched * 2 + item.importance, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return tuple(item for _, item in scored[:limit])

    def context_brief(self, limit: int = 5) -> dict[str, Any]:
        """A compact situational snapshot for the executive's prompt/state."""
        return {
            "items": [
                {"key": i.key, "summary": i.summary, "importance": round(i.importance, 3)}
                for i in self.focus(limit)
            ],
            "load": len(self._items),
            "capacity": self.capacity,
        }

    def _evict_one(self) -> None:
        now = datetime.now(timezone.utc)
        victim_key = min(self._items, key=lambda k: self._items[k].salience(now))
        victim = self._items.pop(victim_key)
        if self._episodic is not None:
            self._episodic.remember(
                MemoryLayer.EPISODIC,
                {"key": victim.key, "compressed_from": "working", "content": victim.content},
                summary=self._compressor(victim),
                tags={"evicted_working", victim.key},
                importance=max(0.1, victim.importance * 0.5),
            )

    def __len__(self) -> int:
        return len(self._items)


# Keep the LayeredMemory types importable from here for convenience.
__all__ += ["LayeredMemory", "MemoryItem", "MemoryLayer"]
