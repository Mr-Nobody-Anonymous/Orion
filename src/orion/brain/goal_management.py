from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"


class GoalHorizon(str, Enum):
    INTRADAY = "intraday"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


@dataclass(frozen=True, slots=True)
class Goal:
    identifier: str
    objective: str
    horizon: GoalHorizon
    priority: int = 0
    metrics: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.identifier or not self.objective:
            raise ValueError("goal requires both identifier and objective")
        if not 0 <= self.priority <= 10:
            raise ValueError("priority must be between 0 and 10")


@dataclass(frozen=True, slots=True)
class GoalProgress:
    goal: Goal
    status: GoalStatus
    progress: float
    evidence: tuple[str, ...] = ()
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not 0 <= self.progress <= 1:
            raise ValueError("progress must be between 0 and 1")


class GoalManager:
    """Maintains an ordered set of explicit, accountable goals.

    Goals are explicit objects, not hidden state. The executive can reason
    about active objectives, pause them, complete them, or reject them.
    """

    def __init__(self) -> None:
        self._goals: dict[str, Goal] = {}
        self._progress: dict[str, GoalProgress] = {}
        self._budget: dict[str, float] = {}

    def add(self, goal: Goal, *, progress: float = 0.0) -> GoalProgress:
        if goal.identifier in self._goals:
            raise ValueError(f"goal {goal.identifier} already exists; goals are immutable")
        self._goals[goal.identifier] = goal
        progress_obj = GoalProgress(goal=goal, status=GoalStatus.ACTIVE, progress=progress)
        self._progress[goal.identifier] = progress_obj
        return progress_obj

    def update_progress(self, identifier: str, progress: float, *, evidence: tuple[str, ...] = ()) -> GoalProgress:
        if identifier not in self._goals:
            raise KeyError(identifier)
        current = self._progress[identifier]
        status = current.status
        if progress >= 1.0:
            status = GoalStatus.COMPLETED
        next_progress = GoalProgress(goal=current.goal, status=status, progress=progress, evidence=evidence)
        self._progress[identifier] = next_progress
        return next_progress

    def set_status(self, identifier: str, status: GoalStatus) -> GoalProgress:
        if identifier not in self._goals:
            raise KeyError(identifier)
        current = self._progress[identifier]
        next_progress = GoalProgress(goal=current.goal, status=status, progress=current.progress, evidence=current.evidence)
        self._progress[identifier] = next_progress
        return next_progress

    def active_goals(self) -> tuple[GoalProgress, ...]:
        return tuple(
            sorted(
                (item for item in self._progress.values() if item.status is GoalStatus.ACTIVE),
                key=lambda item: (item.goal.priority, item.goal.horizon.value),
                reverse=True,
            )
        )

    def all(self) -> tuple[GoalProgress, ...]:
        return tuple(self._progress.values())

    def allocate_budget(self, identifier: str, share: float) -> None:
        if not 0 <= share <= 1:
            raise ValueError("budget share must be between 0 and 1")
        if identifier not in self._goals:
            raise KeyError(identifier)
        self._budget[identifier] = share

    def budget_share(self, identifier: str) -> float:
        return self._budget.get(identifier, 0.0)

    def is_stale(self, identifier: str, *, max_age_seconds: float = 86400.0) -> bool:
        if identifier not in self._goals:
            raise KeyError(identifier)
        goal = self._goals[identifier]
        return (datetime.now(timezone.utc) - goal.created_at) > timedelta(seconds=max_age_seconds)

    def as_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "identifier": item.goal.identifier,
                "objective": item.goal.objective,
                "horizon": item.goal.horizon.value,
                "priority": item.goal.priority,
                "status": item.status.value,
                "progress": item.progress,
                "metrics": list(item.goal.metrics),
                "constraints": list(item.goal.constraints),
            }
            for item in self._progress.values()
        ]
