"""Subprocess-based sandbox runner.

The runner:

  1. Audits the source against :class:`SandboxPolicy` *before* spawning
     a subprocess.
  2. Spawns a fresh ``python -I`` interpreter in a per-run tempdir.
  3. Enforces a wall-clock timeout.
  4. Captures stdout/stderr with a hard size cap.
  5. Returns a structured :class:`SandboxResult` for downstream auditing.

The runner is intentionally stdlib-only.  Production deployments that
need a stronger boundary (CPU-seconds, memory caps, no network) should
replace the subprocess spawn with a container runtime; the
:class:`SandboxPolicy` layer remains the same.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .policy import SandboxPolicy
from .protocol import SandboxResult, build_sandbox_program


def _new_temp_workdir() -> Path:
    td = Path(tempfile.mkdtemp(prefix="orion-sandbox-"))
    return td


@dataclass(frozen=True, slots=True)
class PolicyViolation(Exception):
    violations: tuple[str, ...]

    def __str__(self) -> str:
        return f"SandboxPolicy violations: {list(self.violations)}"


def run_isolated(
    source: str,
    *,
    policy: SandboxPolicy | None = None,
    entry_expression: str | None = None,
) -> SandboxResult:
    """Run ``source`` under ``policy`` in an isolated interpreter."""
    pol = policy or SandboxPolicy()
    violations = pol.check_source(source)
    if violations:
        raise PolicyViolation(tuple(violations))

    program = build_sandbox_program(source, entry_expression)
    workdir = Path(pol.working_directory) if pol.working_directory else _new_temp_workdir()
    workdir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    if not pol.allow_network:
        # Conservative: drop common network env hints.  The Python interpreter
        # will still happily make socket calls unless we also firewall them
        # at the OS level; this is a soft signal only.
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", program],
            capture_output=True,
            text=True,
            timeout=pol.timeout_seconds,
            check=False,
            cwd=str(workdir),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(False, None, "", None, True, pol.timeout_seconds)
    duration = time.monotonic() - started
    return _parse(completed.stdout, completed.stderr, duration, pol.max_output_bytes)


def _parse(
    stdout: str,
    stderr: str,
    duration: float,
    max_output_bytes: int,
) -> SandboxResult:
    if len(stdout) > max_output_bytes:
        stdout = stdout[:max_output_bytes] + "...<truncated>"
    if len(stderr) > max_output_bytes:
        stderr = stderr[:max_output_bytes] + "...<truncated>"
    # The original sandbox protocol emits one JSON line on the last stdout line.
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
