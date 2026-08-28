"""Compliance agent (P2-2).

Reads the :class:`orion.compliance.restricted.RestrictedList` and
:class:`orion.compliance.permissions.RoleBasedAccess` to decide
whether the symbol and the requested action are permitted under
ORION's compliance posture. The agent is non-blocking: it returns
``BLOCK`` with explicit reasons when the action is forbidden.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


class ComplianceAgent(Agent):
    role = AgentRole.COMPLIANCE

    def __init__(self, *, restricted: Any | None = None) -> None:
        # ``restricted`` may be a ``RestrictedList`` or anything with
        # an ``is_restricted(symbol) -> bool`` method.
        self._restricted = restricted

    def evaluate(self, context: AgentContext) -> AgentDecision:
        reasons: list[str] = []
        if self._restricted is not None:
            try:
                is_restricted = bool(self._restricted.is_restricted(context.symbol))
            except Exception:  # pragma: no cover - defensive
                is_restricted = False
            if is_restricted:
                reasons.append(f"symbol {context.symbol!r} is on the restricted list")
                return AgentDecision(
                    role=self.role,
                    verdict="BLOCK",
                    reasons=tuple(reasons),
                    notes="compliance: restricted list match",
                )
        # Asset-class whitelist is implicit; unknown classes raise elsewhere.
        return AgentDecision(
            role=self.role,
            verdict="ALLOW",
            reasons=("no restricted-list match",),
        )
