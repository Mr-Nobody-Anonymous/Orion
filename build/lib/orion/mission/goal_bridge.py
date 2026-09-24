"""Mission <-> canonical goal bridge.

Phase 1 ORION 2.0, correction #2. There is exactly ONE canonical goal
tree implementation: :class:`orion.agent.state.Goal` +
:class:`orion.agent.goal_manager.GoalManager` operating on the
immutable :class:`orion.agent.state.WorldState`. This module:

* :class:`MissionGoalCoordinator` â€” instantiates a validated
  :class:`~orion.mission.planner.MissionPlan` as a goal tree using the
  canonical manager (no ``MissionGoal`` classes), and drives goal
  status transitions through it.
* :class:`BrainGoalAdapter` â€” a compatibility adapter exposing the
  legacy ``brain/goal_management.py`` API surface, backed by the
  canonical implementation, so legacy consumers can be migrated
  without maintaining a second goal system.

Correction #3: the mission-scoped ``WorldState`` carries only a
*reference* to the mission (``meta["mission"]["mission_id"]``) â€” no
economic state ever enters ``WorldState``.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone

from ..agent.goal_manager import GoalManager
from ..agent.state import Goal, GoalStatus, WorldState
from .planner import MissionPlan

_BRAIN_TO_CANONICAL = {
    "active": GoalStatus.ACTIVE,
    "paused": GoalStatus.BLOCKED,
    "completed": GoalStatus.DONE,
    "rejected": GoalStatus.ABANDONED,
}

_CANONICAL_TO_BRAIN = {
    GoalStatus.ACTIVE: "active",
    GoalStatus.PROPOSED: "active",
    GoalStatus.DONE: "completed",
    GoalStatus.ABANDONED: "rejected",
    GoalStatus.BLOCKED: "paused",
}


@dataclass(frozen=True, slots=True)
class _LegacyStatus:
    """Duck-compatible stand-in for brain GoalStatus."""

    value: str


@dataclass(frozen=True, slots=True)
class _LegacyProgress:
    """Duck-compatible stand-in for brain GoalProgress."""

    goal: Goal
    status: _LegacyStatus
    progress: float
    evidence: tuple[str, ...] = ()
    updated_at: datetime = dc_field(default_factory=lambda: datetime.now(timezone.utc))


class MissionGoalCoordinator:
    """Owns the mission-scoped goal tree via the canonical GoalManager."""

    def __init__(self, mission_id: str) -> None:
        self._mission_id = mission_id
        self._manager = GoalManager()

    def instantiate(self, plan: MissionPlan) -> WorldState:
        """Create every planned goal in a fresh mission-scoped state."""
        state = WorldState(meta={"mission": {"mission_id": self._mission_id}})
        for pg in plan.goals:
            state = self._manager.create(
                state, pg.goal, reason="mission plan instantiation"
            )
        # Activate the WHOLE tree (root + leaves); every goal the agent may
        # execute must be ACTIVE, not PROPOSED.
        # the status unconditionally so this is safe for every leaf.
        for g in state.goals:
            if g.status is not GoalStatus.ACTIVE:
                state = self._manager.activate(
                    state, g.goal_id, reason="mission plan activated"
                )
        return state

    def complete_goal(self, state: WorldState, goal_id: str) -> WorldState:
        """Mark a goal DONE. Idempotent; parent completion propagates
        through the canonical ``WorldState.with_goal_status`` rules."""
        goal = self.goal(state, goal_id)
        if goal.status is GoalStatus.DONE:
            return state
        return self._manager.complete(
            state, goal_id, reason="mission goal completed"
        )

    def block_goal(
        self, state: WorldState, goal_id: str, *, reason: str = ""
    ) -> WorldState:
        goal = self.goal(state, goal_id)
        if goal.status is GoalStatus.BLOCKED:
            return state
        return self._manager.block(state, goal_id, reason=reason)

    def abandon_goal(
        self, state: WorldState, goal_id: str, *, reason: str = ""
    ) -> WorldState:
        goal = self.goal(state, goal_id)
        if goal.status is GoalStatus.ABANDONED:
            return state
        return self._manager.abandon(state, goal_id, reason=reason)

    def goal(self, state: WorldState, goal_id: str) -> Goal:
        for g in state.goals:
            if g.goal_id == goal_id:
                return g
        raise KeyError(goal_id)

    @staticmethod
    def goals_now_done(before: WorldState, after: WorldState) -> tuple[str, ...]:
        """Goal ids that became DONE between two states (for events)."""
        before_status = {g.goal_id: g.status for g in before.goals}
        return tuple(
            g.goal_id
            for g in after.goals
            if g.status is GoalStatus.DONE
            and before_status.get(g.goal_id) is not GoalStatus.DONE
        )

    @property
    def manager(self) -> GoalManager:
        """The canonical manager (exposed for audit/read use)."""
        return self._manager



class BrainGoalAdapter:
    """Compatibility adapter for ``brain/goal_management.py`` consumers.

    Accepts the legacy API shape (identifier / objective / horizon /
    priority, progress floats, status strings) but stores all state in
    the canonical ``Goal``/``WorldState`` implementation, so there is
    one goal system, not two.
    """

    def __init__(self) -> None:
        self._manager = GoalManager()
        self._state = WorldState()
        self._progress: dict[str, float] = {}

    # ------------------------------------------------------------ legacy API

    def add(
        self,
        identifier: str,
        objective: str,
        *,
        horizon: str = "short",
        priority: int = 5,
    ) -> None:
        if any(g.goal_id == identifier for g in self._state.goals):
            raise ValueError(
                f"goal {identifier!r} already exists; goals are immutable"
            )
        goal = Goal(
            goal_id=identifier,
            description=objective,
            priority=max(0, min(10, int(priority))),
            status=GoalStatus.ACTIVE,
        )
        self._state = self._manager.create(self._state, goal, reason="adapter add")
        self._progress[identifier] = 0.0

    def update_progress(
        self, identifier: str, progress: float, *, evidence: tuple[str, ...] = ()
    ) -> _LegacyProgress:
        if identifier not in self._progress:
            raise KeyError(identifier)
        if not 0.0 <= progress <= 1.0:
            raise ValueError("progress must be between 0 and 1")
        self._progress[identifier] = progress
        if progress >= 1.0:
            self._state = self._manager.complete(
                self._state, identifier, reason="progress complete"
            )
        return self._snapshot(identifier)

    def set_status(self, identifier: str, status) -> _LegacyProgress:
        name = getattr(status, "value", str(status))
        if name not in _BRAIN_TO_CANONICAL:
            raise ValueError(f"unknown legacy status {name!r}")
        canonical = _BRAIN_TO_CANONICAL[name]
        self._state = self._manager._transition(
            self._state, identifier, canonical, reason=f"adapter set_status {name}"
        )
        return self._snapshot(identifier)

    # ----------------------------------------------------------------- reads

    def active_goals(self) -> tuple[_LegacyProgress, ...]:
        return tuple(
            self._snapshot(g.goal_id)
            for g in self._state.goals
            if g.status is GoalStatus.ACTIVE
        )

    def all(self) -> tuple[_LegacyProgress, ...]:
        return tuple(self._snapshot(g.goal_id) for g in self._state.goals)

    def as_dict(self) -> list[dict]:
        return [
            {
                "identifier": pg.goal.goal_id,
                "objective": pg.goal.description,
                "priority": pg.goal.priority,
                "status": _CANONICAL_TO_BRAIN[pg.goal.status],
                "progress": self._progress.get(pg.goal.goal_id, 0.0),
            }
            for pg in self.all()
        ]

    # ------------------------------------------------------------- canonical

    def canonical_goal(self, identifier: str) -> Goal:
        for g in self._state.goals:
            if g.goal_id == identifier:
                return g
        raise KeyError(identifier)

    def canonical_state(self) -> WorldState:
        return self._state

    # --------------------------------------------------------------- helpers

    def _snapshot(self, identifier: str) -> _LegacyProgress:
        goal = self.canonical_goal(identifier)
        return _LegacyProgress(
            goal=goal,
            status=_LegacyStatus(value=_CANONICAL_TO_BRAIN[goal.status]),
            progress=self._progress.get(identifier, 0.0),
        )


__all__ = ["BrainGoalAdapter", "MissionGoalCoordinator"]
