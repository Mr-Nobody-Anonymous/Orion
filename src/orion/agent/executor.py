"""The ORION capability execution protocol.

The 2026-08-28 review said the capability registry is currently
a *catalogue* and the next step is to turn it into a
*callable interface* with a standardized result:

    result = capability.execute(
        input=...,
        context=...,
        constraints=...,
    )

    CapabilityResult
    ├── output
    ├── provenance
    ├── execution_time
    ├── cost
    ├── errors
    ├── artifacts
    ├── confidence
    ├── side_effects
    └── reproducibility metadata

This module provides exactly that. It is a thin wrapper around
the existing :class:`orion.intelligence.capability_registry`
and the actual capability implementations. It does not
implement any capability itself; the registry already lists
what is callable and what is not.

Why this layer
--------------

The agent kernel should not have to know whether a capability
is implemented in this repository, in an upstream
repository, behind an HTTP API, or as a Python function. The
executor abstracts that away. The kernel calls
:meth:`CapabilityExecutor.execute` and gets a
:class:`CapabilityResult` back; what happens underneath is
the executor's concern.

This is also the natural place to enforce:

* **Permission checks.** The executor refuses a call that
  declares a permission the caller does not have.
* **Risk-gate approval.** A ``HIGH``-risk capability call
  requires an explicit risk approval. The executor checks
  this before invoking.
* **Self-model updates.** Every outcome (success or failure)
  is recorded against the calling agent's self-model so the
  agent learns from experience.
"""

from __future__ import annotations

import hashlib
import inspect
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from ..intelligence.capability_registry import (
    CapabilityKind,
    CapabilityQuery,
    CapabilityRegistry,
    Field,
    IntegrationMode,
    Plane,
    RiskLevel,
    Tool,
    default_registry,
)
from .memory import AgentMemory


@dataclass(frozen=True, slots=True)
class CapabilityContext:
    """The execution context for a capability call.

    The agent kernel fills this in. It carries the caller's
    identity, the agent's goal (so a capability can prefer
    "do this safely" over "do this fast" if the goal is
    safety-critical), and any approved permissions the
    caller has been granted.
    """

    caller: str
    goal_id: str
    approved_permissions: frozenset[str] = frozenset()
    risk_approver: str = ""  # non-empty if a high-risk call was approved


@dataclass(frozen=True, slots=True)
class CapabilityConstraints:
    """Constraints the caller places on the execution."""

    timeout_seconds: float = 30.0
    max_cost_units: float = float("inf")  # abstract; depends on the capability
    allow_side_effects: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """The standardised result of a capability call."""

    capability: str
    success: bool
    output: Any = None
    error: str = ""
    execution_time_seconds: float = 0.0
    cost_units: float = 0.0
    artifacts: tuple[str, ...] = ()
    confidence: float = 1.0
    side_effects: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    # Reproducibility: the exact function path, args, and
    # kwargs that produced this result. Re-invoking the
    # capability with the same input should reproduce the
    # output (modulo side effects).
    reproducibility: Mapping[str, Any] = field(default_factory=dict)
    called_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time_seconds": self.execution_time_seconds,
            "cost_units": self.cost_units,
            "artifacts": list(self.artifacts),
            "confidence": self.confidence,
            "side_effects": list(self.side_effects),
            "provenance": dict(self.provenance),
            "reproducibility": dict(self.reproducibility),
            "called_at": self.called_at.isoformat(),
        }


# The signature every capability implementation must satisfy.
CapabilityImpl = Callable[[Mapping[str, Any], CapabilityContext, CapabilityConstraints], Any]


class CapabilityNotFoundError(KeyError):
    """Raised when a capability is not in the registry."""


class PermissionDeniedError(PermissionError):
    """Raised when a caller does not have a required permission."""


class RiskGateError(RuntimeError):
    """Raised when a high-risk capability is invoked without approval."""


class CapabilityExecutor:
    """Routes capability calls to their implementations.

    A :class:`CapabilityExecutor` binds a
    :class:`CapabilityRegistry` (the catalogue) to a set of
    callables (the implementations). It enforces permission
    checks, the risk gate, and self-model updates. It does
    **not** interpret the output; the caller decides what to
    do with the result.
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        memory: AgentMemory | None = None,
        implementations: Mapping[str, CapabilityImpl] | None = None,
    ) -> None:
        self._registry = registry if registry is not None else default_registry()
        self._memory = memory if memory is not None else AgentMemory()
        self._impls: dict[str, CapabilityImpl] = dict(implementations or {})
        # Phase 31G: the immutable invocation log. Every
        # call to ``execute`` appends one record; the
        # caller can read the log with ``records()`` to
        # reconstruct what happened. Capped at 1024
        # records by default to bound memory.
        self._records: list[InvocationRecord] = []
        self._max_records: int = 1024

    def register_implementation(self, capability: str, fn: CapabilityImpl) -> None:
        """Bind an implementation to a registered capability name.

        ``fn`` must be importable. The executor stores the
        function reference, not its source, so the binding
        cannot survive process restart without re-registration.
        """
        if capability not in self._registry:
            raise CapabilityNotFoundError(capability)
        self._impls[capability] = fn

    # ------------------------------------------------------------------ execute

    def execute(
        self,
        capability: str,
        input: Mapping[str, Any],
        context: CapabilityContext,
        constraints: CapabilityConstraints | None = None,
    ) -> CapabilityResult:
        """Execute a capability. Wraps :meth:`execute_with_record`
        and discards the record for backward compatibility.
        """
        result, _record = self.execute_with_record(
            capability, input, context, constraints
        )
        return result

    def execute_with_record(
        self,
        capability: str,
        input: Mapping[str, Any],
        context: CapabilityContext,
        constraints: CapabilityConstraints | None = None,
    ) -> tuple[CapabilityResult, InvocationRecord]:
        """Execute a capability and return the (result, record)
        pair. The record is appended to the executor's
        in-memory log.
        """
        if capability not in self._registry:
            raise CapabilityNotFoundError(capability)
        tool = self._registry.get(capability)
        constraints = constraints or CapabilityConstraints()
        # 1. Permission check
        self._check_permissions(tool, context)
        # 2. Risk gate
        self._check_risk(tool, context)
        # 3. Dispatch and record
        started_at = datetime.now(timezone.utc)
        result = self._dispatch(tool, input, context, constraints)
        inputs_hash = self._hash_mapping({"args": dict(input), "caller": context.caller})
        result_hash = self._hash_mapping({
            "success": result.success,
            "output": result.output,
            "error": result.error,
        })
        record = InvocationRecord(
            invocation_id=str(uuid4()),
            tool=tool.name,
            operation=capability,
            inputs_hash=inputs_hash,
            result_hash=result_hash,
            started_at=started_at,
            duration_seconds=result.execution_time_seconds,
            success=result.success,
            cost_units=result.cost_units,
            risk=tool.risk.value,
            sandbox=tool.integration.value,
            approver=context.risk_approver,
            confidence=result.confidence,
            error=result.error,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]
        return result, record

    @staticmethod
    def _hash_mapping(m: Mapping[str, Any]) -> str:
        """Stable, short hash of a mapping for the invocation
        log. JSON is not used because the values can include
        non-JSON types; we use ``repr`` and SHA-256.
        """
        h = hashlib.sha256()
        for key in sorted(m.keys()):
            h.update(repr(key).encode("utf-8"))
            h.update(b"=")
            h.update(repr(m[key]).encode("utf-8"))
            h.update(b";")
        return h.hexdigest()[:16]

    def records(self) -> tuple[InvocationRecord, ...]:
        """Return the executor's immutable invocation log.

        The log is in append order. The first record is
        the oldest call. The log is bounded by
        ``max_records``; the oldest records are dropped
        first.
        """
        return tuple(self._records)

    def _check_permissions(self, tool: Tool, context: CapabilityContext) -> None:
        for required in tool.permissions:
            if required not in context.approved_permissions:
                raise PermissionDeniedError(
                    f"{tool.name!r} requires permission {required!r} "
                    f"which is not in the caller's approved set"
                )

    def _check_risk(self, tool: Tool, context: CapabilityContext) -> None:
        if tool.risk == RiskLevel.HIGH and not context.risk_approver:
            raise RiskGateError(
                f"{tool.name!r} is HIGH-risk and the caller did not declare "
                f"a non-empty risk_approver; refusing to execute"
            )

    def _dispatch(
        self,
        tool: Tool,
        input: Mapping[str, Any],
        context: CapabilityContext,
        constraints: CapabilityConstraints,
    ) -> CapabilityResult:
        impl = self._impls.get(tool.name)
        if impl is None:
            # No implementation registered. The capability is
            # advertised (perhaps a reference to an upstream
            # capability) but not actually callable. Record
            # this as a failure in the self-model and return
            # an honest error result.
            err = f"no implementation registered for {tool.name!r}"
            self._memory.record_capability_outcome(tool.name, success=False)
            return CapabilityResult(
                capability=tool.name,
                success=False,
                error=err,
                provenance={"tool_kind": tool.kind.value, "tool_plane": tool.plane.value},
                reproducibility={"input": dict(input), "context_caller": context.caller},
            )

        # Time the call.
        start = time.monotonic()
        confidence = 1.0
        side_effects: list[str] = []
        error = ""
        output: Any = None
        try:
            output = impl(input, context, constraints)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            self._memory.record_capability_outcome(tool.name, success=False)
            return CapabilityResult(
                capability=tool.name,
                success=False,
                error=error,
                execution_time_seconds=time.monotonic() - start,
                provenance={"tool_kind": tool.kind.value, "tool_plane": tool.plane.value},
                reproducibility={"input": dict(input), "context_caller": context.caller,
                                  "traceback": traceback.format_exc()},
            )
        elapsed = time.monotonic() - start
        # Heuristic: if the implementation returned a dict
        # with a "confidence" key, surface it; otherwise
        # default to 1.0.
        if isinstance(output, Mapping) and "confidence" in output:
            try:
                confidence = float(output["confidence"])
            except (TypeError, ValueError):
                confidence = 1.0
        if not constraints.allow_side_effects:
            side_effects.append("side_effects_disallowed_by_caller")
        self._memory.record_capability_outcome(tool.name, success=True)
        return CapabilityResult(
            capability=tool.name,
            success=True,
            output=output,
            execution_time_seconds=elapsed,
            confidence=confidence,
            side_effects=tuple(side_effects),
            provenance={
                "tool_kind": tool.kind.value,
                "tool_plane": tool.plane.value,
                "impl_module": getattr(impl, "__module__", "unknown"),
                "impl_qualname": getattr(impl, "__qualname__", repr(impl)),
            },
            reproducibility={
                "input": dict(input),
                "context_caller": context.caller,
                "context_goal_id": context.goal_id,
            },
        )

    # ------------------------------------------------------------------ introspection

    def list_capabilities(self) -> tuple[Tool, ...]:
        """Return every registered tool, sorted by name."""
        return self._registry.tools()

    def has_implementation(self, capability: str) -> bool:
        return capability in self._impls

    def registry(self) -> CapabilityRegistry:
        return self._registry

    def memory(self) -> AgentMemory:
        return self._memory


# --------------------------------------------------------------------------- Phase 31G
# CapabilitySelector + InvocationRecord. These are the
# runtime pieces the 2026-08-28 review (point 3) said are
# "probably the single most important implementation after
# the registry." The selector chooses a registered tool by
# kind / risk / permission; the executor records every
# invocation as an immutable record for the audit log.


@dataclass(frozen=True, slots=True)
class InvocationRecord:
    """An immutable record of one capability call.

    The 2026-08-28 review's point 3: "every invocation
    should generate an immutable record" with at least
    the tool, operation, input/output hashes, started_at,
    duration, and success flag. The executor builds one
    per call and appends it to an in-memory list; the
    list is the kernel's truthful "what did I do?" log.
    """

    invocation_id: str
    tool: str
    operation: str
    inputs_hash: str
    result_hash: str
    started_at: datetime
    duration_seconds: float
    success: bool
    cost_units: float = 0.0
    risk: str = ""
    sandbox: str = ""
    approver: str = ""
    confidence: float = 1.0
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "tool": self.tool,
            "operation": self.operation,
            "inputs_hash": self.inputs_hash,
            "result_hash": self.result_hash,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "cost_units": self.cost_units,
            "risk": self.risk,
            "sandbox": self.sandbox,
            "approver": self.approver,
            "confidence": self.confidence,
            "error": self.error,
        }


class CapabilitySelector:
    """Picks a registered :class:`Tool` for a given task.

    The 2026-08-28 review's point 1: between the
    :class:`CapabilityRegistry` (catalogue) and the
    executor (dispatcher) there should be a *selector*
    that chooses the right tool by kind, risk,
    required permission, etc. The selector is the
    kernel's "which tool is best for this?" primitive.

    The selector does not call the tool — that is the
    executor's job. The selector only picks a candidate
    (or a ranked list of candidates) and surfaces the
    reasons for the ranking. The policy decides.

    The ranking is deterministic and the reasons are
    recorded in the returned :class:`Selection` so the
    audit log can show *why* a tool was chosen.
    """

    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self._registry = registry if registry is not None else default_registry()

    def select(
        self,
        *,
        kind: CapabilityKind | None = None,
        plane: Plane | None = None,
        max_risk: RiskLevel | None = None,
        required_permission: str | None = None,
        name_substring: str | None = None,
    ) -> tuple[Tool, ...]:
        """Return every tool matching the query, in deterministic
        order (alphabetical by name).

        The query is the union of the optional filters. A
        ``None`` filter is a wildcard.
        """
        from ..intelligence.capability_registry import CapabilityQuery
        kinds = (kind,) if kind is not None else ()
        planes = (plane,) if plane is not None else ()
        query = CapabilityQuery(
            kinds=kinds,
            planes=planes,
            max_risk=max_risk,
            name_contains=name_substring or "",
            has_permission=required_permission or "",
        )
        return self._registry.search(query)

    def select_one(
        self,
        *,
        kind: CapabilityKind | None = None,
        plane: Plane | None = None,
        max_risk: RiskLevel | None = None,
        required_permission: str | None = None,
        name_substring: str | None = None,
    ) -> Tool | None:
        """Return the highest-priority tool matching the query,
        or ``None`` if there is no match.

        The current "priority" is alphabetical; the
        :class:`CapabilitySelector` does not invent a
        ranking function. A future session can add
        self-model-aware ranking (review point 13:
        "capability learning") without changing the
        selector's contract.
        """
        matches = self.select(
            kind=kind,
            plane=plane,
            max_risk=max_risk,
            required_permission=required_permission,
            name_substring=name_substring,
        )
        if not matches:
            return None
        return matches[0]
