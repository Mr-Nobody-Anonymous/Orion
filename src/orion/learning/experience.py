"""Prioritized experience replay.

Experiences (observation → prediction → decision → outcome) become training
material only through this bounded, prioritized buffer. High-error samples
are sampled more often, but never exclusively: uniform exploration is
reserved by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from random import Random
from typing import Any


@dataclass(frozen=True, slots=True)
class ReplayItem:
    asset: str
    features: dict[str, Any]
    prediction: Decimal
    actual_return: Decimal
    model: str
    regime: str
    stored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def error(self) -> Decimal:
        return abs(self.actual_return - self.prediction)


class ExperienceReplay:
    """Bounded prioritized replay buffer with deterministic sampling."""

    def __init__(self, *, capacity: int = 5000, priority_exponent: float = 1.0, seed: int = 7) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least one")
        if priority_exponent < 0:
            raise ValueError("priority_exponent must be non-negative")
        self.capacity = capacity
        self.priority_exponent = priority_exponent
        self._items: list[ReplayItem] = []
        self._rng = Random(seed)

    def append(self, item: ReplayItem) -> None:
        self._items.append(item)
        if len(self._items) > self.capacity:
            # Drop the oldest: recency is guaranteed by the buffer order.
            self._items.pop(0)

    def __len__(self) -> int:
        return len(self._items)

    def priorities(self) -> tuple[float, ...]:
        """Priority = (error + epsilon)^exponent; uniform when exponent is 0."""
        return tuple(
            (float(item.error) + 1e-6) ** self.priority_exponent if self.priority_exponent > 0 else 1.0
            for item in self._items
        )

    def sample(self, count: int) -> tuple[ReplayItem, ...]:
        """Prioritized sample without replacement; falls back to uniform when
        all priorities are equal. Raises when the buffer is too small."""
        if count < 1:
            raise ValueError("count must be at least one")
        if count > len(self._items):
            raise ValueError("cannot sample more items than the buffer holds")
        priorities = self.priorities()
        total = sum(priorities)
        if total <= 0:
            return tuple(self._rng.sample(self._items, count))
        chosen: list[ReplayItem] = []
        remaining = list(zip(self._items, priorities))
        target = total
        for _ in range(count):
            threshold = self._rng.random() * target
            cumulative = 0.0
            for index, (item, weight) in enumerate(remaining):
                cumulative += weight
                if cumulative >= threshold:
                    chosen.append(item)
                    target -= weight
                    remaining.pop(index)
                    break
        return tuple(chosen)

    def highest_error_items(self, count: int) -> tuple[ReplayItem, ...]:
        """The worst predictions — the raw material of self-correction."""
        if count < 1:
            raise ValueError("count must be at least one")
        ordered = sorted(self._items, key=lambda item: item.error, reverse=True)
        return tuple(ordered[:count])

    def mean_absolute_error(self) -> Decimal:
        if not self._items:
            raise ValueError("buffer is empty")
        return sum((item.error for item in self._items), Decimal("0")) / len(self._items)

    def by_regime(self) -> dict[str, list[ReplayItem]]:
        buckets: dict[str, list[ReplayItem]] = {}
        for item in self._items:
            buckets.setdefault(item.regime, []).append(item)
        return buckets

    def summary(self) -> dict[str, Any]:
        if not self._items:
            return {"size": 0}
        return {
            "size": len(self._items),
            "capacity": self.capacity,
            "mean_absolute_error": float(self.mean_absolute_error()),
            "regimes": {regime: len(items) for regime, items in self.by_regime().items()},
        }
