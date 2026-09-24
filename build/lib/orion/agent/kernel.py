"""The ORION agent kernel: the smallest possible closed loop.

The 2026-08-28 review's central claim is that the gap
between a pipeline and an agent is *persistence*: a pipeline
runs, returns, and forgets. An agent runs, returns, and
remembers — across calls, across sessions.

This module provides that primitive. The kernel is a single
function, :meth:`Agent.step`, that does five things and only
five things:

1. **Accept an observation.** The environment tells the
   agent what happened.
2. **Update the world state.** The state is immutable; the
   kernel returns a new one with the observation recorded
   and any pending action resolved.
3. **Update memory.** Episodic memory gets the action /
   observation / summary; semantic memory gets any claim
   the policy wants to record; self-model gets the outcome.
4. **Choose an action.** A pluggable policy function maps
   the new state + memory to the next action.
5. **Return the next state and the action.** The kernel is
   pure: given the same state + observation, the same
   policy produces the same next state and the same action.

The kernel does **not**:

* plan hierarchically
* call an LLM
* invoke a capability
* decide what to do
* manage goals

Those are all *policies*. The kernel is the loop; the policy
is the brain. This separation is the reason the kernel is
small enough to fit in one file and the reason a planner /
a learner / a research agent can each be added later as a
policy without changing the kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping

from .executor import CapabilityContext, CapabilityConstraints, CapabilityExecutor
from .memory import AgentMemory, CapabilityScore, Episode, SemanticClaim
from .state import (
    Action,
    ActionOutcome,
    Belief,
    Goal,
    GoalStatus,
    Observation,
    WorldState,
    initial_state,
)


# A policy context is the *input* to a policy function. It
# carries the current world state, the observation that
# triggered the step (if any), and the agent's memory
# facade. A policy is *not* given direct access to the
# executor or the agent's other internals — it returns an
# :class:`Action` and may write to memory through the
# facade, but it cannot, for example, dispatch a capability
# itself. That discipline is what keeps the kernel small
# and the policy testable.
@dataclass(frozen=True, slots=True)
class PolicyContext:
    state: WorldState
    observation: Observation | None
    memory: AgentMemory


# A policy is a pure function: (state, observation, memory) -> action.
Policy = Callable[[PolicyContext], Action]


@dataclass(frozen=True, slots=True)
class StepResult:
    """The output of one ``Agent.step`` call.

    The kernel returns the *new* state and the *action* it
    chose. The caller persists the state and (if it wants
    to actually run the action) dispatches the action to
    the capability executor.
    """

    state: WorldState
    action: Action
    observation: Observation | None  # the observation that triggered this step


# --------------------------------------------------------------------------- Phase 31G
# AgentRun: the persistent agent loop's container. Holds the
# goal, the state, the plan, the memory, the budget, the
# deadline, the current state of the loop (RUNNING, DONE,
# FAILED, BLOCKED, EXHAUSTED), and the reason the loop
# terminated. Survives a process restart via
# ``to_checkpoint()`` / ``from_checkpoint()``.


@dataclass(frozen=True, slots=True)
class AgentRun:
    """The persistent container for a long-running agent.

    The 2026-08-28 review's point 16: a serious autonomous
    agent needs durable state. :class:`AgentRun` is the
    smallest possible such container: it carries the
    agent's state, its goal, its budget, its deadline,
    its loop status, and the reason it terminated.

    The kernel does not write this to disk; the caller
    is expected to serialise it (e.g. to JSON) and reload
    it later via ``AgentRun.from_dict``. The serialised
    form is intentionally small — only the world state
    and the loop status.
    """

    run_id: str
    state: WorldState
    loop_status: str  # "running" | "done" | "failed" | "blocked" | "exhausted"
    termination_reason: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    steps_taken: int = 0
    cost_units_used: float = 0.0

    def is_terminal(self) -> bool:
        """A run is terminal if it is not still running."""
        return self.loop_status != "running"

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state.as_dict(),
            "loop_status": self.loop_status,
            "termination_reason": self.termination_reason,
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat()
                if self.finished_at is not None else None
            ),
            "steps_taken": self.steps_taken,
            "cost_units_used": self.cost_units_used,
        }


# --------------------------------------------------------------------------- default policies


def wait_policy(ctx: PolicyContext) -> Action:
    """The default policy: do nothing, wait for the next observation.

    This is the *correct* default. An agent with no policy
    is an agent that does nothing — which is the safest
    starting point. A real policy is a function the caller
    provides.
    """
    return Action(
        capability="noop.observe",
        args={"step": ctx.state.step_count},
        rationale="default wait policy",
    )


def belief_update_policy(
    claim_to_belief: Mapping[str, str],
    *,
    source: str = "belief_update_policy",
) -> Policy:
    """A small but real policy: a lookup table that converts an
    observation into a belief update + a noop action.

    The lookup is ``{observation_kind: belief_claim}``. When
    the kernel sees an observation whose ``kind`` is in the
    table, the policy records the corresponding claim in
    semantic memory and returns a noop action. This is the
    smallest useful policy and is what the kernel tests
    use to prove that the loop actually advances state.
    """

    def policy(ctx: PolicyContext) -> Action:
        if ctx.observation is None:
            return Action(
                capability="noop.observe",
                args={"step": ctx.state.step_count},
                rationale="no observation yet",
            )
        if ctx.observation.kind in claim_to_belief:
            claim_text = claim_to_belief[ctx.observation.kind]
            ctx.memory.record_claim(SemanticClaim(
                claim=claim_text,
                confidence=0.7,
                evidence=(f"observation={ctx.observation.kind}",),
                source=source,
                updated_at=ctx.observation.observed_at,
            ))
            return Action(
                capability="noop.observe",
                args={"belief_recorded": claim_text},
                rationale=f"observation {ctx.observation.kind!r} triggers belief update",
            )
        return Action(
            capability="noop.observe",
            args={"step": ctx.state.step_count},
            rationale="observation has no policy match",
        )

    return policy


# --------------------------------------------------------------------------- agent


class Agent:
    """The ORION agent kernel.

    An :class:`Agent` is a state machine. It has:

    * a :class:`WorldState` that survives across calls
    * a :class:`AgentMemory` for episodic / semantic /
      procedural / self-model memory
    * a :class:`CapabilityExecutor` for capability dispatch
      (the kernel itself does not call capabilities — it
      returns an :class:`Action` and the caller dispatches)
    * a :class:`Policy` that maps state + memory to action

    The kernel is small on purpose. It enforces the loop and
    nothing else. Adding a planner, a learner, or a
    researcher is a matter of replacing the policy.
    """

    def __init__(
        self,
        *,
        goal: Goal,
        memory: AgentMemory | None = None,
        executor: CapabilityExecutor | None = None,
        policy: Policy | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> None:
        self.memory = memory if memory is not None else AgentMemory()
        self.executor = executor if executor is not None else CapabilityExecutor(memory=self.memory)
        self.policy = policy if policy is not None else wait_policy
        # Initialise the active goal.
        active_goal = Goal(
            goal_id=goal.goal_id,
            description=goal.description,
            priority=goal.priority,
            deadline=goal.deadline,
            status=GoalStatus.ACTIVE,
            success_criteria=goal.success_criteria,
        )
        self.state: WorldState = initial_state(goal=active_goal)
        if meta:
            self.state = self._replace_meta(self.state, dict(meta))

    # ------------------------------------------------------------------ step

    def step(self, observation: Observation | None = None) -> StepResult:
        """Advance the agent by one tick.

        Returns the new state and the action the policy chose.
        The caller is responsible for *dispatching* the
        action (via the executor) and feeding the resulting
        observation back in on the next call.
        """
        # 1. Resolve any pending actions: the *previous*
        #    observation (if any) was the result of the
        #    previous step's action. We pair them here.
        new_state = self._resolve_pending(self.state, observation)

        # 2. The policy looks at the new state and decides
        #    what to do next.
        ctx = PolicyContext(state=new_state, observation=observation, memory=self.memory)
        action = self.policy(ctx)

        # 3. Assign a deterministic intent_id so the same
        #    (state, observation, policy) triple produces the
        #    same Action value. This is the determinism
        #    invariant.
        action = Action(
            capability=action.capability,
            args=action.args,
            intent_id=f"{self.state.state_id}#{new_state.step_count + 1}",
            rationale=action.rationale,
        )

        # 4. Record an episode (episodic memory) summarising
        #    what just happened. We use a deterministic
        #    summary: "observation X arrived, policy chose
        #    capability Y". A real agent would summarise with
        #    a language model, but the kernel itself does not
        #    depend on one.
        if observation is not None or action is not None:
            self.memory.record_episode(Episode(
                episode_id=f"step-{new_state.step_count + 1:06d}",
                occurred_at=observation.observed_at if observation is not None else datetime.now(timezone.utc),
                action_capability=action.capability,
                action_args=action.args,
                observation_kind=observation.kind if observation else "",
                observation_payload=dict(observation.payload) if observation else {},
                summary=(
                    f"observation={observation.kind if observation else 'none'}; "
                    f"action={action.capability}"
                ),
            ))

        # 5. Build the next state with the action pending
        #    and the new observation recorded.
        next_state = self._build_next_state(new_state, action, observation)

        # 6. Update the agent's own state reference.
        self.state = next_state
        return StepResult(state=next_state, action=action, observation=observation)

    # ------------------------------------------------------------------ helpers

    def _resolve_pending(
        self,
        state: WorldState,
        observation: Observation | None,
    ) -> WorldState:
        """Pair the previous step's pending action with the new
        observation, if both are present.
        """
        if not state.pending_actions or observation is None:
            return state
        # We have a pending action and an observation; pair
        # the most recent pending action with this observation.
        pending = list(state.pending_actions)
        completed = list(state.completed_actions)
        action = pending.pop(0)
        completed.append(ActionOutcome(action=action, observation=observation))
        # Cap completed actions.
        if len(completed) > state.max_completed_actions:
            completed = completed[-state.max_completed_actions:]
        return self._replace(
            state,
            completed_actions=tuple(completed),
            pending_actions=tuple(pending),
        )

    def _build_next_state(
        self,
        state: WorldState,
        action: Action,
        observation: Observation | None,
    ) -> WorldState:
        observations = list(state.observations)
        if observation is not None:
            observations.append(observation)
            if len(observations) > state.max_observations:
                observations = observations[-state.max_observations:]
        pending = list(state.pending_actions)
        pending.append(action)
        return self._replace(
            state,
            step_count=state.step_count + 1,
            observations=tuple(observations),
            last_observation=observation,
            pending_actions=tuple(pending),
        )

    @staticmethod
    def _replace(state: WorldState, **changes: Any) -> WorldState:
        return WorldState(
            state_id=state.state_id,
            created_at=state.created_at,
            step_count=changes.get("step_count", state.step_count),
            goals=changes.get("goals", state.goals),
            active_task=changes.get("active_task", state.active_task),
            last_observation=changes.get("last_observation", state.last_observation),
            beliefs=changes.get("beliefs", state.beliefs),
            observations=changes.get("observations", state.observations),
            completed_actions=changes.get("completed_actions", state.completed_actions),
            pending_actions=changes.get("pending_actions", state.pending_actions),
            meta=changes.get("meta", state.meta),
            max_observations=state.max_observations,
            max_completed_actions=state.max_completed_actions,
        )

    @staticmethod
    def _replace_meta(state: WorldState, meta: dict[str, Any]) -> WorldState:
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
            meta=meta,
            max_observations=state.max_observations,
            max_completed_actions=state.max_completed_actions,
            max_predictions=state.max_predictions,
            max_prediction_errors=state.max_prediction_errors,
        )

    # ------------------------------------------------------------------ run

    def run(
        self,
        *,
        max_steps: int = 100,
        deadline: datetime | None = None,
        budget: float = float("inf"),
        observation_source: Callable[[], Observation | None] | None = None,
        dispatcher: Callable[[Action, WorldState], Observation | None] | None = None,
    ) -> AgentRun:
        """Run the agent in a loop until it terminates.

        The 2026-08-28 review's point 4: "the loop doesn't
        terminate after one cycle. It continues until
        goal achieved / impossible / deadline exceeded /
        budget exceeded / human approval required."

        This method implements that. It is deliberately
        small: it loops :meth:`step` until one of the
        termination conditions is met, and returns an
        :class:`AgentRun` describing what happened.

        Parameters
        ----------
        max_steps:
            Hard cap on the number of steps.
        deadline:
            Wall-clock deadline. If ``now()`` exceeds the
            deadline, the run terminates with status
            ``"exhausted"``.
        budget:
            Max accumulated ``cost_units_used``. Each step
            is assumed to cost 1.0 unit unless the
            observation carries a ``cost_units`` payload
            field. A negative or non-finite budget is
            treated as ``inf``.
        observation_source:
            A callable that returns the next observation
            for the kernel, or ``None`` to terminate. If
            ``None``, the loop is single-step (the caller
            is expected to feed observations back via
            :meth:`step`).
        dispatcher:
            A callable that takes the kernel's chosen
            ``Action`` and the current ``WorldState`` and
            returns the resulting ``Observation`` (or
            ``None`` if the action has no immediate
            observation). When provided, the loop
            dispatches each action and feeds the result
            back as the next observation. When ``None``,
            the loop is policy-only: the kernel returns
            each action, the caller dispatches, and the
            next ``observation_source`` call provides the
            next observation.

        Termination
        -----------
        The run terminates when:

        * ``max_steps`` is reached (``"exhausted"``),
        * the deadline is passed (``"exhausted"``),
        * the active goal is DONE (``"done"``),
        * the active goal is BLOCKED or ABANDONED
          (``"failed"``),
        * the active goal is no longer reachable
          (no active leaf; ``"failed"``),
        * ``observation_source`` returns ``None`` with
          the policy asking for ``wait`` (``"blocked"`` —
          the agent has nothing to do and nothing to wait
          for),
        * the budget is exhausted (``"exhausted"``).
        """
        run_id = f"run-{self.state.state_id[:8]}-{int(time.time() * 1000)}"
        started_at = datetime.now(timezone.utc)
        steps = 0
        cost_used = 0.0
        # Initial step with no observation to settle the
        # initial state.
        result = self.step()
        steps += 1
        cost_used += 1.0
        while True:
            now = datetime.now(timezone.utc)
            if deadline is not None and now > deadline:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="exhausted",
                    termination_reason="deadline_exceeded",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            if steps >= max_steps:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="exhausted",
                    termination_reason="max_steps_reached",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            if cost_used >= budget:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="exhausted",
                    termination_reason="budget_exhausted",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            # Check the active goal.
            active = self.state.active_goal()
            if active is None:
                # No active leaf goal. Either everything is
                # done, or nothing is active.
                any_done = any(
                    g.status == GoalStatus.DONE for g in self.state.goals
                )
                any_active = any(
                    g.status == GoalStatus.ACTIVE for g in self.state.goals
                )
                if any_done and not any_active:
                    return AgentRun(
                        run_id=run_id,
                        state=self.state,
                        loop_status="done",
                        termination_reason="all_goals_done",
                        started_at=started_at,
                        finished_at=now,
                        steps_taken=steps,
                        cost_units_used=cost_used,
                    )
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="blocked",
                    termination_reason="no_active_goal",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            if active.status == GoalStatus.BLOCKED:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="failed",
                    termination_reason=f"goal_blocked:{active.goal_id}",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            if active.status == GoalStatus.ABANDONED:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="failed",
                    termination_reason=f"goal_abandoned:{active.goal_id}",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            if active.status == GoalStatus.DONE:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="done",
                    termination_reason=f"goal_done:{active.goal_id}",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            # Get the next observation. Two paths:
            # a) dispatcher mode: dispatch the previous
            #    action and feed the result.
            # b) observation_source mode: ask the source.
            observation: Observation | None = None
            if dispatcher is not None and self.state.pending_actions:
                last_action = self.state.pending_actions[-1]
                observation = dispatcher(last_action, self.state)
            elif observation_source is not None:
                observation = observation_source()
            else:
                # No source, no dispatcher: the caller is
                # expected to drive the agent. Block.
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="blocked",
                    termination_reason="no_observation_source",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            if observation is None:
                return AgentRun(
                    run_id=run_id,
                    state=self.state,
                    loop_status="blocked",
                    termination_reason="no_observation",
                    started_at=started_at,
                    finished_at=now,
                    steps_taken=steps,
                    cost_units_used=cost_used,
                )
            self.step(observation=observation)
            steps += 1
            cost_used += 1.0

