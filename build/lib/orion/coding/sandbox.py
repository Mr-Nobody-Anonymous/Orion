"""Back-compatibility shim for the generated-code sandbox.

The canonical implementation now lives in :mod:`orion.coding.sandbox_v2`.
This module re-exports the same names so that legacy call sites
(``from orion.coding.sandbox import CodeSandbox, SandboxResult, ...``)
continue to work unchanged.

New code should import directly from
:mod:`orion.coding.sandbox_v2` (or from :mod:`orion.coding`, which
surfaces the v2 surface as canonical).
"""

from __future__ import annotations

from dataclasses import dataclass

from .sandbox_v2 import (
    SandboxPolicy,
    SandboxResult,
    build_sandbox_program,
    run_isolated,
)
from .sandbox_v2.runner import PolicyViolation


@dataclass(frozen=True, slots=True)
class CodeSandbox:
    """Deprecated thin wrapper around :func:`run_isolated`.

    Retained so that any external code constructing a ``CodeSandbox``
    instance continues to work.  Delegates to the v2 runner with the
    default policy unless one is supplied.

    The constructor preserves the legacy ``(0, 120]`` timeout validation
    so existing callers that pass an out-of-range timeout continue to
    receive ``ValueError``.
    """

    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.timeout_seconds > 120:
            raise ValueError("timeout_seconds must be within (0, 120]")

    def execute(
        self,
        source: str,
        *,
        entry_expression: str | None = None,
    ) -> SandboxResult:
        policy = SandboxPolicy(timeout_seconds=self.timeout_seconds)
        try:
            return run_isolated(
                source,
                policy=policy,
                entry_expression=entry_expression,
            )
        except PolicyViolation:
            # The legacy API surfaced policy violations as a failed
            # result, not an exception.  Preserve that contract.
            return SandboxResult(
                ok=False,
                value=None,
                stdout="",
                error="sandbox policy violation",
                timed_out=False,
                duration_seconds=0.0,
            )


__all__ = [
    "CodeSandbox",
    "PolicyViolation",
    "SandboxPolicy",
    "SandboxResult",
    "build_sandbox_program",
    "run_isolated",
]
