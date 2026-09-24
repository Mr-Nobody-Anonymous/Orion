"""Role-based access control (P2-3)."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Mapping


class Permission(str, Enum):
    READ_MARKET_DATA = "read_market_data"
    READ_RESEARCH = "read_research"
    PROPOSE_STRATEGY = "propose_strategy"
    APPROVE_PROMOTION = "approve_promotion"
    MODIFY_RISK_LIMITS = "modify_risk_limits"
    EXECUTE_TRADE = "execute_trade"
    REVIEW_AUDIT = "review_audit"
    ADMIN = "admin"


_DEFAULT_ROLES: dict[str, frozenset[Permission]] = {
    "researcher": frozenset({Permission.READ_MARKET_DATA, Permission.READ_RESEARCH}),
    "trader": frozenset(
        {
            Permission.READ_MARKET_DATA,
            Permission.READ_RESEARCH,
            Permission.EXECUTE_TRADE,
        }
    ),
    "risk": frozenset(
        {
            Permission.READ_MARKET_DATA,
            Permission.READ_RESEARCH,
            Permission.MODIFY_RISK_LIMITS,
            Permission.REVIEW_AUDIT,
        }
    ),
    "compliance": frozenset(
        {
            Permission.READ_MARKET_DATA,
            Permission.REVIEW_AUDIT,
        }
    ),
    "admin": frozenset(Permission),
}


class RoleBasedAccess:
    """Lightweight RBAC backed by a dict of role → permissions."""

    def __init__(self, roles: Mapping[str, Iterable[Permission]] | None = None) -> None:
        merged: dict[str, frozenset[Permission]] = {}
        for role, perms in _DEFAULT_ROLES.items():
            merged[role] = frozenset(perms)
        if roles:
            for role, perms in roles.items():
                merged[role] = frozenset(perms)
        self._roles = merged

    def grant(self, role: str, permission: Permission) -> None:
        self._roles[role] = self._roles.get(role, frozenset()) | {permission}

    def revoke(self, role: str, permission: Permission) -> None:
        self._roles[role] = self._roles.get(role, frozenset()) - {permission}

    def roles(self) -> tuple[str, ...]:
        return tuple(self._roles)

    def permissions_for(self, role: str) -> frozenset[Permission]:
        return self._roles.get(role, frozenset())

    def has_permission(self, role: str, permission: Permission) -> bool:
        return permission in self.permissions_for(role)
