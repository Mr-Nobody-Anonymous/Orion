"""Integration health diagnostic monitor and pinger."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..capabilities.base import ProviderHealth, ProviderHealthStatus


@dataclass(frozen=True, slots=True)
class IntegrationDiagnostic:
    """Detailed diagnostic report for an external repository integration."""

    name: str
    category: str
    integration_mode: str
    status: str
    is_available: bool
    is_simulated: bool
    latency_ms: float
    dependencies: tuple[str, ...]
    missing_dependencies: tuple[str, ...]
    last_error: str | None = None
    tested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IntegrationHealthMonitor:
    """Collects and audits health across all external adapters."""

    def __init__(self) -> None:
        self._diagnostics: dict[str, IntegrationDiagnostic] = {}

    def record_diagnostic(self, diag: IntegrationDiagnostic) -> None:
        self._diagnostics[diag.name] = diag

    def get_diagnostic(self, name: str) -> IntegrationDiagnostic | None:
        return self._diagnostics.get(name)

    def summary(self) -> dict[str, Any]:
        total = len(self._diagnostics)
        available = sum(1 for d in self._diagnostics.values() if d.is_available)
        simulated = sum(1 for d in self._diagnostics.values() if d.is_simulated)
        return {
            "total_integrations": total,
            "available": available,
            "simulated": simulated,
            "offline": total - available - simulated,
            "diagnostics": [d.as_dict() for d in sorted(self._diagnostics.values(), key=lambda x: x.name)],
        }
