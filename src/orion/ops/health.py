"""Health checks.

A :class:`HealthCheck` is a callable that returns a
:class:`HealthStatus` and an optional detail string.  The check is
*intentionally* allowed to raise; the registry converts the
exception into a ``CRITICAL`` status with the message attached.

The :class:`HealthReport` aggregates checks by name and exposes the
worst status; ``run_all`` is the only API the rest of ORION should
use.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable, Mapping


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _STATUS_RANK[self]


_STATUS_RANK: dict[HealthStatus, int] = {
    HealthStatus.OK: 0,
    HealthStatus.DEGRADED: 1,
    HealthStatus.CRITICAL: 2,
}


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """A single named health check."""

    name: str
    fn: Callable[[], "HealthCheckResult"]
    description: str = ""


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    name: str
    status: HealthStatus
    detail: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True, slots=True)
class HealthReport:
    """The aggregated result of running a set of :class:`HealthCheck`s."""

    results: tuple[HealthCheckResult, ...]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def status(self) -> HealthStatus:
        if not self.results:
            return HealthStatus.OK
        return max((r.status for r in self.results), key=lambda s: s.rank)

    def failing(self) -> tuple[HealthCheckResult, ...]:
        return tuple(r for r in self.results if r.status is not HealthStatus.OK)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "checks": {
                r.name: {
                    "status": r.status.value,
                    "detail": r.detail,
                    "checked_at": r.checked_at,
                }
                for r in self.results
            },
        }


class HealthRegistry:
    """A small registry of :class:`HealthCheck`s with a :meth:`run_all` runner."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}
        self._lock = threading.RLock()

    def register(self, check: HealthCheck) -> None:
        with self._lock:
            if check.name in self._checks:
                raise ValueError(f"health check {check.name!r} already registered")
            self._checks[check.name] = check

    def unregister(self, name: str) -> None:
        with self._lock:
            self._checks.pop(name, None)

    def checks(self) -> tuple[HealthCheck, ...]:
        with self._lock:
            return tuple(self._checks.values())

    def run_all(self) -> HealthReport:
        results: list[HealthCheckResult] = []
        for check in self.checks():
            try:
                result = check.fn()
            except Exception as exc:  # noqa: BLE001 — health checks may raise
                result = HealthCheckResult(
                    name=check.name,
                    status=HealthStatus.CRITICAL,
                    detail=f"check raised: {exc!r}",
                )
            if result.name != check.name:
                raise ValueError(
                    f"check {check.name!r} returned result with name {result.name!r}"
                )
            results.append(result)
        return HealthReport(results=tuple(results))


# ---- standard health checks --------------------------------------------


def data_freshness_check(
    last_quote_at: datetime | None,
    *,
    max_age_seconds: float = 300.0,
) -> HealthCheckResult:
    """Check that the most recent market quote is not too old.

    Returns CRITICAL when no quote has ever been recorded, DEGRADED
    when the quote is older than ``max_age_seconds``, OK otherwise.
    """
    if last_quote_at is None:
        return HealthCheckResult(
            name="data_freshness",
            status=HealthStatus.CRITICAL,
            detail="no quotes recorded",
        )
    age = (datetime.now(timezone.utc) - last_quote_at).total_seconds()
    if age > max_age_seconds:
        return HealthCheckResult(
            name="data_freshness",
            status=HealthStatus.DEGRADED,
            detail=f"last quote {age:.1f}s old (>{max_age_seconds}s)",
        )
    return HealthCheckResult(
        name="data_freshness",
        status=HealthStatus.OK,
        detail=f"last quote {age:.1f}s old",
    )


def drift_check(psi: float | None, *, threshold: float = 0.2) -> HealthCheckResult:
    """Population-stability-index check: PSI > ``threshold`` is DEGRADED."""
    if psi is None:
        return HealthCheckResult(
            name="model_drift",
            status=HealthStatus.OK,
            detail="no drift score recorded",
        )
    if psi > threshold:
        return HealthCheckResult(
            name="model_drift",
            status=HealthStatus.DEGRADED,
            detail=f"psi={psi:.3f} > {threshold}",
        )
    return HealthCheckResult(
        name="model_drift",
        status=HealthStatus.OK,
        detail=f"psi={psi:.3f}",
    )


def broker_connectivity_check(connected: bool, *, detail: str = "") -> HealthCheckResult:
    status = HealthStatus.OK if connected else HealthStatus.CRITICAL
    return HealthCheckResult(
        name="broker_connectivity",
        status=status,
        detail=detail or ("connected" if connected else "disconnected"),
    )


__all__ = [
    "HealthCheck",
    "HealthCheckResult",
    "HealthRegistry",
    "HealthReport",
    "HealthStatus",
    "broker_connectivity_check",
    "data_freshness_check",
    "drift_check",
]
