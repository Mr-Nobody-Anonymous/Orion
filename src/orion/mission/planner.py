"""The deterministic MissionPlanner and its injectable strategies.

Phase 1 ORION 2.0, corrections #12 and #13:

* The planner is deterministic and explicit. No LLM in Phase 1.
* Strategies are injectable: a :class:`PlannerStrategy` proposes a
  :class:`MissionPlan`; a deterministic validation layer
  (:func:`validate_plan`) decides whether the proposal is structurally
  valid. A future LLM planner plugs in as another strategy and passes
  through the same validation.
* Every planned goal carries expectations (expected_cost,
  required_capabilities, dependencies, success/failure conditions,
  confidence) that later connect planning to economics.

There are NO ``MissionGoal`` classes (correction #2): a plan is built
from the canonical :class:`orion.agent.state.Goal` objects.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from ..agent.state import Goal, GoalStatus
from .objective import MissionObjective


class PlanValidationError(ValueError):
    """A planner strategy proposed a structurally invalid plan."""


@dataclass(frozen=True, slots=True)
class GoalExpectation:
    """What executing one planned goal is expected to take/require."""

    expected_cost: Decimal = Decimal("0")
    expected_duration_seconds: float = 0.0
    required_capabilities: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    success_condition: str = ""
    failure_condition: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.expected_cost, Decimal):
            raise ValueError("expected_cost must be a Decimal")
        if self.expected_cost < 0:
            raise ValueError("expected_cost must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class PlannedGoal:
    """One canonical Goal plus its execution expectations."""

    goal: Goal
    expectation: GoalExpectation


@dataclass(frozen=True, slots=True)
class MissionPlan:
    """A proposal: an ordered goal tree + expectations (no timestamps,
    so identical inputs produce identical, comparable plans)."""

    mission_id: str
    goals: tuple[PlannedGoal, ...]
    root_goal_id: str
    strategy_name: str

    def leaf_goals(self) -> tuple[PlannedGoal, ...]:
        return tuple(pg for pg in self.goals if not pg.goal.subgoal_ids)

    def topological_order(self) -> tuple[PlannedGoal, ...]:
        """Leaf goals in dependency order (stable, deterministic)."""
        leafs = list(self.leaf_goals())
        remaining: dict[str, set[str]] = {
            pg.goal.goal_id: set(pg.expectation.dependencies)
            for pg in leafs
        }
        # honour the plan's original order on ties so two runs over
        # the same plan produce the same order.
        ordered: list[PlannedGoal] = []
        ordered_ids: set[str] = set()
        while remaining:
            ready = [
                gid for gid, deps in remaining.items() if not deps
            ]
            if not ready:
                # Unreachable in practice: validate_plan already
                # rejects cycles. Break to avoid an infinite loop.
                break
            for gid in sorted(ready):
                pg = next(p for p in leafs if p.goal.goal_id == gid)
                ordered.append(pg)
                ordered_ids.add(gid)
                del remaining[gid]
            for deps in remaining.values():
                deps -= ordered_ids
        return tuple(ordered)


class PlannerStrategy(Protocol):
    """A plan proposal strategy (RuleBased today, LLM tomorrow)."""

    name: str

    def propose(
        self, objective: MissionObjective, mission_id: str
    ) -> MissionPlan: ...


# ------------------------------------------------------------- validation


def validate_plan(
    plan: MissionPlan,
    objective: MissionObjective | None = None,
) -> tuple[str, ...]:
    """Structurally validate a proposed plan. Empty tuple = valid.

    Deliberately deterministic and cheap: id uniqueness, dependency
    existence, acyclicity, root presence, capability constraints.
    """
    errors: list[str] = []
    if not plan.goals:
        errors.append("plan has no goals")
        return tuple(errors)
    ids = [pg.goal.goal_id for pg in plan.goals]
    if len(ids) != len(set(ids)):
        errors.append("duplicate goal ids in plan")
    id_set = set(ids)
    if plan.root_goal_id not in id_set:
        errors.append(f"root goal {plan.root_goal_id!r} missing from plan")
    # dependencies must reference known goals
    for pg in plan.goals:
        for dep in pg.expectation.dependencies:
            if dep not in id_set:
                errors.append(
                    f"goal {pg.goal.goal_id!r} depends on unknown goal {dep!r}"
                )
            elif dep == pg.goal.goal_id:
                errors.append(f"goal {pg.goal.goal_id!r} depends on itself")
    # acyclicity via topological sort
    remaining = {
        pg.goal.goal_id: set(pg.expectation.dependencies) & id_set
        for pg in plan.goals
    }
    resolved: set[str] = set()
    while remaining:
        ready = [gid for gid, deps in remaining.items() if deps <= resolved]
        if not ready:
            errors.append("plan contains a dependency cycle")
            break
        for gid in ready:
            resolved.add(gid)
            del remaining[gid]
    # capability constraints (declarative; real enforcement is elsewhere)
    if objective is not None:
        forbidden = set(objective.forbidden_tools)
        allowed = set(objective.allowed_tools)
        for pg in plan.goals:
            for cap in pg.expectation.required_capabilities:
                if cap in forbidden:
                    errors.append(
                        f"goal {pg.goal.goal_id!r} requires forbidden "
                        f"capability {cap!r}"
                    )
                if allowed and cap not in allowed:
                    errors.append(
                        f"goal {pg.goal.goal_id!r} requires capability "
                        f"{cap!r} outside the objective's allowed tools"
                    )
    return tuple(errors)


# -------------------------------------------------------------- strategies


class DocumentSummaryStrategy:
    """Deterministic decomposition for ``kind="document_summary"``.

    Discover -> Read -> Summarize -> Validate, executed against the
    sandboxed test capabilities (correction #22).
    """

    name = "document_summary"

    _LEAVES: tuple[tuple[str, str, str], ...] = (
        ("discover", "Discover documents", "test.fs.discover"),
        ("read", "Read documents", "test.fs.read"),
        ("summarize", "Produce summary", "test.text.summarize"),
        ("validate", "Validate summary", "test.text.validate"),
    )

    def propose(
        self, objective: MissionObjective, mission_id: str
    ) -> MissionPlan:
        root_id = f"{mission_id}:root"
        leaf_ids = tuple(f"{mission_id}:{slug}" for slug, _, _ in self._LEAVES)
        criteria = tuple(m.name for m in objective.success_metrics)
        root = Goal(
            goal_id=root_id,
            description=objective.target_outcome,
            success_criteria=criteria or ("mission objective met",),
            subgoal_ids=leaf_ids,
        )
        planned: list[PlannedGoal] = [
            PlannedGoal(
                goal=root,
                expectation=GoalExpectation(
                    expected_cost=Decimal("0"),
                    success_condition="all subgoals done",
                    confidence=1.0,
                ),
            )
        ]
        previous: str | None = None
        for (slug, description, capability), gid in zip(self._LEAVES, leaf_ids):
            deps = (previous,) if previous is not None else ()
            planned.append(
                PlannedGoal(
                    goal=Goal(
                        goal_id=gid,
                        description=description,
                        parent_goal_id=root_id,
                        success_criteria=(f"{description} succeeded",),
                    ),
                    expectation=GoalExpectation(
                        expected_cost=Decimal("1"),
                        required_capabilities=(capability,),
                        dependencies=deps,
                        success_condition=f"{description.lower()} succeeded",
                        failure_condition=f"{description.lower()} failed",
                        confidence=1.0,
                    ),
                )
            )
            previous = gid
        return MissionPlan(
            mission_id=mission_id,
            goals=tuple(planned),
            root_goal_id=root_id,
            strategy_name=self.name,
        )


class LinearFallbackStrategy:
    """The safe default: one root goal, no invented decomposition."""

    name = "linear_fallback"

    def propose(
        self, objective: MissionObjective, mission_id: str
    ) -> MissionPlan:
        root_id = f"{mission_id}:main"
        return MissionPlan(
            mission_id=mission_id,
            goals=(
                PlannedGoal(
                    goal=Goal(
                        goal_id=root_id,
                        description=objective.target_outcome,
                        success_criteria=tuple(
                            m.name for m in objective.success_metrics
                        )
                        or ("mission objective met",),
                    ),
                    expectation=GoalExpectation(
                        expected_cost=(
                            objective.budget
                            if objective.budget is not None
                            else Decimal("0")
                        ),
                        success_condition="mission objective met",
                        confidence=1.0,
                    ),
                ),
            ),
            root_goal_id=root_id,
            strategy_name=self.name,
        )


_DEFAULT_STRATEGIES: dict[str, PlannerStrategy] = {
    DocumentSummaryStrategy.name: DocumentSummaryStrategy(),
    LinearFallbackStrategy.name: LinearFallbackStrategy(),
}


class MissionPlanner:
    """Runs a strategy and validates its output (correction #12)."""

    def __init__(self, strategy: PlannerStrategy | None = None) -> None:
        self._strategy = strategy

    def plan(self, mission: "Mission") -> MissionPlan:
        strategy = self._strategy
        if strategy is None:
            strategy = _DEFAULT_STRATEGIES.get(
                mission.objective.kind,
                _DEFAULT_STRATEGIES["linear_fallback"],
            )
        plan = strategy.propose(mission.objective, mission.mission_id)
        errors = validate_plan(plan, objective=mission.objective)
        if errors:
            raise PlanValidationError(
                f"invalid plan from strategy {strategy.name!r}: "
                + "; ".join(errors)
            )
        return plan


__all__ = [
    "DocumentSummaryStrategy",
    "GoalExpectation",
    "LinearFallbackStrategy",
    "MissionPlan",
    "MissionPlanner",
    "PlanValidationError",
    "PlannedGoal",
    "PlannerStrategy",
    "validate_plan",
]

