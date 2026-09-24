"""Institutional multi-user, multi-tenant collaboration and access control.

Provides Organization, Team, User, Role, and fine-grained ABAC/RBAC
authorization, workspace sharing, and maker-checker approval workflows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class InstitutionalRole(str, Enum):
    ADMIN = "ADMIN"
    PORTFOLIO_MANAGER = "PORTFOLIO_MANAGER"
    TRADER = "TRADER"
    QUANT_ANALYST = "QUANT_ANALYST"
    RISK_OFFICER = "RISK_OFFICER"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    VIEWER = "VIEWER"


class InstitutionalPermission(str, Enum):
    EXECUTE_ORDER = "EXECUTE_ORDER"
    APPROVE_TRADE = "APPROVE_TRADE"
    VIEW_PORTFOLIO = "VIEW_PORTFOLIO"
    MANAGE_PORTFOLIO = "MANAGE_PORTFOLIO"
    MANAGE_RISK = "MANAGE_RISK"
    PROPOSE_RESEARCH = "PROPOSE_RESEARCH"
    SHARE_WORKSPACE = "SHARE_WORKSPACE"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    MANAGE_ORGANIZATION = "MANAGE_ORGANIZATION"


ROLE_PERMISSIONS: dict[InstitutionalRole, frozenset[InstitutionalPermission]] = {
    InstitutionalRole.ADMIN: frozenset(InstitutionalPermission),
    InstitutionalRole.PORTFOLIO_MANAGER: frozenset({
        InstitutionalPermission.VIEW_PORTFOLIO,
        InstitutionalPermission.MANAGE_PORTFOLIO,
        InstitutionalPermission.APPROVE_TRADE,
        InstitutionalPermission.PROPOSE_RESEARCH,
        InstitutionalPermission.SHARE_WORKSPACE,
    }),
    InstitutionalRole.TRADER: frozenset({
        InstitutionalPermission.VIEW_PORTFOLIO,
        InstitutionalPermission.EXECUTE_ORDER,
        InstitutionalPermission.PROPOSE_RESEARCH,
        InstitutionalPermission.SHARE_WORKSPACE,
    }),
    InstitutionalRole.QUANT_ANALYST: frozenset({
        InstitutionalPermission.VIEW_PORTFOLIO,
        InstitutionalPermission.PROPOSE_RESEARCH,
        InstitutionalPermission.SHARE_WORKSPACE,
    }),
    InstitutionalRole.RISK_OFFICER: frozenset({
        InstitutionalPermission.VIEW_PORTFOLIO,
        InstitutionalPermission.MANAGE_RISK,
        InstitutionalPermission.APPROVE_TRADE,
        InstitutionalPermission.VIEW_AUDIT_LOGS,
    }),
    InstitutionalRole.COMPLIANCE_OFFICER: frozenset({
        InstitutionalPermission.VIEW_PORTFOLIO,
        InstitutionalPermission.VIEW_AUDIT_LOGS,
        InstitutionalPermission.APPROVE_TRADE,
    }),
    InstitutionalRole.VIEWER: frozenset({
        InstitutionalPermission.VIEW_PORTFOLIO,
    }),
}


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    username: str
    email: str
    org_id: str
    team_id: str
    role: InstitutionalRole
    max_notional_limit: float = 100_000.0
    allowed_asset_classes: tuple[str, ...] = ("EQUITY", "CRYPTO", "FX", "FIXED_INCOME", "PREDICTION")
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Team:
    team_id: str
    org_id: str
    name: str
    mandate: str
    member_user_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Organization:
    org_id: str
    name: str
    domain: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True, slots=True)
class TradeIdea:
    idea_id: str
    author_id: str
    org_id: str
    symbol: str
    action: str
    notional: float
    thesis: str
    status: str = "PROPOSED"  # PROPOSED, APPROVED, REJECTED, EXECUTED
    approver_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True, slots=True)
class SharedWorkspace:
    workspace_id: str
    owner_id: str
    org_id: str
    name: str
    layout_config: Mapping[str, Any]
    shared_with_teams: tuple[str, ...] = ()
    shared_with_users: tuple[str, ...] = ()


class InstitutionalUserManager:
    """Manages institutional organizations, users, authorization, and dual-custody approval workflows."""

    def __init__(self) -> None:
        self._orgs: dict[str, Organization] = {}
        self._teams: dict[str, Team] = {}
        self._users: dict[str, User] = {}
        self._workspaces: dict[str, SharedWorkspace] = {}
        self._trade_ideas: dict[str, TradeIdea] = {}

    def register_organization(self, name: str, domain: str) -> Organization:
        org_id = f"org_{uuid.uuid4().hex[:8]}"
        org = Organization(org_id=org_id, name=name, domain=domain)
        self._orgs[org_id] = org
        return org

    def create_team(self, org_id: str, name: str, mandate: str) -> Team:
        if org_id not in self._orgs:
            raise KeyError(f"Unknown organization {org_id}")
        team_id = f"team_{uuid.uuid4().hex[:8]}"
        team = Team(team_id=team_id, org_id=org_id, name=name, mandate=mandate)
        self._teams[team_id] = team
        return team

    def create_user(
        self,
        username: str,
        email: str,
        org_id: str,
        team_id: str,
        role: InstitutionalRole,
        max_notional: float = 100_000.0,
        allowed_asset_classes: Sequence[str] = ("EQUITY", "CRYPTO", "FX", "FIXED_INCOME", "PREDICTION"),
    ) -> User:
        if org_id not in self._orgs:
            raise KeyError(f"Unknown organization {org_id}")
        if team_id not in self._teams:
            raise KeyError(f"Unknown team {team_id}")
        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            org_id=org_id,
            team_id=team_id,
            role=role,
            max_notional_limit=max_notional,
            allowed_asset_classes=tuple(allowed_asset_classes),
        )
        self._users[user_id] = user
        # Update team members
        team = self._teams[team_id]
        self._teams[team_id] = Team(
            team_id=team.team_id,
            org_id=team.org_id,
            name=team.name,
            mandate=team.mandate,
            member_user_ids=(*team.member_user_ids, user_id),
        )
        return user

    def authorize(
        self,
        user_id: str,
        permission: InstitutionalPermission,
        asset_class: str | None = None,
        notional: float | None = None,
    ) -> tuple[bool, str]:
        """Perform ABAC validation against user role, permissions, notional and asset class."""
        user = self._users.get(user_id)
        if not user:
            return False, f"User {user_id} not found"
        if not user.is_active:
            return False, f"User {user_id} is inactive"

        perms = ROLE_PERMISSIONS.get(user.role, frozenset())
        if permission not in perms:
            return False, f"Role {user.role.value} lacks permission {permission.value}"

        if asset_class and asset_class not in user.allowed_asset_classes:
            return False, f"Asset class {asset_class} not permitted for user {user.username}"

        if notional is not None and notional > user.max_notional_limit:
            return False, f"Notional ${notional:,.2f} exceeds user limit of ${user.max_notional_limit:,.2f}"

        return True, "Authorized"

    def submit_trade_idea(self, author_id: str, symbol: str, action: str, notional: float, thesis: str) -> TradeIdea:
        user = self._users.get(author_id)
        if not user:
            raise KeyError(f"Author {author_id} not found")
        idea_id = f"idea_{uuid.uuid4().hex[:8]}"
        idea = TradeIdea(
            idea_id=idea_id,
            author_id=author_id,
            org_id=user.org_id,
            symbol=symbol,
            action=action,
            notional=notional,
            thesis=thesis,
            status="PROPOSED",
        )
        self._trade_ideas[idea_id] = idea
        return idea

    def review_trade_idea(self, reviewer_id: str, idea_id: str, approved: bool) -> TradeIdea:
        """Maker-checker rule: author cannot approve their own trade."""
        idea = self._trade_ideas.get(idea_id)
        if not idea:
            raise KeyError(f"Idea {idea_id} not found")
        if idea.author_id == reviewer_id:
            raise ValueError("Maker-checker violation: author cannot review their own trade idea")

        reviewer = self._users.get(reviewer_id)
        if not reviewer:
            raise KeyError(f"Reviewer {reviewer_id} not found")

        perms = ROLE_PERMISSIONS.get(reviewer.role, frozenset())
        if InstitutionalPermission.APPROVE_TRADE not in perms:
            raise PermissionError(f"Reviewer role {reviewer.role.value} lacks APPROVE_TRADE permission")

        new_status = "APPROVED" if approved else "REJECTED"
        updated_idea = TradeIdea(
            idea_id=idea.idea_id,
            author_id=idea.author_id,
            org_id=idea.org_id,
            symbol=idea.symbol,
            action=idea.action,
            notional=idea.notional,
            thesis=idea.thesis,
            status=new_status,
            approver_id=reviewer_id,
            created_at=idea.created_at,
        )
        self._trade_ideas[idea_id] = updated_idea
        return updated_idea

    def share_workspace(
        self,
        owner_id: str,
        name: str,
        layout_config: Mapping[str, Any],
        shared_teams: Sequence[str] = (),
        shared_users: Sequence[str] = (),
    ) -> SharedWorkspace:
        user = self._users.get(owner_id)
        if not user:
            raise KeyError(f"Owner {owner_id} not found")
        ws_id = f"ws_{uuid.uuid4().hex[:8]}"
        ws = SharedWorkspace(
            workspace_id=ws_id,
            owner_id=owner_id,
            org_id=user.org_id,
            name=name,
            layout_config=layout_config,
            shared_with_teams=tuple(shared_teams),
            shared_with_users=tuple(shared_users),
        )
        self._workspaces[ws_id] = ws
        return ws

    def get_accessible_workspaces(self, user_id: str) -> list[SharedWorkspace]:
        user = self._users.get(user_id)
        if not user:
            return []
        results = []
        for ws in self._workspaces.values():
            if ws.org_id != user.org_id:
                continue
            if ws.owner_id == user_id or user_id in ws.shared_with_users or user.team_id in ws.shared_with_teams:
                results.append(ws)
        return results
