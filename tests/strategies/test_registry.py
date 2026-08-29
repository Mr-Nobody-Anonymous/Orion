"""Tests for the Strategy Registry (audit §21): immutable lineage + gated lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from orion.strategies import StrategyRegistry, StrategyStatus


def sample_rules() -> dict:
    return {"entry": "momentum>0", "exit": "stop_loss=0.02", "lookback": 20}


class TestImmutableVersions:
    def test_register_creates_v1(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        version = registry.register("ORION-MOMENTUM", rules=sample_rules(), universe=("AAPL", "MSFT"))
        assert version.version == "v1"
        assert version.status == StrategyStatus.EXPERIMENTAL
        assert len(version.version_hash) == 16

    def test_registering_changed_definition_makes_v2(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        registry.register("STRAT", rules=sample_rules(), universe=("AAPL",))
        second = registry.register("STRAT", rules={**sample_rules(), "lookback": 30}, universe=("AAPL",))
        assert second.version == "v2"
        assert len(registry.history("STRAT")) == 2
        assert registry.get("STRAT").version == "v2"

    def test_history_is_never_overwritten(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        v1 = registry.register("STRAT", rules=sample_rules())
        v2 = registry.register("STRAT", rules={**sample_rules(), "lookback": 99})
        assert registry.get_version("STRAT", "v1") == v1
        assert registry.get_version("STRAT", "v2") == v2
        assert registry.history("STRAT")[0].version_hash != registry.history("STRAT")[1].version_hash

    def test_replay_from_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "s.jsonl"
        first = StrategyRegistry(path=path)
        first.register("STRAT", rules=sample_rules(), universe=("AAPL",))
        second = StrategyRegistry(path=path)
        assert second.get("STRAT") is not None
        assert second.get("STRAT").version == "v1"


class TestLifecycleGate:
    def test_full_promotion_path(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        registry.register("STRAT", rules=sample_rules())
        registry.transition("STRAT", "validating")
        registry.transition("STRAT", "approved")
        registry.transition("STRAT", "production")
        assert registry.get("STRAT").status == StrategyStatus.PRODUCTION

    def test_cannot_skip_to_production(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        registry.register("STRAT", rules=sample_rules())
        with pytest.raises(ValueError, match="illegal transition"):
            registry.transition("STRAT", "production")

    def test_rejected_is_terminal(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        registry.register("STRAT", rules=sample_rules())
        registry.transition("STRAT", "rejected")
        with pytest.raises(ValueError, match="illegal transition"):
            registry.transition("STRAT", "approved")

    def test_unknown_strategy(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        with pytest.raises(ValueError, match="unknown strategy"):
            registry.transition("NOPE", "approved")


class TestLineage:
    def test_lineage_chain_is_recorded(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        registry.register(
            "ORION-MOMENTUM-042",
            rules=sample_rules(),
            universe=("AAPL", "MSFT"),
            risk_params={"risk_model": "v12", "max_position": 0.05},
            lineage=("US-EQUITIES-2026-08", "momentum-features-v3", "Kronos-v17", "ensemble-v2"),
            backtest_ref="bt-2026-08-28-0001",
            walk_forward_ref="wf-2026-08-28-0001",
        )
        chain = registry.lineage("ORION-MOMENTUM-042")
        assert chain is not None
        assert chain["dataset"] == "US-EQUITIES-2026-08"
        assert chain["model"] == "Kronos-v17"
        assert chain["backtest"] == "bt-2026-08-28-0001"
        assert chain["strategy_version"]

    def test_summary_counts_statuses(self, tmp_path: Path) -> None:
        registry = StrategyRegistry(path=tmp_path / "s.jsonl")
        registry.register("A", rules=sample_rules())
        registry.register("B", rules={**sample_rules(), "lookback": 5})
        registry.transition("A", "validating")
        summary = registry.summary()
        assert summary["strategies"] == 2
        assert summary["by_status"]["experimental"] == 1
        assert summary["by_status"]["validating"] == 1


class TestSystemWireup:
    def test_orion_system_registers_and_promotes(self, tmp_path: Path, monkeypatch) -> None:
        from orion.experiments import JsonlExperimentBackend
        from orion.orchestration.system import OrionSystem

        monkeypatch.chdir(tmp_path)
        system = OrionSystem()
        assert isinstance(system.experiments.backend, JsonlExperimentBackend)

        started = system.start_experiment("sens-eval", tags={"env": "test"})
        assert started["experiment"]["name"] == "sens-eval"

        registered = system.register_strategy(
            "SYS-STRAT",
            rules={"lookback": 20},
            universe=("SPY",),
            lineage=("ds", "feat", "model"),
            backtest_ref="bt-1",
        )
        assert registered["strategy"]["version"] == "v1"

        promoted = system.promote_strategy("SYS-STRAT", "validating")
        assert promoted["strategy"]["status"] == "validating"
        assert system.strategy_lineage("SYS-STRAT")["lineage"]["backtest"] == "bt-1"
        assert system.strategy_registry_summary()["strategies"] == 1
        assert system.experiments_summary()["experiments"] == 1