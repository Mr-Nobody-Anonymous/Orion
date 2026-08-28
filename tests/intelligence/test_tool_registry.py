"""Tests for the permissioned tool registry."""

from __future__ import annotations

import pytest

from orion.intelligence import (
    AgentProfile,
    ToolPermission,
    ToolRegistry,
    ToolSpec,
    register_builtin_tools,
)
from orion.memory import LayeredMemory


@pytest.fixture()
def registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_builtin_tools(registry, memory=LayeredMemory())
    return registry


ANALYST = AgentProfile("analyst", frozenset({ToolPermission.COMPUTE, ToolPermission.MARKET_DATA, ToolPermission.MEMORY}))
QUANT = AgentProfile(
    "quant",
    frozenset({ToolPermission.COMPUTE, ToolPermission.BACKTEST, ToolPermission.SIMULATION,
               ToolPermission.PRICING, ToolPermission.MARKET_DATA}),
)


class TestPermissions:
    def test_allowed_invocation(self, registry: ToolRegistry) -> None:
        result = registry.invoke(ANALYST, "calculator", expression="2 + 2 * 3")
        assert result.ok and result.value == 8.0
        assert result.record.allowed and result.record.ok

    def test_denial_without_permission(self, registry: ToolRegistry) -> None:
        result = registry.invoke(ANALYST, "backtest", prices=[100.0, 101.0, 102.0, 103.0, 104.0])
        assert not result.ok
        assert "lacks permission" in result.error
        assert registry.denials()

    def test_unknown_tool(self, registry: ToolRegistry) -> None:
        result = registry.invoke(ANALYST, "nuke", x=1)
        assert not result.ok and "unknown tool" in result.error

    def test_tool_failure_is_a_result(self, registry: ToolRegistry) -> None:
        result = registry.invoke(ANALYST, "calculator", expression="1 / 0")
        assert not result.ok
        assert "ZeroDivision" in result.error

    def test_duplicate_registration_rejected(self, registry: ToolRegistry) -> None:
        with pytest.raises(ValueError):
            registry.register(ToolSpec("calculator", "dup", ToolPermission.COMPUTE, lambda: 1))

    def test_audit_trail_records_everything(self, registry: ToolRegistry) -> None:
        registry.invoke(ANALYST, "calculator", expression="1 + 1")
        registry.invoke(ANALYST, "backtest", prices=[1.0])
        assert len(registry.audit_log()) == 2
        assert len(registry.denials()) == 1


class TestBuiltinTools:
    def test_calculator_rejects_non_arithmetic(self, registry: ToolRegistry) -> None:
        result = registry.invoke(ANALYST, "calculator", expression="__import__('os').system('dir')")
        assert not result.ok

    def test_statistics_tool(self, registry: ToolRegistry) -> None:
        result = registry.invoke(ANALYST, "statistics", values=[1.0, 2.0, 3.0], statistic="mean")
        assert result.ok and result.value == 2.0

    def test_backtest_tool(self, registry: ToolRegistry) -> None:
        prices = [100.0, 101.0, 100.5, 102.0, 103.0, 104.0, 105.0, 104.5]
        result = registry.invoke(QUANT, "backtest", prices=prices, lookback=3)
        assert result.ok
        assert "sharpe" in result.value

    def test_regime_tool(self, registry: ToolRegistry) -> None:
        prices = [100.0 * (1.004 ** i) for i in range(40)]
        result = registry.invoke(ANALYST, "regime", prices=prices)
        assert result.ok
        assert result.value["regime"] == "bull_trend"

    def test_pricing_tool(self, registry: ToolRegistry) -> None:
        result = registry.invoke(QUANT, "option_price", spot=100, strike=100, maturity=1.0, rate=0.05, volatility=0.2)
        assert result.ok and 5 < result.value < 20

    def test_memory_tool(self) -> None:
        from orion.memory import LayeredMemory, MemoryLayer

        memory = LayeredMemory()
        memory.remember(MemoryLayer.SEMANTIC, {"topic": "gold"}, summary="gold seasonality study", tags={"gold"})
        registry = ToolRegistry()
        register_builtin_tools(registry, memory=memory)
        result = registry.invoke(ANALYST, "memory_search", query="gold")
        assert result.ok
        assert any("gold" in item["summary"] for item in result.value)
