"""Mission events — with the three categories kept distinct.

Phase 1 ORION 2.0, correction #15:

* DOMAIN events   — facts about the mission's lifecycle and economics
  (``MissionCreated``, ``GoalCompleted``, ``OutcomeRecorded``, ...).
* EXECUTION events — tool / worker mechanics (Phase 2; the existing
  executor's ``InvocationRecord`` already covers this).
* AUDIT events    — permission / risk / approval decisions (Phase 2;
  the existing ``security.audit`` and ``ApprovalGate`` own these).

A :class:`MissionEvent` carries its category explicitly so the three
concepts never collapse into one generic event type. Domain events are
additionally published on the existing infrastructure
:class:`~orion.infrastructure.event_bus.EventBus` as ``mission.<Name>``
:code:`orion.data.contracts.Event` items.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class EventCategory(str, Enum):
    DOMAIN = "domain"
    EXECUTION = "execution"
    AUDIT = "audit"


class DomainEvents:
    """Canonical domain event names (strings, enum-safe)."""

    MISSION_CREATED = "MissionCreated"
    MISSION_PLANNED = "MissionPlanned"
    MISSION_ACTIVATED = "MissionActivated"
    MISSION_PAUSED = "MissionPaused"
    MISSION_RESUMED = "MissionResumed"
    MISSION_BLOCKED = "MissionBlocked"
    MISSION_COMPLETED = "MissionCompleted"
    MISSION_FAILED = "MissionFailed"
    MISSION_CANCELLED = "MissionCancelled"
    MISSION_EXPIRED = "MissionExpired"
    GOAL_COMPLETED = "GoalCompleted"
    GOAL_FAILED = "GoalFailed"
    OUTCOME_RECORDED = "OutcomeRecorded"
    BUDGET_RESERVED = "BudgetReserved"
    BUDGET_COMMITTED = "BudgetCommitted"
    BUDGET_RELEASED = "BudgetReleased"


@dataclass(frozen=True, slots=True)
class MissionEvent:
    """One immutable, append-only mission event.

    ``seq`` is a per-mission monotonic sequence number assigned by the
    engine so replay order is fully deterministic across restarts.
    """

    event_id: str
    category: EventCategory
    name: str
    mission_id: str
    agent_id: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    seq: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "name": self.name,
            "mission_id": self.mission_id,
            "agent_id": self.agent_id,
            "payload": dict(self.payload),
            "at": self.at.isoformat(),
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MissionEvent":
        return cls(
            event_id=str(d["event_id"]),
            category=EventCategory(d["category"]),
            name=str(d["name"]),
            mission_id=str(d["mission_id"]),
            agent_id=str(d.get("agent_id", "")),
            payload=dict(d.get("payload", {})),
            at=datetime.fromisoformat(str(d["at"])),
            seq=int(d.get("seq", 0)),
        )


def domain_event(
    name: str,
    mission_id: str,
    *,
    agent_id: str = "",
    event_id: str | None = None,
    **payload: Any,
) -> MissionEvent:
    """Convenience factory for DOMAIN-category mission events."""
    return MissionEvent(
        event_id=event_id or uuid4().hex,
        category=EventCategory.DOMAIN,
        name=name,
        mission_id=mission_id,
        agent_id=agent_id,
        payload=payload,
    )


__all__ = [
    "DomainEvents",
    "EventCategory",
    "MissionEvent",
    "domain_event",
]
