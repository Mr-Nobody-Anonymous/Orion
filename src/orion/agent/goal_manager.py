"""The ORION :class:`GoalManager` — a thin layer over the
:class:`WorldState` goal list that exposes the operations
the 2026-08-28 review (point 5) called out:

* ``create(goal) -> state``
* ``prioritize(goal_id, priority) -> state``
* ``decompose(goal_id, subgoals) -> state``
* ``activate(goal_id) -> state``
* ``pause(goal_id) -> state``   (new in Phase 31G)
* ``resume(goal_id) -> state``  (new in Phase 31G)
* ``block(goal_id, reason) -> state``
* ``abandon(goal_id, reason) -> state``
* ``complete(goal_id) -> state``  (alias of DONE)
* ``retry(goal_id) -> state``     (new in Phase 31G)
* ``replan(goal_id, subgoals) -> state``  (new in Phase 31G)

Why a separate class
--------------------

All of these could be methods on :class:`WorldState`. The
:class:`GoalManager` exists for two reasons:

1. **Stable surface for the policy.** The policy asks the
   manager to ``pause`` or ``retry``; it does not need to
   know about the internal ``GoalStatus`` enum or the
   propagation rules. The manager is the policy's
   vocabulary.
2. **Single place to attach audit.** Every operation
   records a short reason string so the goal's status
   history is reconstructable from the meta dict.

The manager is a **thin** layer: it does not plan, does
not invent subgoals, does not infer priorities. The
caller (the policy or the user) supplies the inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .state import Goal, GoalStatus, WorldState


@dataclass(frozen=True, slots=True)
class GoalHistoryEntry:
    """One entry in a goal's status history.

    A goal's history is the audit trail of every status
    transition the :class:`GoalManager` made. It lives
    in the :class:`WorldState`'s ``meta`` dict under
    the key ``f"goal_history:{goal_id}"`` so the agent
    can read it back without inventing a new field on
    the state.
    """

    goal_id: str
    from_status: str
    to_status: str
    reason: str
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "at": self.at.isoformat(),
        }


class GoalManager:
    """A vocabulary for the agent's goal list.

    The manager holds no state of its own; it is a pure
    function from (state, operation) to (state', reason).
    Construct one with ``GoalManager()`` and call its
    methods on a :class:`WorldState`.
    """

    HISTORY_KEY_PREFIX = "goal_history:"

    # ------------------------------------------------------------------ create

    def create(
        self,
        state: WorldState,
        goal: Goal,
        *,
        reason: str = "",
    ) -> WorldState:
        """Append a new goal to the state.

        The goal's ``goal_id`` must be unique. If the
        caller wants the goal to start as ACTIVE, set
        ``status=GoalStatus.ACTIVE`` in the goal's
        constructor; the manager does not enforce a
        default.
        """
        if any(g.goal_id == goal.goal_id for g in state.goals):
            raise ValueError(
                f"goal_id {goal.goal_id!r} already in state"
            )
        new_goals = state.goals + (goal,)
        new_state = self._replace_goals(state, new_goals)
        return self._record_history(
            new_state, goal.goal_id,
            from_status="(none)", to_status=goal.status.value,
            reason=reason or "create",
        )

    # ------------------------------------------------------------------ prioritise

    def prioritize(
        self,
        state: WorldState,
        goal_id: str,
        new_priority: int,
        *,
        reason: str = "",
    ) -> WorldState:
        """Return a new state with ``goal_id``'s priority changed."""
        by_id = {g.goal_id: g for g in state.goals}
        if goal_id not in by_id:
            raise KeyError(f"goal {goal_id!r} not in state")
        if new_priority < 0:
            raise ValueError("priority must be non-negative")
        old = by_id[goal_id]
        new_goals = tuple(
            Goal(
                goal_id=g.goal_id,
                description=g.description,
                priority=new_priority if g.goal_id == goal_id else g.priority,
                deadline=g.deadline,
                status=g.status,
                success_criteria=g.success_criteria,
                parent_goal_id=g.parent_goal_id,
                subgoal_ids=g.subgoal_ids,
            ) for g in state.goals
        )
        new_state = self._replace_goals(state, new_goals)
        return self._record_history(
            new_state, goal_id,
            from_status=old.status.value,
            to_status=old.status.value,
            reason=reason or f"prioritise:{old.priority}->{new_priority}",
        )

    # ------------------------------------------------------------------ decompose

    def decompose(
        self,
        state: WorldState,
        parent_goal_id: str,
        subgoals: tuple[Goal, ...],
        *,
        reason: str = "",
    ) -> WorldState:
        """Decompose ``parent_goal_id`` into ``subgoals``.

        The new state is the input state with
        :meth:`WorldState.decompose_goal` applied, plus
        a history entry.
        """
        # Capture the parent's status before decomposition.
        by_id = {g.goal_id: g for g in state.goals}
        if parent_goal_id not in by_id:
            raise KeyError(f"parent goal {parent_goal_id!r} not in state")
        parent = by_id[parent_goal_id]
        new_state = state.decompose_goal(parent_goal_id, subgoals)
        return self._record_history(
            new_state, parent_goal_id,
            from_status=parent.status.value,
            to_status=parent.status.value,
            reason=reason or f"decompose:{len(subgoals)}_subgoals",
        )

    # ------------------------------------------------------------------ activate / pause / resume

    def activate(
        self,
        state: WorldState,
        goal_id: str,
        *,
        reason: str = "",
    ) -> WorldState:
        """Set ``goal_id``'s status to ``ACTIVE``."""
        return self._transition(state, goal_id, GoalStatus.ACTIVE, reason=reason or "activate")

    def pause(
        self,
        state: WorldState,
        goal_id: str,
        *,
        reason: str = "",
    ) -> WorldState:
        """Pause a goal by setting its status to ``PROPOSED``.

        ``PAUSE`` reuses the existing :class:`GoalStatus`
        set (``PROPOSED``, ``ACTIVE``, ``BLOCKED``,
        ``DONE``, ``ABANDONED``) rather than introducing
        a new ``PAUSED`` state. The goal is no longer
        the active leaf; it can be returned to ACTIVE by
        :meth:`resume`.
        """
        return self._transition(state, goal_id, GoalStatus.PROPOSED, reason=reason or "pause")

    def resume(
        self,
        state: WorldState,
        goal_id: str,
        *,
        reason: str = "",
    ) -> WorldState:
        """Resume a paused goal by setting its status to ``ACTIVE``."""
        return self._transition(state, goal_id, GoalStatus.ACTIVE, reason=reason or "resume")

    # ------------------------------------------------------------------ block / abandon / complete

    def block(
        self,
        state: WorldState,
        goal_id: str,
        reason: str = "",
    ) -> WorldState:
        """Set ``goal_id``'s status to ``BLOCKED`` with a reason.

        The reason is recorded in the goal's history so
        the agent (or a human reviewer) can reconstruct
        why the goal is blocked.
        """
        return self._transition(state, goal_id, GoalStatus.BLOCKED, reason=reason or "block")

    def abandon(
        self,
        state: WorldState,
        goal_id: str,
        reason: str = "",
    ) -> WorldState:
        """Set ``goal_id``'s status to ``ABANDONED`` with a reason."""
        return self._transition(state, goal_id, GoalStatus.ABANDONED, reason=reason or "abandon")

    def complete(
        self,
        state: WorldState,
        goal_id: str,
        reason: str = "",
    ) -> WorldState:
        """Set ``goal_id``'s status to ``DONE`` (alias of completion)."""
        return self._transition(state, goal_id, GoalStatus.DONE, reason=reason or "complete")

    # ------------------------------------------------------------------ retry / replan

    def retry(
        self,
        state: WorldState,
        goal_id: str,
        *,
        reason: str = "",
    ) -> WorldState:
        """Reset ``goal_id`` to ``ACTIVE``.

        Used when an agent has been BLOCKED or ABANDONED
        and the policy decides the conditions have
        changed (e.g. a new observation suggests the
        blocker is gone). The retry re-activates the
        goal and is recorded in the history.
        """
        return self._transition(state, goal_id, GoalStatus.ACTIVE, reason=reason or "retry")

    def replan(
        self,
        state: WorldState,
        goal_id: str,
        subgoals: tuple[Goal, ...],
        *,
        reason: str = "",
    ) -> WorldState:
        """Decompose ``goal_id`` into new subgoals, replacing
        any existing decomposition.

        This is "replan": the agent rethinks how to
        approach the goal. The old subgoals are kept
        (the state is append-only for the goal list) but
        the new subgoals are added on top.
        """
        return self.decompose(
            state, goal_id, subgoals, reason=reason or "replan",
        )

    # ------------------------------------------------------------------ introspection

    def history(
        self,
        state: WorldState,
        goal_id: str,
    ) -> tuple[GoalHistoryEntry, ...]:
        """Return the goal's status history."""
        raw = state.meta.get(self.HISTORY_KEY_PREFIX + goal_id, ())
        return tuple(GoalHistoryEntry(**e) for e in raw)

    # ------------------------------------------------------------------ helpers

    def _transition(
        self,
        state: WorldState,
        goal_id: str,
        new_status: GoalStatus,
        *,
        reason: str,
    ) -> WorldState:
        by_id = {g.goal_id: g for g in state.goals}
        if goal_id not in by_id:
            raise KeyError(f"goal {goal_id!r} not in state")
        old = by_id[goal_id]
        # Re-use WorldState.with_goal_status for the
        # status change (and auto-propagation of DONE up
        # the parent chain).
        new_state = state.with_goal_status(goal_id, new_status)
        return self._record_history(
            new_state, goal_id,
            from_status=old.status.value,
            to_status=new_status.value,
            reason=reason,
        )

    def _record_history(
        self,
        state: WorldState,
        goal_id: str,
        *,
        from_status: str,
        to_status: str,
        reason: str,
    ) -> WorldState:
        entry = GoalHistoryEntry(
            goal_id=goal_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
        )
        key = self.HISTORY_KEY_PREFIX + goal_id
        history = list(state.meta.get(key, ()))
        history.append(entry.as_dict())
        new_meta = dict(state.meta)
        new_meta[key] = tuple(history)
        return WorldState(
            state_id=state.state_id,
            created_at=state.created_at,
            step_count=state.step_count,
            goals=state.goals,
            active_task=state.active_task,
            last_observation=state.last_observation,
            beliefs=state.beliefs,
            observations=state.observations,
            completed_actions=state.completed_actions,
            pending_actions=state.pending_actions,
            predictions=state.predictions,
            prediction_errors=state.prediction_errors,
            meta=new_meta,
            max_observations=state.max_observations,
            max_completed_actions=state.max_completed_actions,
            max_predictions=state.max_predictions,
            max_prediction_errors=state.max_prediction_errors,
        )

    def _replace_goals(
        self,
        state: WorldState,
        new_goals: tuple[Goal, ...],
    ) -> WorldState:
        return WorldState(
            state_id=state.state_id,
            created_at=state.created_at,
            step_count=state.step_count,
            goals=new_goals,
            active_task=state.active_task,
            last_observation=state.last_observation,
            beliefs=state.beliefs,
            observations=state.observations,
            completed_actions=state.completed_actions,
            pending_actions=state.pending_actions,
            predictions=state.predictions,
            prediction_errors=state.prediction_errors,
            meta=state.meta,
            max_observations=state.max_observations,
            max_completed_actions=state.max_completed_actions,
            max_predictions=state.max_predictions,
            max_prediction_errors=state.max_prediction_errors,
        )
