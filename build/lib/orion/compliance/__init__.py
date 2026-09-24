"""ORION compliance and regulatory scaffolding (P2-3 of TODO.md).

This package provides:

- :class:`AuditLog` — an append-only audit log with a retention policy.
- :class:`RoleBasedAccess` — role-based permission checking.
- :class:`RestrictedList` — block trading on listed symbols.
- :class:`BestExecutionReport` — slippage and venue comparison.

All components are deterministic and stdlib-only. They never make a
network call and never block the system; they record what *should*
happen so the operator can verify it after the fact.
"""

from __future__ import annotations

from .audit import AuditLog, AuditRecord
from .permissions import RoleBasedAccess, Permission
from .restricted import RestrictedList
from .best_execution import (
    BestExecutionReport,
    VenueExecution,
    build_best_execution_report,
)

__all__ = [
    "AuditLog",
    "AuditRecord",
    "RoleBasedAccess",
    "Permission",
    "RestrictedList",
    "BestExecutionReport",
    "VenueExecution",
    "build_best_execution_report",
]
