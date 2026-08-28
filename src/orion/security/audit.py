"""Tamper-evident append-only audit log.

Each entry is chained to its predecessor via SHA-256, so any retroactive
edit or deletion breaks verification. Audit logs are governance property:
no subsystem, including self-improvement, may truncate or rewrite them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping


GENESIS = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditEntry:
    sequence: int
    action: str
    actor: str
    detail: Mapping[str, Any]
    timestamp: datetime
    previous_hash: str
    entry_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "action": self.action,
            "actor": self.actor,
            "detail": dict(self.detail),
            "timestamp": self.timestamp.isoformat(),
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


def _compute_hash(sequence: int, action: str, actor: str, detail: Mapping[str, Any],
                  timestamp: datetime, previous_hash: str) -> str:
    material = f"{sequence}|{action}|{actor}|{repr(sorted(detail.items()))}|{timestamp.isoformat()}|{previous_hash}"
    return sha256(material.encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only, hash-chained action log."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, action: str, actor: str, **detail: Any) -> AuditEntry:
        if not action.strip():
            raise ValueError("action is required")
        if not actor.strip():
            raise ValueError("actor is required")
        previous_hash = self._entries[-1].entry_hash if self._entries else GENESIS
        timestamp = datetime.now(timezone.utc)
        sequence = len(self._entries)
        entry_hash = _compute_hash(sequence, action, actor, detail, timestamp, previous_hash)
        entry = AuditEntry(sequence, action, actor, dict(detail), timestamp, previous_hash, entry_hash)
        self._entries.append(entry)
        return entry

    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def verify(self) -> tuple[bool, str]:
        """Recompute the full chain; return (ok, first_broken_sequence_or_ok)."""
        previous_hash = GENESIS
        for expected_index, entry in enumerate(self._entries):
            if entry.sequence != expected_index:
                return False, f"sequence break at {entry.sequence}"
            if entry.previous_hash != previous_hash:
                return False, f"chain break at {entry.sequence}"
            recomputed = _compute_hash(entry.sequence, entry.action, entry.actor,
                                       entry.detail, entry.timestamp, entry.previous_hash)
            if recomputed != entry.entry_hash:
                return False, f"hash mismatch at {entry.sequence}"
            previous_hash = entry.entry_hash
        return True, "ok"

    def by_actor(self, actor: str) -> tuple[AuditEntry, ...]:
        return tuple(entry for entry in self._entries if entry.actor == actor)

    def count(self) -> int:
        return len(self._entries)


class ApprovalGate:
    """Explicit human approval for consequential operations.

    Self-improvement MAY propose; only an explicit approval token issued by
    the operator MAY promote, enable live trading, or change risk limits.
    Tokens are single-operation and revocable.
    """

    def __init__(self, audit: AuditLog | None = None) -> None:
        self.audit = audit or AuditLog()
        self._pending: dict[str, str] = {}
        self._approvals: dict[str, str] = {}

    def request(self, operation: str, *, justification: str) -> str:
        if not justification.strip():
            raise ValueError("a justification is required for any approval request")
        token = sha256(f"{operation}|{justification}".encode("utf-8")).hexdigest()[:16]
        self._pending[operation] = token
        self.audit.append("approval_requested", actor="orion", operation=operation, justification=justification)
        return token

    def approve(self, operation: str, token: str, *, approver: str) -> bool:
        """Grant approval only when the token matches the outstanding request."""
        if not approver.strip():
            raise ValueError("approver identity is required")
        expected = self._pending.get(operation)
        if expected is None or not token or token != expected:
            self.audit.append("approval_denied", actor=approver, operation=operation,
                              reason="no matching pending request or bad token")
            return False
        del self._pending[operation]
        self._approvals[operation] = approver
        self.audit.append("approval_granted", actor=approver, operation=operation)
        return True

    def is_approved(self, operation: str) -> bool:
        return operation in self._approvals

    def revoke(self, operation: str, *, revoker: str) -> None:
        self._pending.pop(operation, None)
        if operation in self._approvals:
            del self._approvals[operation]
            self.audit.append("approval_revoked", actor=revoker, operation=operation)


__all__ = [
    "AuditEntry",
    "AuditLog",
    "ApprovalGate",
]
