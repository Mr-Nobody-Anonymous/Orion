"""Permissioned tool registry for ORION agents.

Agents never get unrestricted access. Every tool declares the permission it
requires; every agent profile declares the permissions it holds; every
invocation is audited with its outcome. Denials are first-class results, not
exceptions the caller can silently ignore.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Callable, Mapping


class ToolPermission(str, Enum):
    MARKET_DATA = "market_data"
    RESEARCH = "research"
    COMPUTE = "compute"
    MEMORY = "memory"
    CODE_EXECUTION = "code_execution"
    BACKTEST = "backtest"
    SIMULATION = "simulation"
    PRICING = "pricing"
    TRAINING = "training"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    permission: ToolPermission
    handler: Callable[..., Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name is required")


@dataclass(frozen=True, slots=True)
class AgentProfile:
    name: str
    permissions: frozenset[ToolPermission]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("agent name is required")

    def holds(self, permission: ToolPermission) -> bool:
        return permission in self.permissions


@dataclass(frozen=True, slots=True)
class InvocationRecord:
    tool: str
    agent: str
    arguments_hash: str
    allowed: bool
    ok: bool
    duration_seconds: float
    denial_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "agent": self.agent,
            "arguments_hash": self.arguments_hash,
            "allowed": self.allowed,
            "ok": self.ok,
            "duration_seconds": self.duration_seconds,
            "denial_reason": self.denial_reason,
        }


@dataclass(frozen=True, slots=True)
class InvocationResult:
    ok: bool
    value: Any = None
    error: str = ""
    record: InvocationRecord | None = None


class ToolRegistry:
    """Central, audited tool broker."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._audit: list[InvocationRecord] = []

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def spec(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def invoke(self, agent: AgentProfile, tool_name: str, /, **arguments: Any) -> InvocationResult:
        if tool_name not in self._tools:
            record = self._record(tool_name, agent, arguments, allowed=False, ok=False,
                                  duration=0.0, denial_reason="unknown tool")
            return InvocationResult(False, error="unknown tool", record=record)
        spec = self._tools[tool_name]
        if not agent.holds(spec.permission):
            reason = f"agent '{agent.name}' lacks permission '{spec.permission.value}'"
            record = self._record(tool_name, agent, arguments, allowed=False, ok=False,
                                  duration=0.0, denial_reason=reason)
            return InvocationResult(False, error=reason, record=record)
        started = time.monotonic()
        try:
            value = spec.handler(**arguments)
        except Exception as error:  # tool failure is a result, not a crash
            duration = time.monotonic() - started
            record = self._record(tool_name, agent, arguments, allowed=True, ok=False,
                                  duration=duration, denial_reason=f"{type(error).__name__}: {error}")
            return InvocationResult(False, error=f"{type(error).__name__}: {error}", record=record)
        duration = time.monotonic() - started
        record = self._record(tool_name, agent, arguments, allowed=True, ok=True, duration=duration)
        return InvocationResult(True, value=value, record=record)

    def _record(self, tool: str, agent: AgentProfile, arguments: Mapping[str, Any], *, allowed: bool,
                ok: bool, duration: float, denial_reason: str = "") -> InvocationRecord:
        arguments_hash = sha256(repr(sorted(arguments.items())).encode("utf-8")).hexdigest()[:16]
        record = InvocationRecord(tool, agent.name, arguments_hash, allowed, ok, duration, denial_reason)
        self._audit.append(record)
        return record

    def audit_log(self) -> tuple[InvocationRecord, ...]:
        return tuple(self._audit)

    def denials(self) -> tuple[InvocationRecord, ...]:
        return tuple(record for record in self._audit if not record.allowed)
