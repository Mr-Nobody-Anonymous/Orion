"""The ORION mission layer — Phase 1 vertical slice.

Canonical import paths::

    from orion.mission import (
        Mission, MissionStatus, MissionEngine, MissionObjective,
        MetricSpec, MissionPlanner, OutcomeLedger, OutcomeRecord,
        Budget, MissionEvent, MissionStore,
    )

Concept boundaries (do not collapse them):

* MISSION — persistence/orchestration above the goal system
* OBJECTIVE — the measurable intent (never execution authority)
* GOAL — canonical :class:`orion.agent.state.Goal` objects only
* TASK — a planned capability step (see ``orion.mission.adapter``)
* POLICY / RISK — remain in the existing safety components
* ACCOUNTING — the append-only outcome ledger + reservation budget
"""

from .adapter import (
    ExecutionResult,
    KernelMissionAdapter,
    MissionExecutionAdapter,
    SafeCapabilityAdapter,
    ScriptStep,
)
from .budget import Budget, BudgetError, Reservation
from .engine import MetricReading, MissionEngine, MissionRunResult
from .events import DomainEvents, EventCategory, MissionEvent, domain_event
from .goal_bridge import BrainGoalAdapter, MissionGoalCoordinator
from .ledger import LedgerAggregates, OutcomeLedger, OutcomeRecord
from .mission import (
    LEGAL_TRANSITIONS,
    Mission,
    MissionStateError,
    MissionStatus,
    new_mission,
)
from .objective import (
    EconomicTarget,
    MetricOperator,
    MetricSpec,
    MetricType,
    MissionObjective,
    ValidationError,
    evaluate_metric,
)
from .persistence import ConcurrentUpdateError, MissionStore
from .planner import (
    DocumentSummaryStrategy,
    GoalExpectation,
    LinearFallbackStrategy,
    MissionPlan,
    MissionPlanner,
    PlanValidationError,
    PlannedGoal,
    PlannerStrategy,
    validate_plan,
)

__all__ = [
    "BrainGoalAdapter",
    "Budget",
    "BudgetError",
    "ConcurrentUpdateError",
    "DocumentSummaryStrategy",
    "DomainEvents",
    "EconomicTarget",
    "EventCategory",
    "ExecutionResult",
    "GoalExpectation",
    "KernelMissionAdapter",
    "LEGAL_TRANSITIONS",
    "LedgerAggregates",
    "LinearFallbackStrategy",
    "MetricOperator",
    "MetricReading",
    "MetricSpec",
    "MetricType",
    "Mission",
    "MissionEngine",
    "MissionEvent",
    "MissionExecutionAdapter",
    "MissionGoalCoordinator",
    "MissionObjective",
    "MissionPlan",
    "MissionPlanner",
    "MissionRunResult",
    "MissionStateError",
    "MissionStatus",
    "MissionStore",
    "OutcomeLedger",
    "OutcomeRecord",
    "PlanValidationError",
    "PlannedGoal",
    "PlannerStrategy",
    "Reservation",
    "SafeCapabilityAdapter",
    "ScriptStep",
    "ValidationError",
    "domain_event",
    "evaluate_metric",
    "new_mission",
    "validate_plan",
]
