from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class PlanStep:
    name: str
    status: str = "pending"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    objective: str
    steps: tuple[PlanStep, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
