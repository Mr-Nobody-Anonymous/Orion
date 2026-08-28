"""Tests for the generated-code sandbox."""

from __future__ import annotations

import pytest

from orion.coding.sandbox_v2 import PolicyViolation, SandboxPolicy, run_isolated


# ----- Policy audit ----------------------------------------------------

def test_policy_accepts_clean_source() -> None:
    pol = SandboxPolicy()
    assert pol.check_source("x = 1 + 2\n") == []


def test_policy_rejects_os_import() -> None:
    pol = SandboxPolicy()
    violations = pol.check_source("import os\nos.system('echo hi')\n")
    assert any(v.startswith("import_not_allowed") for v in violations)


def test_policy_rejects_subprocess() -> None:
    pol = SandboxPolicy()
    violations = pol.check_source("from subprocess import run\n")
    assert any(v.startswith("import_not_allowed") for v in violations)


def test_policy_rejects_forbidden_eval() -> None:
    pol = SandboxPolicy()
    violations = pol.check_source("eval('1+1')\n")
    assert any(v.startswith("forbidden_pattern") for v in violations)


def test_policy_rejects_forbidden_exec() -> None:
    pol = SandboxPolicy()
    violations = pol.check_source("exec('print(1)')\n")
    assert any(v.startswith("forbidden_pattern") for v in violations)


def test_policy_rejects_open_call() -> None:
    pol = SandboxPolicy()
    violations = pol.check_source("open('/etc/passwd', 'r')\n")
    assert any(v.startswith("forbidden_pattern") for v in violations)


# ----- Runner -----------------------------------------------------------

def test_runner_executes_clean_source() -> None:
    pol = SandboxPolicy(timeout_seconds=5)
    result = run_isolated("x = 2 + 2", policy=pol)
    assert result.ok is True
    assert result.timed_out is False


def test_runner_captures_stdout() -> None:
    pol = SandboxPolicy(timeout_seconds=5)
    result = run_isolated("print('hello sandbox')", policy=pol, entry_expression="None")
    assert result.ok is True
    assert "hello sandbox" in result.stdout


def test_runner_blocks_policy_violation() -> None:
    pol = SandboxPolicy(timeout_seconds=5)
    with pytest.raises(PolicyViolation):
        run_isolated("import os", policy=pol)


def test_runner_captures_errors() -> None:
    pol = SandboxPolicy(timeout_seconds=5)
    result = run_isolated("1/0", policy=pol)
    assert result.ok is False
    assert "ZeroDivisionError" in (result.error or "")


def test_runner_enforces_timeout() -> None:
    pol = SandboxPolicy(timeout_seconds=1)
    result = run_isolated("while True: pass", policy=pol)
    assert result.timed_out is True
    assert result.ok is False
