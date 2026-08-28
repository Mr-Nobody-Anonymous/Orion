"""Candidate patching with mandatory before/after verification.

A patch is applied to TEXT, verified statically, and sandbox-tested. The
original is retained for one-command revert. Patches never touch the ORION
package tree; they operate on candidate artifacts supplied by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Sequence

from .verification import verify_candidate_source


@dataclass(frozen=True, slots=True)
class PatchOperation:
    old: str
    new: str


@dataclass(frozen=True, slots=True)
class PatchResult:
    applied: bool
    patched_source: str
    previous_hash: str
    patched_hash: str
    issues: tuple[str, ...]


def _hash(source: str) -> str:
    return sha256(source.encode("utf-8")).hexdigest()


class PatchApplier:
    """Apply, verify, and revert text patches on candidate sources."""

    def __init__(self) -> None:
        self._undo_stack: dict[str, list[str]] = {}

    def apply(self, candidate_id: str, source: str, operations: Sequence[PatchOperation]) -> PatchResult:
        if not operations:
            raise ValueError("at least one patch operation is required")
        patched = source
        applied_count = 0
        for operation in operations:
            if operation.old == operation.new:
                raise ValueError("patch operation replaces text with itself")
            if operation.old not in patched:
                return PatchResult(False, source, _hash(source), _hash(source),
                                   (f"anchor text not found: {operation.old[:60]!r}",))
            patched = patched.replace(operation.old, operation.new, 1)
            applied_count += 1
        if applied_count != len(operations):
            return PatchResult(False, source, _hash(source), _hash(source), ("not all operations applied",))
        verification = verify_candidate_source(patched)
        if not verification.accepted:
            return PatchResult(False, source, _hash(source), _hash(source), verification.issues)
        self._undo_stack.setdefault(candidate_id, []).append(source)
        return PatchResult(True, patched, _hash(source), _hash(patched), ())

    def revert(self, candidate_id: str, current: str) -> str | None:
        """Restore the most recent pre-patch version; None when nothing to undo."""
        history = self._undo_stack.get(candidate_id)
        if not history:
            return None
        previous = history.pop()
        return previous
