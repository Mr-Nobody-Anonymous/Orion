"""Failure-recovery supervisor: graceful degradation as a first-class path.

Every subsystem failure maps to a documented action. The supervisor never
hides a failure: it records it, degrades the affected capability, and keeps
the rest of ORION running. Trading halts are conservative by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping


class Subsystem(str, Enum):
    MARKET_DATA_API = "market_data_api"
    NEWS_API = "news_api"
    RESEARCH_API = "research_api"
    CLOUD_LLM = "cloud_llm"
    LOCAL_LLM = "local_llm"
    TRAINING = "training"
    DATABASE = "database"
    BROKER = "broker"
    MODEL_INFERENCE = "model_inference"


class DegradationLevel(str, Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class FailureEvent:
    subsystem: Subsystem
    description: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("failure description is required")


@dataclass(frozen=True, slots=True)
class RecoveryAction:
    subsystem: Subsystem
    level: DegradationLevel
    actions: tuple[str, ...]
    trading_permitted: bool
    explanation: str


# Documented playbook: subsystem -> degraded-mode behavior.
_PLAYBOOK: Mapping[Subsystem, tuple[str, ...]] = {
    Subsystem.MARKET_DATA_API: (
        "switch_to_cached_or_backup_data",
        "mark_data_quality_degraded",
        "widen_risk_buffers",
    ),
    Subsystem.NEWS_API: ("disable_news_signals", "rely_on_price_and_fundamentals"),
    Subsystem.RESEARCH_API: ("queue_research_for_retry", "continue_with_local_knowledge"),
    Subsystem.CLOUD_LLM: ("route_to_local_models", "reduce_prompt_complexity"),
    Subsystem.LOCAL_LLM: ("route_to_cloud_if_available", "fall_back_to_statistical_models"),
    Subsystem.TRAINING: ("suspend_training_jobs", "keep_evaluation_only"),
    Subsystem.DATABASE: ("switch_to_in_memory_store", "defer_persistence_writes"),
    Subsystem.BROKER: ("suspend_order_routing", "cancel_stale_orders", "require_manual_restart"),
    Subsystem.MODEL_INFERENCE: ("disable_faulty_model_in_council", "renormalize_member_weights"),
}

class Supervisor:
    """Tracks failures and prescribes the documented degradation for each."""

    def __init__(self, *, broker_failure_tolerance: int = 1, max_stale_data_minutes: int = 30) -> None:
        if broker_failure_tolerance < 0:
            raise ValueError("broker_failure_tolerance must be non-negative")
        if max_stale_data_minutes < 1:
            raise ValueError("max_stale_data_minutes must be at least one")
        self.broker_failure_tolerance = broker_failure_tolerance
        self.max_stale_data = timedelta(minutes=max_stale_data_minutes)
        self._failures: list[FailureEvent] = []
        self._broker_failures = 0
        self._halted = False
        self._disabled_models: set[str] = set()

    def report(self, event: FailureEvent) -> RecoveryAction:
        self._failures.append(event)
        actions = _PLAYBOOK[event.subsystem]
        if event.subsystem is Subsystem.BROKER:
            self._broker_failures += 1
            if self._broker_failures > self.broker_failure_tolerance:
                self._halted = True
                return RecoveryAction(event.subsystem, DegradationLevel.HALTED, actions, False,
                                      "repeated broker failure: trading halted pending manual restart")
            return RecoveryAction(event.subsystem, DegradationLevel.DEGRADED, actions, False,
                                  "broker failure: order routing suspended")
        if event.subsystem is Subsystem.MODEL_INFERENCE:
            self._disable_model_from(event.description)
            return RecoveryAction(event.subsystem, DegradationLevel.DEGRADED, actions, True,
                                  "faulty model disabled; council renormalized")
        if event.subsystem in {Subsystem.LOCAL_LLM, Subsystem.CLOUD_LLM}:
            return RecoveryAction(event.subsystem, DegradationLevel.DEGRADED, actions, True,
                                  "inference degraded: fallback routing active")
        if event.subsystem is Subsystem.DATABASE:
            return RecoveryAction(event.subsystem, DegradationLevel.DEGRADED, actions, True,
                                  "persistence degraded: in-memory fallback")
        return RecoveryAction(event.subsystem, DegradationLevel.DEGRADED, actions, True,
                              f"{event.subsystem.value} degraded: playbook applied")

    @staticmethod
    def _extract_model_name(description: str) -> str | None:
        for token in description.replace(",", " ").replace(":", " ").split():
            if token.isidentifier() and ("model" in token.lower() or token.startswith("orion")):
                return token
        return None

    def _disable_model_from(self, description: str) -> None:
        name = self._extract_model_name(description)
        if name:
            self._disabled_models.add(name)

    def report_stale_data(self, *, age: timedelta) -> RecoveryAction:
        if age > self.max_stale_data:
            return RecoveryAction(Subsystem.MARKET_DATA_API, DegradationLevel.CRITICAL,
                                  ("block_new_entries", "mark_regime_unknown", "exit_rules_only"),
                                  False, f"data is stale by {age}; new entries blocked")
        return RecoveryAction(Subsystem.MARKET_DATA_API, DegradationLevel.NOMINAL, (), True,
                              "data freshness acceptable")

    @property
    def halted(self) -> bool:
        return self._halted

    def resume(self, *, actor: str) -> bool:
        """Manual restart after a halt; returns whether a halt was cleared."""
        if not self._halted:
            return False
        self._halted = False
        self._broker_failures = 0
        self._failures.append(FailureEvent(Subsystem.BROKER, f"manual resume by {actor}"))
        return True

    def disabled_models(self) -> tuple[str, ...]:
        return tuple(sorted(self._disabled_models))

    def failures(self) -> tuple[FailureEvent, ...]:
        return tuple(self._failures)

    def health(self) -> dict[str, str]:
        counts: dict[str, int] = {}
        for failure in self._failures:
            counts[failure.subsystem.value] = counts.get(failure.subsystem.value, 0) + 1
        return {name: ("failing" if count >= 3 else "degraded" if count else "nominal")
                for name, count in sorted(counts.items())} or {"all": "nominal"}

