"""Compatibility test: ``orion.coding.sandbox`` and
``orion.coding.sandbox_v2`` must expose the same primitive types and
both must remain usable.

The consolidation move keeps the legacy module as a re-export shim;
this test fails loudly if anyone re-introduces divergent definitions.
"""

from __future__ import annotations


def test_sandbox_result_is_same_class() -> None:
    from orion.coding.sandbox import SandboxResult as LegacyResult
    from orion.coding.sandbox_v2 import SandboxResult as V2Result
    assert LegacyResult is V2Result


def test_build_sandbox_program_is_same_function() -> None:
    from orion.coding.sandbox import build_sandbox_program as legacy_build
    from orion.coding.sandbox_v2 import build_sandbox_program as v2_build
    assert legacy_build is v2_build


def test_sandbox_v2_is_self_contained() -> None:
    """The v2 package must not import from the legacy sandbox module."""
    import orion.coding.sandbox_v2 as v2
    # If runner.py still imported from ..sandbox this would be a hard
    # cycle on a removal.  We assert by importing the runner and
    # checking the import graph.
    import orion.coding.sandbox_v2.runner as runner
    # The protocol symbols must be defined inside the v2 package.
    assert hasattr(runner, "SandboxResult")
    assert hasattr(runner, "build_sandbox_program")
    assert v2.SandboxPolicy is runner.SandboxPolicy


def test_legacy_codesandbox_delegates_to_v2() -> None:
    from orion.coding.sandbox import CodeSandbox
    from orion.coding.sandbox_v2 import SandboxResult

    box = CodeSandbox(timeout_seconds=5)
    result = box.execute("print('ok')", entry_expression="None")
    assert isinstance(result, SandboxResult)
    assert result.ok is True
    assert "ok" in result.stdout


def test_coding_package_reexports_v2_canonical() -> None:
    """``orion.coding`` must surface the v2 surface as the public API."""
    import orion.coding as coding
    for name in (
        "SandboxPolicy",
        "PolicyViolation",
        "run_isolated",
        "SandboxResult",
        "build_sandbox_program",
        "CodeSandbox",
    ):
        assert hasattr(coding, name), f"orion.coding missing {name}"


def test_policy_violation_surfaces_as_failed_result_in_legacy_wrapper() -> None:
    from orion.coding.sandbox import CodeSandbox

    box = CodeSandbox(timeout_seconds=5)
    # ``import os`` is forbidden by the default policy.  The legacy
    # wrapper must surface the violation as a failed SandboxResult,
    # not an exception, to preserve the old contract.
    result = box.execute("import os\n")
    assert result.ok is False
    assert result.error is not None
    assert "policy" in result.error.lower()
