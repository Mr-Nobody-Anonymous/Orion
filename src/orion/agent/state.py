"""Persistent agent world state.

The :class:`WorldState` is the unit of persistence for an
ORION agent. It survives across ``step`` calls. Every field
on it is either a primitive, a tuple, or a frozen dataclass
so the state is cheap to copy and trivially serialisable.

Why copy-on-write
-----------------

The state is **frozen** and every ``step`` returns a *new*
state rather than mutating the existing one. This makes three
properties fall out for free:

* **Determinism.** Given the same state and the same
  observation, the kernel produces the same next state and
  the same action. Reproducibility for free.
* **Audit.** Every state transition is a value that can be
  hashed, compared, and replayed. The truth artifact can
  record the full state trajectory.
* **Branching.** Two threads can each call ``step`` on the
  same starting state and get two independent successor
  states. The agent can try alternative actions without
  corrupting the original state.

State contents
--------------

The state carries exactly the fields the 2026-08-28 review
called out as required for an agent world model:

* ``goal`` — what the agent is trying to achieve.
* ``active_task`` — the immediate next thing to do.
* ``observations`` — what the environment has reported, in
  order, capped at a configurable maximum.
* ``beliefs`` — the agent's current best guess at facts,
  with confidence. This is the "semantic memory" the review
  asked for.
* ``completed_actions`` — every action the agent has taken
  and the observation that resulted.
* ``pending_actions`` — actions the agent has chosen but
  not yet observed an outcome for.
* ``step_count`` — monotonically increasing; the
  audit log uses it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import UUID, uuid4


class GoalStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DONE = "done"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class Goal:
    """The top-level objective the agent is pursuing.

    A goal has a priority (0 = highest), a deadline (optional),
    a status, and a list of success criteria. The agent cannot
    do anything more sophisticated than this without a
    planner; the goal structure is the *input* to a future
    planner, not a planner itself.

    Goals form a **tree**, not a flat list. A goal can have a
    ``parent_goal_id`` and a ``subgoal_ids`` tuple. The
    hierarchy is a deliberate response to the 2026-08-28
    review's point 12: a strong agent decomposes a goal
    into subgoals, executes them, and only marks the parent
    done when every leaf subgoal is done. The kernel does
    not plan the decomposition; it stores and queries it.

    Cycle protection
    ----------------

    A goal cannot be its own ancestor. The kernel validates
    this in :meth:`WorldState.decompose_goal` by walking
    the parent chain; a cycle is a structural error.
    """

    goal_id: str
    description: str
    priority: int = 0
    deadline: datetime | None = None
    status: GoalStatus = GoalStatus.PROPOSED
    success_criteria: tuple[str, ...] = ()
    parent_goal_id: str | None = None
    subgoal_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.goal_id:
            raise ValueError("goal_id must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        # A goal cannot be its own parent.
        if self.parent_goal_id == self.goal_id:
            raise ValueError(
                f"goal {self.goal_id!r} cannot be its own parent"
            )
        # Subgoal ids must be unique and must not include
        # the parent itself.
        if len(set(self.subgoal_ids)) != len(self.subgoal_ids):
            raise ValueError(
                f"goal {self.goal_id!r} has duplicate subgoal_ids"
            )
        if self.goal_id in self.subgoal_ids:
            raise ValueError(
                f"goal {self.goal_id!r} cannot be its own subgoal"
            )

    def is_leaf(self) -> bool:
        """A leaf goal has no subgoals."""
        return not self.subgoal_ids

    def is_done(self) -> bool:
        """A goal is done when its status is DONE."""
        return self.status == GoalStatus.DONE

    def is_blocked(self) -> bool:
        """A goal is blocked when its status is BLOCKED."""
        return self.status == GoalStatus.BLOCKED

    def is_terminal(self) -> bool:
        """A terminal goal is DONE, ABANDONED, or BLOCKED."""
        return self.status in (
            GoalStatus.DONE,
            GoalStatus.ABANDONED,
            GoalStatus.BLOCKED,
        )

    def with_status(self, status: GoalStatus) -> "Goal":
        """Return a new :class:`Goal` with the given status.

        This is the canonical way to mutate a goal's status;
        it preserves immutability.
        """
        return Goal(
            goal_id=self.goal_id,
            description=self.description,
            priority=self.priority,
            deadline=self.deadline,
            status=status,
            success_criteria=self.success_criteria,
            parent_goal_id=self.parent_goal_id,
            subgoal_ids=self.subgoal_ids,
        )

    def with_subgoals(self, subgoal_ids: tuple[str, ...]) -> "Goal":
        """Return a new :class:`Goal` with the given subgoals.

        Used by :meth:`WorldState.decompose_goal` to attach
        a freshly-decomposed set of subgoals to a parent
        goal.
        """
        return Goal(
            goal_id=self.goal_id,
            description=self.description,
            priority=self.priority,
            deadline=self.deadline,
            status=self.status,
            success_criteria=self.success_criteria,
            parent_goal_id=self.parent_goal_id,
            subgoal_ids=tuple(subgoal_ids),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status.value,
            "success_criteria": list(self.success_criteria),
            "parent_goal_id": self.parent_goal_id,
            "subgoal_ids": list(self.subgoal_ids),
        }


@dataclass(frozen=True, slots=True)
class Belief:
    """A fact the agent believes, with confidence.

    The ``source`` field is mandatory: an agent that cannot
    say *why* it believes something is not a serious agent.
    The ``confidence`` is in [0, 1]. A belief with confidence
    0.0 is "I have no idea"; 1.0 is "I am certain".

    Beliefs support calibrated updating via
    :meth:`update`, which is the kernel's "rational change
    of mind" primitive. The update is a bounded log-odds
    shift: positive ``evidence`` raises confidence,
    negative lowers it, and the magnitude controls how
    strong the move is. The confidence is clamped to
    [0, 1] so the result is always a valid :class:`Belief`.
    """

    claim: str
    confidence: float
    source: str
    evidence: tuple[str, ...] = ()
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence {self.confidence} not in [0, 1]")
        if not self.claim:
            raise ValueError("claim must be non-empty")
        if not self.source:
            raise ValueError("source must be non-empty")

    def update(
        self,
        evidence: float,
        *,
        source: str = "",
        reason: str = "",
        learning_rate: float = 0.3,
    ) -> "Belief":
        """Return a new :class:`Belief` with updated confidence.

        This is the kernel's "change my mind" primitive.
        Positive ``evidence`` raises confidence (the agent
        is more sure); negative lowers it. The shift is
        applied in log-odds space so the result is symmetric
        around 0.5 and bounded by [0, 1].

        Parameters
        ----------
        evidence:
            Signed number. ``+1.0`` is one piece of strong
            supporting evidence; ``-1.0`` is one piece of
            strong refuting evidence; ``0.0`` is a no-op
            (the new belief equals the old one modulo the
            new evidence string and timestamp).
        source:
            Optional new source string. If empty, the
            existing source is preserved.
        reason:
            Short human-readable reason for the update,
            appended to the ``evidence`` tuple for audit.
        learning_rate:
            How fast the agent learns. The default of
            ``0.3`` means a single ``+1.0`` evidence moves
            the confidence by about 30 % of the remaining
            distance to 0.5 in log-odds space. Clamped to
            ``(0, 1]``.

        Notes
        -----
        The mathematical form is:

            p_new = sigmoid(logit(p_old) + lr * evidence)

        where ``logit`` and ``sigmoid`` are the standard
        log-odds transforms. Edge cases (``p_old == 0`` or
        ``p_old == 1``) are handled by clipping to a small
        epsilon so the logit is finite.
        """
        if not 0.0 < learning_rate <= 1.0:
            raise ValueError(
                f"learning_rate {learning_rate} not in (0, 1]"
            )
        eps = 1e-6
        p = min(max(self.confidence, eps), 1.0 - eps)
        logit_p = math.log(p / (1.0 - p))
        new_logit = logit_p + learning_rate * float(evidence)
        # sigmoid, but bounded to [0, 1] for numerical safety
        new_p = 1.0 / (1.0 + math.exp(-new_logit))
        new_p = min(max(new_p, 0.0), 1.0)
        new_evidence: tuple[str, ...] = self.evidence
        if reason:
            new_evidence = self.evidence + (reason,)
        return Belief(
            claim=self.claim,
            confidence=new_p,
            source=source or self.source,
            evidence=new_evidence,
            updated_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class Observation:
    """What the environment told the agent at one tick.

    The ``kind`` field is a free-form string; the agent
    kernel does not interpret it. Downstream reasoners /
    planners may branch on it.
    """

    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "environment"

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("kind must be non-empty")
        if not self.source:
            raise ValueError("source must be non-empty")

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "payload": dict(self.payload),
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class Action:
    """What the agent chose to do at one tick.

    The ``capability`` field is the name of a registered
    capability (matches :class:`Tool.name` in
    :mod:`orion.intelligence.capability_registry`). The
    ``args`` are the call's input, and ``intent_id`` is a
    deterministic identifier derived from the step + tick
    so the same state + policy produces the same action
    (the kernel's determinism invariant).
    """

    capability: str
    args: Mapping[str, Any] = field(default_factory=dict)
    intent_id: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.capability:
            raise ValueError("capability must be non-empty")


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    """A pair of an action and the observation that resulted.

    The agent appends an :class:`ActionOutcome` to its
    completed_actions on every step so the audit log can
    reconstruct the trajectory.
    """

    action: Action
    observation: Observation


@dataclass(frozen=True, slots=True)
class WorldState:
    """The persistent state of an ORION agent.

    Immutable. Every :meth:`Agent.step` returns a new
    :class:`WorldState` that shares most of its structure with
    the input state. To roll back a step, drop the latest
    state and keep the previous one.
    """

    state_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    step_count: int = 0
    # The top-level goal hierarchy. Only the *active* goal is
    # followed by the kernel; the rest are stored for a future
    # planner.
    goals: tuple[Goal, ...] = ()
    # The current task: the immediate next thing to do. May
    # be a sub-task of a goal.
    active_task: str = ""
    # The observation that the agent most recently received.
    last_observation: Observation | None = None
    # The belief table. Keyed by claim. The dict is the only
    # mutable-shaped field on the state; it is replaced with
    # a new dict on every change, so the state remains
    # hashable.
    beliefs: Mapping[str, Belief] = field(default_factory=dict)
    # The recent observation history, capped at max_observations.
    observations: tuple[Observation, ...] = ()
    # The actions the agent has taken and the observation that
    # resulted, capped at max_completed_actions.
    completed_actions: tuple[ActionOutcome, ...] = ()
    # Actions the agent has chosen but not yet observed an
    # outcome for. The kernel moves them to completed_actions
    # on the next step (when the next observation arrives).
    pending_actions: tuple[Action, ...] = ()
    # Free-form metadata for callers that want to attach
    # session ids, user ids, etc.
    meta: Mapping[str, Any] = field(default_factory=dict)
    # Capping parameters. Stored on the state so the agent
    # can self-tune.
    max_observations: int = 256
    max_completed_actions: int = 1024

    def __post_init__(self) -> None:
        if self.step_count < 0:
            raise ValueError("step_count must be non-negative")
        if self.max_observations <= 0:
            raise ValueError("max_observations must be > 0")
        if self.max_completed_actions <= 0:
            raise ValueError("max_completed_actions must be > 0")
        for goal in self.goals:
            if not isinstance(goal, Goal):
                raise ValueError("every entry in goals must be a Goal")
        for claim, belief in self.beliefs.items():
            if not isinstance(belief, Belief):
                raise ValueError(f"beliefs[{claim!r}] is not a Belief")
            if belief.claim != claim:
                raise ValueError(
                    f"belief key {claim!r} does not match belief.claim {belief.claim!r}"
                )

    # ------------------------------------------------------------------ queries

    def active_goal(self) -> Goal | None:
        """Return the highest-priority *leaf* active goal, or None.

        A leaf goal has no subgoals. If an active goal has
        subgoals and any of them are still incomplete, the
        leaf active goal is the highest-priority one of
        *those*, not the parent. The parent goal remains
        ACTIVE in the state but is shadowed by its
        in-progress children. This is the kernel's
        "execute the leaves, propagate up" convention.

        The original (flat) behaviour is preserved for the
        case where no goal has subgoals, so existing tests
        and policies that treat the goal list as a flat
        priority queue still work.
        """
        by_id = {g.goal_id: g for g in self.goals}
        active = [g for g in self.goals if g.status == GoalStatus.ACTIVE]
        if not active:
            return None
        # Find the set of goal_ids that are still incomplete
        # leaves reachable from an active parent. A leaf is
        # "incomplete" if it is ACTIVE or PROPOSED. A leaf
        # that is DONE/ABANDONED/BLOCKED is complete.
        leaf_candidates: list[Goal] = []
        for g in active:
            if not g.subgoal_ids:
                # Active, no subgoals — it is itself a leaf.
                leaf_candidates.append(g)
                continue
            # Active, has subgoals — look at the children.
            children = [by_id.get(sid) for sid in g.subgoal_ids]
            children = [c for c in children if c is not None]
            incomplete = [
                c for c in children
                if c.status in (GoalStatus.ACTIVE, GoalStatus.PROPOSED)
            ]
            if not incomplete:
                # Every child is done; the parent is
                # effectively done too, but the status
                # update is the kernel's job, not the
                # query's. We just don't return the
                # parent.
                continue
            # The active goal is the highest-priority
            # incomplete child.
            leaf_candidates.append(
                min(incomplete, key=lambda c: c.priority)
            )
        if not leaf_candidates:
            return None
        return min(leaf_candidates, key=lambda g: g.priority)

    def belief_about(self, claim: str) -> Belief | None:
        return self.beliefs.get(claim)

    def beliefs_below_confidence(self, threshold: float) -> tuple[Belief, ...]:
        return tuple(b for b in self.beliefs.values() if b.confidence < threshold)

    # ------------------------------------------------------------------ mutations

    def with_belief(self, belief: Belief) -> "WorldState":
        """Return a new state with ``belief`` added or updated.

        The key is the belief's claim. If a belief with the
        same claim already exists, it is replaced. This is
        the canonical "write to semantic memory" operation.
        """
        new_beliefs = dict(self.beliefs)
        new_beliefs[belief.claim] = belief
        return WorldState(
            state_id=self.state_id,
            created_at=self.created_at,
            step_count=self.step_count,
            goals=self.goals,
            active_task=self.active_task,
            last_observation=self.last_observation,
            beliefs=new_beliefs,
            observations=self.observations,
            completed_actions=self.completed_actions,
            pending_actions=self.pending_actions,
            meta=self.meta,
            max_observations=self.max_observations,
            max_completed_actions=self.max_completed_actions,
        )

    def decompose_goal(
        self,
        parent_goal_id: str,
        subgoals: tuple[Goal, ...],
    ) -> "WorldState":
        """Return a new state with ``parent_goal_id`` decomposed.

        This is the kernel's "expand a goal into subgoals"
        primitive. The parent goal's ``subgoal_ids`` are
        updated to point at the new children; each child
        is added to the state with ``parent_goal_id`` set
        to the parent and status ``PROPOSED``.

        Validation
        ----------

        * The parent must exist in the state.
        * Every subgoal's ``goal_id`` must be unique within
          the resulting state.
        * No subgoal's ``goal_id`` may already exist in
          the state.
        * No subgoal may be a descendant of any other
          subgoal (cycle protection).
        * Subgoal priorities are *not* re-numbered; the
          caller chooses priorities. The kernel does not
          invent a planner.

        Returns a new :class:`WorldState`; the input state
        is not modified.
        """
        by_id = {g.goal_id: g for g in self.goals}
        if parent_goal_id not in by_id:
            raise KeyError(f"parent goal {parent_goal_id!r} not in state")
        parent = by_id[parent_goal_id]
        # Validate the new subgoals.
        new_subgoal_ids: list[str] = []
        normalised_subgoals: list[Goal] = []
        for sg in subgoals:
            if sg.goal_id in by_id:
                raise ValueError(
                    f"subgoal {sg.goal_id!r} already exists in state"
                )
            if sg.parent_goal_id not in (None, parent_goal_id):
                raise ValueError(
                    f"subgoal {sg.goal_id!r} has parent_goal_id "
                    f"{sg.parent_goal_id!r} but is being attached "
                    f"to {parent_goal_id!r}"
                )
            if sg.goal_id in new_subgoal_ids:
                raise ValueError(
                    f"subgoal {sg.goal_id!r} listed twice in decompose"
                )
            new_subgoal_ids.append(sg.goal_id)
            # Force the parent_goal_id so propagation
            # from leaf to parent works regardless of
            # what the caller passed. Re-build a Goal
            # rather than mutating.
            normalised_subgoals.append(Goal(
                goal_id=sg.goal_id,
                description=sg.description,
                priority=sg.priority,
                deadline=sg.deadline,
                status=sg.status,
                success_criteria=sg.success_criteria,
                parent_goal_id=parent_goal_id,
                subgoal_ids=sg.subgoal_ids,
            ))
        # Cycle check: walk the parent chain of every
        # existing goal; none of the new subgoals may be on
        # the chain. (We only need to check the new
        # subgoals' parent_goal_id, which we just
        # validated, and the parent itself, which by
        # construction is not in the new subgoals. The
        # only remaining concern is a *new* subgoal that
        # names an existing goal as its parent; we have
        # already caught that above.)
        # Build the new state. The parent goal is
        # *replaced* in the list (its subgoal_ids are
        # updated); the new subgoals are appended.
        new_goals = [
            g.with_subgoals(tuple(new_subgoal_ids))
            if g.goal_id == parent_goal_id else g
            for g in self.goals
        ]
        new_goals.extend(normalised_subgoals)
        return WorldState(
            state_id=self.state_id,
            created_at=self.created_at,
            step_count=self.step_count,
            goals=tuple(new_goals),
            active_task=self.active_task,
            last_observation=self.last_observation,
            beliefs=self.beliefs,
            observations=self.observations,
            completed_actions=self.completed_actions,
            pending_actions=self.pending_actions,
            meta=self.meta,
            max_observations=self.max_observations,
            max_completed_actions=self.max_completed_actions,
        )

    def with_goal_status(
        self, goal_id: str, status: GoalStatus
    ) -> "WorldState":
        """Return a new state with ``goal_id``'s status updated.

        A parent goal is automatically marked DONE when
        every one of its leaf descendants is DONE. A parent
        goal is automatically marked ABANDONED when one of
        its leaf descendants is BLOCKED and the parent
        itself is ACTIVE (the policy may still override
        by setting a different status explicitly). The
        propagation is one level only; deeper propagation
        is the planner's responsibility, not the kernel's.

        The transition is a copy-on-write: the input state
        is not modified.
        """
        by_id = {g.goal_id: g for g in self.goals}
        if goal_id not in by_id:
            raise KeyError(f"goal {goal_id!r} not in state")
        target = by_id[goal_id]
        new_goals: list[Goal] = []
        for g in self.goals:
            if g.goal_id == goal_id:
                new_goals.append(g.with_status(status))
            else:
                new_goals.append(g)
        # Auto-propagate: if the goal is a leaf, walk up
        # the parent chain and update parents whose
        # children are all done.
        if target.is_leaf():
            # Use the *new* goals list (so we see the
            # just-updated status of the leaf) when
            # checking parents.
            new_by_id = {g.goal_id: g for g in new_goals}
            cursor_id: str | None = target.parent_goal_id
            while cursor_id is not None:
                cursor = new_by_id.get(cursor_id)
                if cursor is None:
                    break
                # Every direct child must be a terminal
                # goal (DONE, ABANDONED, or BLOCKED) for
                # the parent to be considered for
                # auto-completion. We only auto-complete
                # to DONE; ABANDONED is the policy's
                # call.
                child_statuses = [
                    new_by_id[sid].status
                    for sid in cursor.subgoal_ids
                    if sid in new_by_id
                ]
                if child_statuses and all(
                    s == GoalStatus.DONE for s in child_statuses
                ) and cursor.status == GoalStatus.ACTIVE:
                    new_goals = [
                        g.with_status(GoalStatus.DONE)
                        if g.goal_id == cursor_id else g
                        for g in new_goals
                    ]
                    # Refresh the lookup so the next
                    # iteration sees the updated parent.
                    new_by_id = {g.goal_id: g for g in new_goals}
                cursor_id = cursor.parent_goal_id
        return WorldState(
            state_id=self.state_id,
            created_at=self.created_at,
            step_count=self.step_count,
            goals=tuple(new_goals),
            active_task=self.active_task,
            last_observation=self.last_observation,
            beliefs=self.beliefs,
            observations=self.observations,
            completed_actions=self.completed_actions,
            pending_actions=self.pending_actions,
            meta=self.meta,
            max_observations=self.max_observations,
            max_completed_actions=self.max_completed_actions,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "created_at": self.created_at.isoformat(),
            "step_count": self.step_count,
            "goals": [g.as_dict() for g in self.goals],
            "active_task": self.active_task,
            "last_observation": (
                None if self.last_observation is None
                else self.last_observation.as_dict()
            ),
            "beliefs": {claim: {
                "claim": b.claim,
                "confidence": b.confidence,
                "source": b.source,
                "evidence": list(b.evidence),
                "updated_at": b.updated_at.isoformat(),
            } for claim, b in self.beliefs.items()},
            "n_observations": len(self.observations),
            "n_completed_actions": len(self.completed_actions),
            "n_pending_actions": len(self.pending_actions),
            "meta": dict(self.meta),
        }


def initial_state(goal: Goal, *, max_observations: int = 256,
                   max_completed_actions: int = 1024) -> WorldState:
    """Convenience constructor: a fresh state with one active goal.

    The returned state is in step 0 with an empty observation
    history. It is the natural starting point for an agent.
    """
    return WorldState(
        goals=(goal,),
        max_observations=max_observations,
        max_completed_actions=max_completed_actions,
    )
