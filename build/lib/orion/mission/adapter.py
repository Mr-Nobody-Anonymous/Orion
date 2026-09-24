"""Mission execution adapters — the seam to existing execution.

Phase 1 ORION 2.0, corrections #14, #19, #20:

    MissionEngine
        -> MissionExecutionAdapter   (this module)
        -> existing Agent kernel     (orion.agent.kernel.Agent / AgentRun)
        -> existing CapabilityExecutor (permission + risk gates intact)

The engine never embeds the cognitive loop and never touches live
broker execution. ``SafeCapabilityAdapter`` dispatches through the
existing :class:`~orion.agent.executor.CapabilityExecutor`, so the
existing permission check and risk gate run unchanged; Phase 1 only
ever registers LOW-risk deterministic test capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from ..agent.executor import (
    CapabilityContext,
    CapabilityExecutor,
    CapabilityResult,
)
from ..agent.kernel import Agent, AgentRun
from ..agent.state import Action, Goal, Observation
from .budget import BudgetError
from .planner import MissionPlan


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Adapter-normalized result of one capability execution."""

    success: bool
    output: Mapping[str, Any] = field(default_factory=dict)
    cost: Decimal = Decimal("0")
    error: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


class MissionExecutionAdapter(Protocol):
    """The seam the engine drives; swappable for other executors."""

    def execute(
        self, capability: str, args: Mapping[str, Any], *, goal_id: str
    ) -> ExecutionResult: ...


@dataclass(frozen=True, slots=True)
class ScriptStep:
    """One planned action: which goal, which capability, what it costs."""

    goal_id: str
    capability: str
    args: Mapping[str, Any] = field(default_factory=dict)
    expected_cost: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class KernelRunResult:
    """What one pass through the existing kernel produced."""

    run: AgentRun | None
    steps_taken: int
    stopped_reason: str  # done | budget_exhausted | exhausted
    outcomes: tuple[tuple[str, str, ExecutionResult], ...] = ()


class SafeCapabilityAdapter:
    """Dispatches capability calls through the existing CapabilityExecutor.

    The executor enforces registry membership, permissions, and the
    risk gate — unchanged safety-critical behaviour (correction #19).
    Costs arrive as floats from the executor and are converted to
    Decimal exactly via ``str``.
    """

    def __init__(
        self,
        executor: CapabilityExecutor,
        *,
        agent_id: str = "mission-agent",
        approved_permissions: frozenset[str] = frozenset({"read_data"}),
    ) -> None:
        self._executor = executor
        self._agent_id = agent_id
        self._permissions = approved_permissions

    def execute(
        self, capability: str, args: Mapping[str, Any], *, goal_id: str
    ) -> ExecutionResult:
        context = CapabilityContext(
            caller=self._agent_id,
            goal_id=goal_id,
            approved_permissions=self._permissions,
        )
        result: CapabilityResult = self._executor.execute(
            capability, dict(args), context
        )
        output = (
            dict(result.output)
            if isinstance(result.output, Mapping)
            else {"value": result.output}
        )
        return ExecutionResult(
            success=result.success,
            output=output,
            cost=Decimal(str(result.cost_units)),
            error=result.error,
            provenance=dict(result.provenance),
        )


class KernelMissionAdapter:
    """Runs a mission's script through the EXISTING agent kernel.

    The cognitive loop is the canonical one
    (:meth:`orion.agent.kernel.Agent.step`); this adapter only scripts
    the deterministic policy and dispatches actions through a
    :class:`MissionExecutionAdapter`, producing a real
    :class:`~orion.agent.kernel.AgentRun` for audit and recovery.
    """

    COMPLETE_CAPABILITY = "mission.complete"

    def __init__(
        self,
        capabilities: MissionExecutionAdapter,
        *,
        budget_gate: Callable[[ScriptStep], None] | None = None,
        agent_id: str = "mission-agent",
    ) -> None:
        self._capabilities = capabilities
        self._budget_gate = budget_gate
        self._agent_id = agent_id

    def run(
        self,
        mission_id: str,
        root_goal: Goal,
        script: tuple[ScriptStep, ...],
        *,
        max_actions: int = 100,
    ) -> KernelRunResult:
        # Deterministic dataflow: the output of the last successful
        # step is carried into the next step's input. Planner-specified
        # ``ScriptStep.args`` always win over carried keys. The policy
        # and the execution merge identically, so the audited Action
        # args match what actually ran.
        carried: dict[str, Any] = {}

        # Deterministic policy: walk the script in order, then finish.
        def policy(ctx) -> Action:
            # At policy time ``step_count`` is the number of steps
            # already taken (the kernel increments it after the policy
            # runs), so it is exactly the index of the script step to
            # choose now.
            index = ctx.state.step_count
            if index < len(script):
                step = script[index]
                return Action(
                    capability=step.capability,
                    args={**carried, **dict(step.args)},
                    rationale=f"mission {mission_id} goal {step.goal_id}",
                )
            return Action(
                capability=self.COMPLETE_CAPABILITY,
                args={},
                rationale=f"mission {mission_id} script complete",
            )

        agent = Agent(goal=root_goal, policy=policy)
        outcomes: list[tuple[str, str, ExecutionResult]] = []
        actions = 0
        cost_used = 0.0
        stopped = "done"
        observation: Observation | None = None
        while True:
            step_result = agent.step(observation=observation)
            action = step_result.action
            if action.capability == self.COMPLETE_CAPABILITY:
                break
            index = min(step_result.state.step_count - 1, len(script) - 1)
            step = script[index]
            if self._budget_gate is not None:
                try:
                    self._budget_gate(step)
                except BudgetError:
                    stopped = "budget_exhausted"
                    break
            args = {**carried, **dict(step.args)}
            result = self._capabilities.execute(
                step.capability, args, goal_id=step.goal_id
            )
            outcomes.append((step.goal_id, step.capability, result))
            actions += 1
            cost_used += float(result.cost)
            if result.success:
                carried = dict(result.output)
            observation = Observation(
                kind="capability_result",
                payload={
                    "capability": step.capability,
                    "success": result.success,
                    "error": result.error,
                    "cost_units": float(result.cost),
                },
                source=f"mission:{mission_id}",
            )
            if actions >= max_actions:
                stopped = "exhausted"
                break
        run = AgentRun(
            run_id=uuid4().hex,
            state=agent.state,
            loop_status="done" if stopped == "done" else "blocked",
            termination_reason=stopped,
            steps_taken=actions,
            cost_units_used=cost_used,
        )
        return KernelRunResult(
            run=run,
            steps_taken=actions,
            stopped_reason=stopped,
            outcomes=tuple(outcomes),
        )


__all__ = [
    "ExecutionResult",
    "KernelMissionAdapter",
    "KernelRunResult",
    "MissionExecutionAdapter",
    "SafeCapabilityAdapter",
    "ScriptStep",
]

