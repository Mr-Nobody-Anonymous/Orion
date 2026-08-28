"""Alerts: declarative rules over metrics and health.

A :class:`Rule` is a small predicate.  :class:`AlertEngine` evaluates
every registered rule, raises an :class:`Alert` for each one that
fires, and keeps the most recent state.  Rules are pure functions
of the inputs they were given at registration time; they should
*not* mutate the system.

The default engine is stateless; pass it a snapshot of metrics
(:func:`orion.ops.metrics.metrics_registry.snapshot`) and a
:class:`HealthReport` and it will produce a list of alerts.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable, Mapping

from .health import HealthReport, HealthStatus
from .metrics import metrics_registry


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class Alert:
    rule_id: str
    severity: AlertSeverity
    message: str
    raised_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Rule:
    """A named rule: ``predicate(metrics, health) -> Alert | None``."""

    rule_id: str
    severity: AlertSeverity
    description: str
    predicate: Callable[[Mapping[str, object], HealthReport], Alert | None]


# The metrics module exposes a plain dict from ``snapshot()``; we type it
# as ``Mapping[str, object]`` for callers.  The ``MetricsSnapshot`` alias
# is purely documentary.
MetricsSnapshot = Mapping[str, object]  # type: ignore[misc]  # re-defined for documentation


class AlertEngine:
    """Stateless rule evaluator.

    The engine is thread-safe and re-entrant: multiple callers can
    evaluate at the same time without interfering.  Rules are
    registered at construction; new rules can be added via
    :meth:`add_rule` for tests.
    """

    def __init__(self, rules: Iterable[Rule] = ()) -> None:
        self._rules: dict[str, Rule] = {}
        self._lock = threading.RLock()
        for rule in rules:
            self.add_rule(rule)

    def add_rule(self, rule: Rule) -> None:
        with self._lock:
            if rule.rule_id in self._rules:
                raise ValueError(f"rule {rule.rule_id!r} already registered")
            self._rules[rule.rule_id] = rule

    def rules(self) -> tuple[Rule, ...]:
        with self._lock:
            return tuple(self._rules.values())

    def evaluate(
        self,
        *,
        metrics_snapshot: Mapping[str, object] | None = None,
        health_report: HealthReport | None = None,
    ) -> tuple[Alert, ...]:
        """Evaluate every rule and return the alerts that fired.

        ``metrics_snapshot`` defaults to the process-wide
        :data:`metrics_registry` snapshot.  ``health_report`` is
        optional; rules that need it will see an empty report if not
        supplied (which is the same as ``OK`` for the worst-status
        aggregator).
        """
        snap = metrics_snapshot if metrics_snapshot is not None else metrics_registry.snapshot()
        report = health_report or HealthReport(results=())
        alerts: list[Alert] = []
        for rule in self.rules():
            try:
                alert = rule.predicate(snap, report)
            except Exception as exc:  # noqa: BLE001 — rule bugs must not crash the engine
                alert = Alert(
                    rule_id=rule.rule_id,
                    severity=AlertSeverity.WARNING,
                    message=f"rule {rule.rule_id!r} raised: {exc!r}",
                )
            if alert is not None:
                alerts.append(alert)
        return tuple(alerts)


# ---- standard rules ----------------------------------------------------


def rule_broker_disconnected(rule_id: str = "broker.disconnected") -> Rule:
    def _pred(_: Mapping[str, object], health: HealthReport) -> Alert | None:
        for result in health.results:
            if result.name == "broker_connectivity" and result.status is HealthStatus.CRITICAL:
                return Alert(
                    rule_id=rule_id,
                    severity=AlertSeverity.CRITICAL,
                    message=f"broker disconnected: {result.detail}",
                    context={"detail": result.detail},
                )
        return None

    return Rule(
        rule_id=rule_id,
        severity=AlertSeverity.CRITICAL,
        description="Broker connection is down",
        predicate=_pred,
    )


def rule_data_stale(rule_id: str = "data.stale") -> Rule:
    def _pred(_: Mapping[str, object], health: HealthReport) -> Alert | None:
        for result in health.results:
            if result.name == "data_freshness" and result.status in (
                HealthStatus.DEGRADED,
                HealthStatus.CRITICAL,
            ):
                sev = (
                    AlertSeverity.CRITICAL
                    if result.status is HealthStatus.CRITICAL
                    else AlertSeverity.WARNING
                )
                return Alert(
                    rule_id=rule_id,
                    severity=sev,
                    message=f"market data is stale: {result.detail}",
                    context={"detail": result.detail},
                )
        return None

    return Rule(
        rule_id=rule_id,
        severity=AlertSeverity.WARNING,
        description="Market data is stale or missing",
        predicate=_pred,
    )


def rule_model_drift(rule_id: str = "model.drift", *, threshold: float = 0.2) -> Rule:
    def _pred(_: Mapping[str, object], health: HealthReport) -> Alert | None:
        for result in health.results:
            if result.name == "model_drift" and result.status is HealthStatus.DEGRADED:
                return Alert(
                    rule_id=rule_id,
                    severity=AlertSeverity.WARNING,
                    message=f"model drift exceeded threshold ({threshold}): {result.detail}",
                    context={"detail": result.detail, "threshold": threshold},
                )
        return None

    return Rule(
        rule_id=rule_id,
        severity=AlertSeverity.WARNING,
        description="Model drift above threshold",
        predicate=_pred,
    )


__all__ = [
    "Alert",
    "AlertEngine",
    "AlertSeverity",
    "Rule",
    "rule_broker_disconnected",
    "rule_data_stale",
    "rule_model_drift",
]
