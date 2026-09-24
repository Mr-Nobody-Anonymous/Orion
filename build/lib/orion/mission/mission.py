"""The Mission aggregate — an explicit, legal-transition state machine.

Phase 1 ORION 2.0, correction #9. Status transitions are restricted to
the table below; every successful transition produces a DOMAIN
:class:`~orion.mission.events.MissionEvent`. There is no API that sets
``status`` directly.

    DRAFT    -> ACTIVE | CANCELLED
    ACTIVE   -> PAUSED | BLOCKED | COMPLETED | FAILED | CANCELLED | EXPIRED
    PAUSED   -> ACTIVE | CANCELLED
    BLOCKED  -> ACTIVE | FAILED | CANCELLED
    COMPLETED / FAILED / CANCELLED / EXPIRED  -> (terminal)

A Mission carries its objective (intent), a reference to its goal tree
(the canonical Goal ids), and its :class:`~orion.mission.budget.Budget`
(economics live in the mission's bounded context — correction #3 —
never inside :class:`WorldState`). Missions are identified by a stable
``mission_id`` and carry a monotonic ``version`` for optimistic
concurrency, so several agents can operate on missions safely
(correction #11).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from .budget import Budget
from .events import DomainEvents, MissionEvent, domain_event
from .objective import MissionObjective


class MissionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


#: The explicit legal-transition table (correction #9).
LEGAL_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.DRAFT: {MissionStatus.ACTIVE, MissionStatus.CANCELLED},
    MissionStatus.ACTIVE: {
        MissionStatus.PAUSED,
        MissionStatus.BLOCKED,
        MissionStatus.COMPLETED,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
        MissionStatus.EXPIRED,
    },
    MissionStatus.PAUSED: {MissionStatus.ACTIVE, MissionStatus.CANCELLED},
    MissionStatus.BLOCKED: {
        MissionStatus.ACTIVE,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
    },
    MissionStatus.COMPLETED: set(),
    MissionStatus.FAILED: set(),
    MissionStatus.CANCELLED: set(),
    MissionStatus.EXPIRED: set(),
}

_EVENT_NAMES: dict[MissionStatus, str] = {
    MissionStatus.ACTIVE: DomainEvents.MISSION_ACTIVATED,
    MissionStatus.PAUSED: DomainEvents.MISSION_PAUSED,
    MissionStatus.BLOCKED: DomainEvents.MISSION_BLOCKED,
    MissionStatus.COMPLETED: DomainEvents.MISSION_COMPLETED,
    MissionStatus.FAILED: DomainEvents.MISSION_FAILED,
    MissionStatus.CANCELLED: DomainEvents.MISSION_CANCELLED,
    MissionStatus.EXPIRED: DomainEvents.MISSION_EXPIRED,
}

_TERMINAL = frozenset(
    {
        MissionStatus.COMPLETED,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
        MissionStatus.EXPIRED,
    }
)


class MissionStateError(RuntimeError):
    """An illegal mission status transition was attempted."""



@dataclass(frozen=True, slots=True)
class Mission:
    """The persistent mission aggregate."""

    mission_id: str
    name: str
    objective: MissionObjective
    status: MissionStatus = MissionStatus.DRAFT
    version: int = 1
    goal_ids: tuple[str, ...] = ()
    root_goal_id: str = ""
    agent_id: str = ""
    budget: Budget = field(default_factory=lambda: Budget(allocated=Decimal("0")))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.mission_id:
            raise ValueError("mission_id must be non-empty")
        if not self.name:
            raise ValueError("name must be non-empty")

    # ------------------------------------------------------------- queries

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL

    def can_transition(self, to_status: MissionStatus) -> bool:
        return to_status in LEGAL_TRANSITIONS[self.status]

    # ---------------------------------------------------------- transition

    def transition(
        self,
        to_status: MissionStatus,
        *,
        reason: str = "",
        agent_id: str = "",
        event_id: str | None = None,
    ) -> tuple["Mission", MissionEvent]:
        """Return (next mission, event) for one legal transition.

        Illegal transitions raise :class:`MissionStateError`; nothing
        is mutated. The event id may be supplied by the engine to make
        the transition idempotent under duplicate delivery.
        """
        if not self.can_transition(to_status):
            raise MissionStateError(
                f"mission {self.mission_id!r}: illegal transition "
                f"{self.status.value.upper()} -> {to_status.value.upper()}"
            )
        now = datetime.now(timezone.utc)
        if to_status is MissionStatus.ACTIVE and self.status in (
            MissionStatus.PAUSED, MissionStatus.BLOCKED,
        ):
            event_name = DomainEvents.MISSION_RESUMED
        else:
            event_name = _EVENT_NAMES[to_status]
        event = domain_event(
            event_name,
            self.mission_id,
            agent_id=agent_id,
            event_id=event_id,
            reason=reason,
            from_status=self.status.value,
            to_status=to_status.value,
            version=self.version + 1,
        )
        next_mission = replace(
            self,
            status=to_status,
            version=self.version + 1,
            updated_at=now,
        )
        return next_mission, event

    # --------------------------------------------------------- persistence

    def as_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "name": self.name,
            "objective": self.objective.as_dict(),
            "status": self.status.value,
            "version": self.version,
            "goal_ids": list(self.goal_ids),
            "root_goal_id": self.root_goal_id,
            "agent_id": self.agent_id,
            "budget": self.budget.as_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Mission":
        return cls(
            mission_id=str(d["mission_id"]),
            name=str(d["name"]),
            objective=MissionObjective.from_dict(d["objective"]),
            status=MissionStatus(d["status"]),
            version=int(d.get("version", 1)),
            goal_ids=tuple(d.get("goal_ids", ())),
            root_goal_id=str(d.get("root_goal_id", "")),
            agent_id=str(d.get("agent_id", "")),
            budget=Budget.from_dict(d["budget"]),
            created_at=datetime.fromisoformat(str(d["created_at"])),
            updated_at=datetime.fromisoformat(str(d["updated_at"])),
        )


def new_mission(
    *,
    mission_id: str | None = None,
    name: str,
    objective: MissionObjective,
    agent_id: str = "",
) -> Mission:
    """Create a DRAFT mission with a budget derived from the objective."""
    budget = Budget(
        allocated=(
            objective.budget if objective.budget is not None else Decimal("0")
        )
    )
    return Mission(
        mission_id=mission_id or uuid4().hex,
        name=name,
        objective=objective,
        agent_id=agent_id,
        budget=budget,
    )


__all__ = [
    "LEGAL_TRANSITIONS",
    "Mission",
    "MissionStateError",
    "MissionStatus",
    "new_mission",
]
