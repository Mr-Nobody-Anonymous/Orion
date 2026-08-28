#!/usr/bin/env python
"""Run every ORION quality gate and report.

Gates
-----

1. Architecture validation (``config/architecture.yaml`` matches
   ``src/orion/``).
2. Plane separation (no Intelligence->Control or Control->Intelligence
   imports, except the documented executive brain bridge).
3. Full pytest suite.

Each gate runs in order. A failure in one stops the rest. The
intention is to give a single command that an operator (or CI) can
run before merging a change.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def header(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


def run_script(name: str) -> tuple[int, float]:
    """Run a python script as a subprocess; return (exit_code, duration)."""
    start = time.monotonic()
    result = subprocess.run(
        [PYTHON, str(ROOT / "tools" / name)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    duration = time.monotonic() - start
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode != 0:
        print(result.stderr, end="" if result.stderr else "")
    return result.returncode, duration


def run_pytest() -> tuple[int, float]:
    start = time.monotonic()
    result = subprocess.run(
        [PYTHON, "-m", "pytest", "tests", "-q", "--tb=line", "--no-header"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    duration = time.monotonic() - start
    # Only print the last few lines (summary) so the output stays compact.
    lines = result.stdout.splitlines()
    summary = lines[-6:] if len(lines) > 6 else lines
    print("\n".join(summary))
    if result.returncode != 0:
        # On failure, show the first failure context.
        for line in lines[-30:]:
            if "FAILED" in line or "==" in line or "PASSED" in line:
                print(line)
    return result.returncode, duration


def main() -> int:
    gates: list[tuple[str, tuple[int, float]]] = []
    print(f"Running ORION quality gates from {ROOT}")
    print(f"Python: {PYTHON}")

    header("Gate 1/3  Architecture validation (config/architecture.yaml)")
    rc, dur = run_script("validate_architecture.py")
    print(f"[{dur:5.1f}s]  exit={rc}")
    gates.append(("architecture-validation", (rc, dur)))
    if rc != 0:
        return 1

    header("Gate 2/3  Plane separation (Intelligence / Truth / Control)")
    rc, dur = run_script("enforce_planes.py")
    print(f"[{dur:5.1f}s]  exit={rc}")
    gates.append(("plane-separation", (rc, dur)))
    if rc != 0:
        return 1

    header("Gate 3/3  Full pytest suite")
    rc, dur = run_pytest()
    print(f"[{dur:5.1f}s]  exit={rc}")
    gates.append(("pytest", (rc, dur)))
    if rc != 0:
        return 1

    header("Summary")
    for name, (rc, dur) in gates:
        status = "PASS" if rc == 0 else "FAIL"
        print(f"  {name:30s}  {status}  ({dur:5.1f}s)")
    print()
    print("All ORION quality gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
