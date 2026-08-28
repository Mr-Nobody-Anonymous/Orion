"""Sandbox protocol: the child-interpreter program and result dataclass.

The runner and the legacy ``orion.coding.sandbox`` module both depend on
these definitions.  They live in :mod:`orion.coding.sandbox_v2.protocol`
so the v2 package is fully self-contained and can be promoted to
canonical without touching other subsystems.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass


def _indent(source: str) -> str:
    return "\n".join(("    " + line) if line.strip() else line for line in source.splitlines())


def build_sandbox_program(source: str, entry_expression: str | None = None) -> str:
    """Compose the child-interpreter program for a candidate source.

    The runner executes the candidate verbatim, captures stdout, optionally
    evaluates ``entry_expression`` afterwards, and always emits one JSON line.
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


__all__ = ["SandboxResult", "build_sandbox_program"]
