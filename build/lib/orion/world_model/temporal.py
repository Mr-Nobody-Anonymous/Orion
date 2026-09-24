"""Temporal reasoning: event timeline and staleness detection.

Markets are time-sensitive: a fact observed an hour ago may be worthless now.
The timeline keeps bounded history and flags stale entries rather than
silently trusting them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    OBSERVATION = "observation"
    DECISION = "decision"
    TRADE = "trade"
    NEWS = "news"
    MACRO_RELEASE = "macro_release"
    MODEL_UPDATE = "model_update"
    ANOMALY = "anomaly"
    REGIME_CHANGE = "regime_change"


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    kind: EventKind
    description: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("event description is required")


@dataclass(frozen=True, slots=True)
class StalenessReport:
    fresh: int
    stale: int
    oldest_age_seconds: float
    staleness_by_kind: dict[str, float]

    @property
    def has_stale(self) -> bool:
        return self.stale > 0


class Timeline:
    """Bounded, time-ordered event history with staleness accounting."""

    def __init__(self, *, max_events: int = 500, default_freshness: timedelta = timedelta(hours=6)) -> None:
        if max_events < 1:
            raise ValueError("max_events must be at least one")
        if default_freshness.total_seconds() <= 0:
            raise ValueError("default_freshness must be positive")
        self.max_events = max_events
        self.default_freshness = default_freshness
        self._events: list[TimelineEvent] = []

    def record(self, kind: EventKind, description: str, *, payload: dict[str, Any] | None = None,
               occurred_at: datetime | None = None) -> TimelineEvent:
        event = TimelineEvent(kind, description, dict(payload or {}), occurred_at or datetime.now(timezone.utc))
        if event.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        self._events.append(event)
        self._events.sort(key=lambda e: e.occurred_at)
        if len(self._events) > self.max_events:
            self._events.pop(0)
        return event

    def events_since(self, cutoff: datetime) -> tuple[TimelineEvent, ...]:
        return tuple(event for event in self._events if event.occurred_at >= cutoff)

    def events_of_kind(self, kind: EventKind) -> tuple[TimelineEvent, ...]:
        return tuple(event for event in self._events if event.kind is kind)

    def latest(self, kind: EventKind | None = None) -> TimelineEvent | None:
        candidates = self._events if kind is None else [e for e in self._events if e.kind is kind]
        return candidates[-1] if candidates else None

    def staleness(self, *, now: datetime | None = None, freshness: timedelta | None = None) -> StalenessReport:
        reference = now or datetime.now(timezone.utc)
        limit = freshness or self.default_freshness
        fresh = stale = 0
        oldest_age = 0.0
        by_kind: dict[str, list[float]] = {}
        for event in self._events:
            age = (reference - event.occurred_at).total_seconds()
            oldest_age = max(oldest_age, age)
            by_kind.setdefault(event.kind.value, []).append(age)
            if age <= limit.total_seconds():
                fresh += 1
            else:
                stale += 1
        return StalenessReport(
            fresh, stale, oldest_age,
            {kind: max(ages) for kind, ages in by_kind.items()},
        )

    def count(self) -> int:
        return len(self._events)

    def scheduled_between(self, start: datetime, end: datetime) -> tuple[TimelineEvent, ...]:
        if end < start:
            raise ValueError("end must not precede start")
        return tuple(event for event in self._events if start <= event.occurred_at <= end)
