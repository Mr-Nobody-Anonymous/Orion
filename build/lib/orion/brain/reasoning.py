from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class ReasoningStep:
    premise: str
    conclusion: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReasoningTrace:
    steps: tuple[ReasoningStep, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
