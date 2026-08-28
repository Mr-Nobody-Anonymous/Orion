"""Process-isolated code execution sandbox.

Generated candidate code NEVER runs in the ORION process. It runs in a fresh,
isolated interpreter (`python -I`) communicating over a strict JSON protocol,
with a hard wall-clock timeout. Any failure is captured and classified by
`debugging.py` — never surfaced as a crash of the platform.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass


def _indent(source: str) -> str:
    return "\n".join("    " + line if line.strip() else line for line in source.splitlines())


def build_sandbox_program(source: str, entry_expression: str | None = None) -> str:
    """Compose the child-interpreter program for a candidate source.

    The runner executes the candidate verbatim, captures stdout, optionally
    evaluates `entry_expression` afterwards, and always emits one JSON line.
    """
    capture_value = ""
    if entry_expression is not None:
        capture_value = (
            f"    _payload['value'] = json.dumps(eval({entry_expression!r}), default=str)\n"
        )
    return (
        "import json, sys, io, traceback\n"
        "_buf = io.StringIO()\n"
        "_real_stdout = sys.stdout\n"
        "sys.stdout = _buf\n"
        "_payload = {'status': 'ok', 'value': None, 'error': None, 'stdout': ''}\n"
        "try:\n"
        f"{_indent(source)}\n"
        f"{capture_value}"
        "except BaseException:\n"
        "    _payload['status'] = 'error'\n"
        "    _payload['error'] = traceback.format_exc()\n"
        "finally:\n"
        "    sys.stdout = _real_stdout\n"
        "    _payload['stdout'] = _buf.getvalue()\n"
        "    print(json.dumps(_payload))\n"
    )


@dataclass(frozen=True, slots=True)
class SandboxResult:
    ok: bool
    value: str | None
    stdout: str
    error: str | None
    timed_out: bool
    duration_seconds: float


class CodeSandbox:
    """Runs candidate source in an isolated interpreter with a hard timeout."""

    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 120:
            raise ValueError("timeout_seconds must be within (0, 120]")
        self.timeout_seconds = timeout_seconds

    def execute(self, source: str, *, entry_expression: str | None = None) -> SandboxResult:
        program = build_sandbox_program(source, entry_expression)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-c", program],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(False, None, "", None, True, self.timeout_seconds)
        duration = time.monotonic() - started
        return self._parse(completed.stdout, completed.stderr, duration=duration)

    @staticmethod
    def _parse(stdout: str, stderr: str, *, duration: float) -> SandboxResult:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and "status" in payload:
                    return SandboxResult(
                        payload.get("status") == "ok",
                        payload.get("value"),
                        str(payload.get("stdout", "")),
                        payload.get("error"),
                        False,
                        duration,
                    )
        return SandboxResult(False, None, stdout, stderr or "sandbox produced no protocol output", False, duration)
