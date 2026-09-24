"""Failure classification for sandboxed code execution.

Level 1 self-correction starts here: parse a traceback, identify the failure
mode, and propose a concrete correction hypothesis. ORION does not silently
retry; every diagnosis is recorded with the attempt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class FailureMode(str, Enum):
    SYNTAX = "syntax"
    IMPORT_MISSING = "import_missing"
    IMPORT_FORBIDDEN = "import_forbidden"
    NAME_ERROR = "name_error"
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    ZERO_DIVISION = "zero_division"
    INDEX_ERROR = "index_error"
    KEY_ERROR = "key_error"
    TIMEOUT = "timeout"
    MEMORY = "memory"
    ASSERTION = "assertion"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"


_TIMEOUT_PATTERNS = ("timeout", "timed out")

_CORRECTIONS: Mapping[FailureMode, str] = {
    FailureMode.SYNTAX: "Regenerate source fixing the reported syntax error before any further attempt.",
    FailureMode.IMPORT_MISSING: "Remove or replace the unavailable import with an allowlisted stdlib/orion module.",
    FailureMode.IMPORT_FORBIDDEN: "The import is outside the sandbox allowlist; rewrite using math/statistics/decimal only.",
    FailureMode.NAME_ERROR: "Define or correctly spell the missing name; check variable scope and typos.",
    FailureMode.TYPE_ERROR: "Align operand types (float vs Decimal vs str) and argument counts.",
    FailureMode.VALUE_ERROR: "Validate inputs before use: positivity, length, and range preconditions.",
    FailureMode.ZERO_DIVISION: "Guard denominators against zero before dividing.",
    FailureMode.INDEX_ERROR: "Check series length before indexing; clamp or reject short inputs.",
    FailureMode.KEY_ERROR: "Use .get with a default or verify the key exists in the mapping.",
    FailureMode.TIMEOUT: "Reduce computational complexity or add an early termination guard.",
    FailureMode.MEMORY: "Reduce data size or switch to a streaming/chunked formulation.",
    FailureMode.ASSERTION: "The candidate's own test failed; the strategy logic, not the harness, is wrong.",
    FailureMode.PROTOCOL: "The child produced no protocol output; likely a hard crash or stdout abuse.",
    FailureMode.UNKNOWN: "Insufficient information; rerun with the error captured verbatim.",
}


def diagnose(*, error: str | None = None, timed_out: bool = False,
             no_protocol_output: bool = False) -> FailureDiagnosis:
    """Classify a sandbox failure from its traceback or flags."""
    if timed_out:
        return FailureDiagnosis(FailureMode.TIMEOUT, "TimeoutExpired", "execution exceeded the sandbox timeout", None,
                                _CORRECTIONS[FailureMode.TIMEOUT])
    if no_protocol_output:
        return FailureDiagnosis(FailureMode.PROTOCOL, "ProtocolError", "sandbox produced no JSON protocol line", None,
                                _CORRECTIONS[FailureMode.PROTOCOL])
    if not error or not error.strip():
        return FailureDiagnosis(FailureMode.UNKNOWN, "Unknown", "no error information", None,
                                _CORRECTIONS[FailureMode.UNKNOWN])
    lowered = error.lower()
    exception_type, message, line_hint = _parse_traceback(error)
    if "syntaxerror" in lowered:
        mode = FailureMode.SYNTAX
    elif "modulenotfounderror" in lowered or "importerror" in lowered:
        mode = FailureMode.IMPORT_FORBIDDEN if _looks_forbidden(error) else FailureMode.IMPORT_MISSING
    elif "nameerror" in lowered:
        mode = FailureMode.NAME_ERROR
    elif "zerodivisionerror" in lowered:
        mode = FailureMode.ZERO_DIVISION
    elif "indexerror" in lowered:
        mode = FailureMode.INDEX_ERROR
    elif "keyerror" in lowered:
        mode = FailureMode.KEY_ERROR
    elif "typeerror" in lowered:
        mode = FailureMode.TYPE_ERROR
    elif "valueerror" in lowered:
        mode = FailureMode.VALUE_ERROR
    elif "memoryerror" in lowered:
        mode = FailureMode.MEMORY
    elif "assertionerror" in lowered:
        mode = FailureMode.ASSERTION
    elif any(pattern in lowered for pattern in _TIMEOUT_PATTERNS):
        mode = FailureMode.TIMEOUT
    else:
        mode = FailureMode.UNKNOWN
    return FailureDiagnosis(mode, exception_type, message, line_hint, _CORRECTIONS[mode])


@dataclass(frozen=True, slots=True)
class FailureDiagnosis:
    mode: FailureMode
    exception_type: str
    message: str
    line_hint: int | None
    correction_hypothesis: str

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "mode": self.mode.value,
            "exception_type": self.exception_type,
            "message": self.message,
            "line_hint": self.line_hint,
            "correction_hypothesis": self.correction_hypothesis,
        }


def _looks_forbidden(error: str) -> bool:
    blocked = ("subprocess", "socket", "ctypes", "urllib", "requests", "httpx")
    return any(name in error.lower() for name in blocked)


def _parse_traceback(error: str) -> tuple[str, str, int | None]:
    lines: Sequence[str] = error.strip().splitlines()
    exception_type = "Unknown"
    message = lines[-1] if lines else ""
    line_hint: int | None = None
    match = re.search(r'File "<string>", line (\d+)', error)
    if match:
        line_hint = int(match.group(1))
    if lines:
        last = lines[-1].strip()
        if ": " in last:
            candidate_type = last.split(": ", 1)[0].split(".")[-1]
            if candidate_type.endswith("Error") or candidate_type.endswith("Exception"):
                exception_type = candidate_type
                message = last.split(": ", 1)[1]
    return exception_type, message, line_hint


class SelfDebugger:
    """Records diagnosis history so repeated identical failures are visible."""

    def __init__(self, *, max_history: int = 100) -> None:
        if max_history < 1:
            raise ValueError("max_history must be at least one")
        self.max_history = max_history
        self._history: list[FailureDiagnosis] = []

    def record(self, diagnosis: FailureDiagnosis) -> FailureDiagnosis:
        self._history.append(diagnosis)
        if len(self._history) > self.max_history:
            self._history.pop(0)
        return diagnosis

    def failure_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._history:
            counts[item.mode.value] = counts.get(item.mode.value, 0) + 1
        return counts

    def most_common_failure(self) -> FailureMode | None:
        if not self._history:
            return None
        counts = self.failure_counts()
        top = max(counts.items(), key=lambda kv: kv[1])
        return FailureMode(top[0])

    def history(self) -> tuple[FailureDiagnosis, ...]:
        return tuple(self._history)

