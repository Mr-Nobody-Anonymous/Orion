"""Tests for orion.coding: analysis, sandbox, generation."""

from __future__ import annotations

import pytest

from orion.coding import (
    CodeSandbox,
    StrategyCodeGenerator,
    analyze_source,
    build_sandbox_program,
)


GOOD_STRATEGY = """
def generate_signals(prices, lookback=3):
    if len(prices) <= lookback or any(p <= 0 for p in prices):
        raise ValueError("bad prices")
    return [1 if prices[i] > prices[i - lookback] else 0 for i in range(lookback, len(prices))]
"""


class TestAnalysis:
    def test_accepts_clean_source(self) -> None:
        result = analyze_source(GOOD_STRATEGY)
        assert result.acceptable
        assert result.function_count == 1

    def test_flags_dangerous_calls(self) -> None:
        result = analyze_source("x = eval('1+1')\n")
        assert not result.acceptable
        assert any("eval" in issue for issue in result.issues)

    def test_flags_disallowed_imports(self) -> None:
        result = analyze_source("import socket\n")
        assert any("socket" in issue for issue in result.issues)

    def test_flags_environment_access(self) -> None:
        result = analyze_source("import os\nx = os.environ['KEY']\n")
        assert any("environ" in issue for issue in result.issues)

    def test_syntax_error_reported(self) -> None:
        result = analyze_source("def broken(:\n")
        assert not result.parses
        assert result.issues


class TestSandbox:
    def test_executes_clean_code(self) -> None:
        result = CodeSandbox(timeout_seconds=30).execute(
            GOOD_STRATEGY,
            entry_expression="len(generate_signals([100.0, 101.0, 102.0, 103.0, 104.0]))",
        )
        assert result.ok, result.error
        assert result.value == "2"

    def test_captures_runtime_error(self) -> None:
        result = CodeSandbox(timeout_seconds=30).execute("x = 1 / 0\n")
        assert not result.ok
        assert result.error and "ZeroDivisionError" in result.error

    def test_timeout_is_reported(self) -> None:
        result = CodeSandbox(timeout_seconds=2).execute("while True:\n    pass\n")
        assert not result.ok
        assert result.timed_out

    def test_stdout_captured(self) -> None:
        result = CodeSandbox(timeout_seconds=30).execute("print('hello from candidate')\n")
        assert result.ok
        assert "hello from candidate" in result.stdout

    def test_timeout_bounds_enforced(self) -> None:
        with pytest.raises(ValueError):
            CodeSandbox(timeout_seconds=0)
        with pytest.raises(ValueError):
            CodeSandbox(timeout_seconds=1000)

    def test_program_includes_source(self) -> None:
        program = build_sandbox_program("x = 1\n")
        assert "x = 1" in program
        assert "json.dumps" in program


class TestGeneration:
    def test_generates_deterministic_candidate(self) -> None:
        generator = StrategyCodeGenerator()
        first = generator.generate("alpha", lookback=4, entry_threshold=0.02)
        second = generator.generate("alpha", lookback=4, entry_threshold=0.02)
        assert first.source == second.source
        assert first.content_hash == second.content_hash
        assert first.parameters["lookback"] == 4

    def test_generated_strategy_runs_in_sandbox(self) -> None:
        candidate = StrategyCodeGenerator().generate("sandbox-check", lookback=3)
        result = CodeSandbox(timeout_seconds=30).execute(
            candidate.source,
            entry_expression="generate_signals([100.0, 101.0, 100.5, 102.0, 103.0, 104.0])",
        )
        assert result.ok, result.error
        assert result.value is not None

    def test_variant_grid_sizes(self) -> None:
        candidates = StrategyCodeGenerator().variant_grid("grid", lookbacks=(2, 3), entry_thresholds=(0.01, 0.02))
        assert len(candidates) == 4

    def test_invalid_parameters_rejected(self) -> None:
        generator = StrategyCodeGenerator()
        with pytest.raises(ValueError):
            generator.generate("x", lookback=1)
        with pytest.raises(ValueError):
            generator.generate("x", entry_threshold=0.01, exit_threshold=0.02)
