"""Tests for orion.coding debugging and patching."""

from __future__ import annotations

import pytest

from orion.coding import (
    FailureMode,
    PatchApplier,
    PatchOperation,
    SelfDebugger,
    diagnose,
)


SOURCE = """
def generate_signals(prices, lookback=3):
    if len(prices) <= lookback or any(p <= 0 for p in prices):
        raise ValueError("bad prices")
    return [1 if prices[i] > prices[i - lookback] else 0 for i in range(lookback, len(prices))]
"""


class TestDebugging:
    def test_classifies_zero_division(self) -> None:
        error = 'Traceback (most recent call last):\n  File "<string>", line 2\nZeroDivisionError: division by zero'
        diagnosis = diagnose(error=error)
        assert diagnosis.mode is FailureMode.ZERO_DIVISION
        assert diagnosis.line_hint == 2
        assert "denominator" in diagnosis.correction_hypothesis

    def test_classifies_timeout(self) -> None:
        assert diagnose(timed_out=True).mode is FailureMode.TIMEOUT

    def test_classifies_missing_import(self) -> None:
        error = "ModuleNotFoundError: No module named 'pandas'"
        assert diagnose(error=error).mode is FailureMode.IMPORT_MISSING

    def test_classifies_forbidden_import(self) -> None:
        error = "ModuleNotFoundError: No module named 'socket'"
        assert diagnose(error=error).mode is FailureMode.IMPORT_FORBIDDEN

    def test_classifies_name_error(self) -> None:
        error = 'Traceback:\nNameError: name "priecs" is not defined'
        assert diagnose(error=error).mode is FailureMode.NAME_ERROR

    def test_debugger_history_and_counts(self) -> None:
        debugger = SelfDebugger()
        debugger.record(diagnose(timed_out=True))
        debugger.record(diagnose(timed_out=True))
        debugger.record(diagnose(error="ValueError: bad input"))
        assert debugger.failure_counts()["timeout"] == 2
        assert debugger.most_common_failure() is FailureMode.TIMEOUT
        assert len(debugger.history()) == 3

    def test_empty_error_is_unknown(self) -> None:
        assert diagnose(error="").mode is FailureMode.UNKNOWN

    def test_diagnosis_serializable(self) -> None:
        payload = diagnose(timed_out=True).as_dict()
        assert payload["mode"] == "timeout"


class TestPatching:
    def test_apply_and_revert(self) -> None:
        applier = PatchApplier()
        result = applier.apply("c1", SOURCE, [PatchOperation("lookback=3", "lookback=5")])
        assert result.applied
        assert "lookback=5" in result.patched_source
        assert result.patched_hash != result.previous_hash
        assert applier.revert("c1", result.patched_source) == SOURCE

    def test_missing_anchor_rejected(self) -> None:
        result = PatchApplier().apply("c2", SOURCE, [PatchOperation("NOT PRESENT", "x")])
        assert not result.applied
        assert any("anchor" in issue for issue in result.issues)

    def test_patch_rejected_if_verification_fails(self) -> None:
        result = PatchApplier().apply(
            "c3", SOURCE, [PatchOperation('raise ValueError("bad prices")', "exec('x=1')")]
        )
        assert not result.applied

    def test_noop_patch_rejected(self) -> None:
        with pytest.raises(ValueError):
            PatchApplier().apply("c4", SOURCE, [PatchOperation("same", "same")])

    def test_revert_without_history(self) -> None:
        assert PatchApplier().revert("nothing", "source") is None

    def test_multi_operation_patch(self) -> None:
        applier = PatchApplier()
        result = applier.apply("c5", SOURCE, [
            PatchOperation("lookback=3", "lookback=4"),
            PatchOperation('"bad prices"', '"prices too short"'),
        ])
        assert result.applied
        assert "lookback=4" in result.patched_source
        assert '"prices too short"' in result.patched_source
