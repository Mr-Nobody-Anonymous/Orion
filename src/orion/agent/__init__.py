"""ORION agent runtime: the smallest kernel that closes the
"pipeline vs agent" gap.

The 2026-08-28 review said the single biggest missing piece is
the transition from a one-shot pipeline to a persistent agent
loop. This package builds the *smallest piece* that
distinguishes an agent from a pipeline: **persistent state
with an explicit ``step(observation) -> action`` interface**.
Everything else (planning, hierarchical decomposition,
long-horizon execution, self-directed learning) is downstream
of that primitive.

The kernel is intentionally small. It does not plan, it does
not learn, it does not call a capability. It is the
*substrate* the planner / learner / capability-manager plug
into.
"""

from __future__ import annotations

from .executor import (
    CapabilityContext,
    CapabilityConstraints,
    CapabilityExecutor,
    CapabilityNotFoundError,
    CapabilityResult,
    PermissionDeniedError,
    RiskGateError,
)
from .kernel import (
    Agent,
    Policy,
    PolicyContext,
    StepResult,
    belief_update_policy,
    wait_policy,
)
from .memory import (
    AgentMemory,
    CapabilityScore,
    Episode,
    Procedure,
    SemanticClaim,
)
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

__all__ = [
    "Action",
    "ActionOutcome",
    "Agent",
    "AgentMemory",
    "Belief",
    "CapabilityContext",
    "CapabilityConstraints",
    "CapabilityExecutor",
    "CapabilityNotFoundError",
    "CapabilityResult",
    "CapabilityScore",
    "Episode",
    "Goal",
    "GoalStatus",
    "Observation",
    "PermissionDeniedError",
    "Policy",
    "PolicyContext",
    "Procedure",
    "RiskGateError",
    "SemanticClaim",
    "StepResult",
    "WorldState",
    "belief_update_policy",
    "wait_policy",
    "initial_state",
]
