"""Tests for the hardware profiler + local model router (audit §11)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from orion.infrastructure.hardware import HardwareProfile
from orion.infrastructure.hardware_profiler import (
    DEFAULT_TIERS,
    ExtendedHardwareProfile,
    HardwareProfiler,
    LocalModelRouter,
    ModelTier,
    TASK_COMPLEXITY,
    _ollama_probe,
)


def make_profile(*, ram_gb: int = 32, ollama_models: tuple[str, ...] = ("qwen2.5:7b",), ollama_available: bool = True) -> ExtendedHardwareProfile:
    return ExtendedHardwareProfile(
        base=HardwareProfile(ram_gb=ram_gb, gpu_name="mock", cuda_available=False),
        cpu_count=8,
        free_disk_gb=120.0,
        total_disk_gb=500.0,
        ollama_available=ollama_available,
        ollama_models=ollama_models,
    )


class TestHardwareProfiler:
    def test_ollama_probe_returns_tuple(self) -> None:
        # The probe must never raise (graceful no-op when ollama is down).
        result = _ollama_probe("http://127.0.0.1:1", timeout=0.2)
        assert isinstance(result, tuple) and len(result) == 2
        ok, models = result
        assert ok is False and models == ()

    def test_snapshot_does_not_explode(self) -> None:
        profile = HardwareProfiler(probe_ollama=False).snapshot()
        # Windows CI may return 0 RAM; we only require the dataclass is well-formed.
        assert profile.cpu_count >= 0
        assert profile.free_disk_gb >= 0
        assert profile.total_disk_gb >= 0
        assert profile.ollama_available is False


class TestLocalModelRouter:
    def test_complexity_must_be_valid(self) -> None:
        router = LocalModelRouter(profile=make_profile())
        with pytest.raises(ValueError, match="complexity"):
            router.select("impossible")

    def test_standard_when_ollama_has_model(self) -> None:
        router = LocalModelRouter(profile=make_profile(ollama_models=("qwen2.5:7b",)))
        tier = router.select("standard")
        assert tier.backend == "ollama"
        assert tier.model == "qwen2.5:7b"
        assert tier.context_window == DEFAULT_TIERS["standard"]["context_window"]

    def test_low_ram_downgrades_deep_to_standard(self) -> None:
        router = LocalModelRouter(profile=make_profile(ram_gb=4, ollama_models=("qwen2.5:14b",)))
        tier = router.select("deep")
        assert tier.model == DEFAULT_TIERS["standard"]["name"]
        assert "downgraded" in tier.reason

    def test_context_overflow_escalates(self) -> None:
        router = LocalModelRouter(
            profile=make_profile(ram_gb=32, ollama_models=("qwen2.5:7b", "qwen2.5:14b"))
        )
        tier = router.select("cheap", context_tokens=200_000)
        assert tier.model == DEFAULT_TIERS["deep"]["name"]
        assert "context" in tier.reason

    def test_latency_budget_chooses_cheap(self) -> None:
        router = LocalModelRouter(profile=make_profile())
        tier = router.select("standard", latency_budget_s=0.5)
        assert tier.model == DEFAULT_TIERS["cheap"]["name"]
        assert "latency" in tier.reason

    def test_missing_model_warns_but_continues(self) -> None:
        router = LocalModelRouter(
            profile=make_profile(ollama_models=("phi3:mini",))
        )
        tier = router.select("cheap")
        # fallback is phi3:mini and is present, so the router uses it
        assert tier.model == "phi3:mini"
        assert "fallback" in tier.reason or "using" in tier.reason

    def test_ollama_unavailable_falls_back_to_http(self) -> None:
        router = LocalModelRouter(profile=make_profile(ollama_available=False, ollama_models=()))
        tier = router.select("standard")
        assert tier.backend == "http"
        assert "ollama not reachable" in tier.reason

    def test_summary_shape(self) -> None:
        profile = make_profile()
        summary = LocalModelRouter(profile=profile).summary()
        assert summary["hardware"]["ram_gb"] == 32
        assert "cheap" in summary["tiers"]


class TestSystemWireup:
    def test_orion_system_selects_local_model(self) -> None:
        from orion.infrastructure.hardware_profiler import ExtendedHardwareProfile
        from orion.orchestration.system import OrionSystem

        system = OrionSystem()
        system.hardware_profile = make_profile()
        system.model_router = LocalModelRouter(profile=system.hardware_profile)
        result = system.select_local_model("cheap")
        assert result["status"] == "IMPLEMENTED"
        assert result["tier"]["backend"] == "ollama"

    def test_orion_system_snapshots_hardware(self) -> None:
        from orion.orchestration.system import OrionSystem

        result = OrionSystem().snapshot_hardware()
        assert result["status"] == "IMPLEMENTED"
        assert "ram_gb" in result["hardware"]
        assert "tiers" in result