from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...infrastructure.configuration import AIMode


class AIProvider(Protocol):
    def generate(self, request: str) -> str: ...

    def embed(self, text: str) -> list[float]: ...

    def analyze(self, data: Any) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    ram_gb: int
    vram_gb: int = 0
    gpu_name: str | None = None
    cuda_available: bool = False


@dataclass(frozen=True, slots=True)
class ModelTier:
    name: str
    parameter_hint: str


class LocalModelRouter:
    def __init__(self, hardware: HardwareProfile, tiers: tuple[ModelTier, ...] | None = None) -> None:
        self.hardware = hardware
        self.tiers = tiers or (
            ModelTier("small", "7B Q4"),
            ModelTier("medium", "13B Q4"),
            ModelTier("large", "32B Q4"),
        )

    def select(self, complexity: str = "routine") -> ModelTier:
        if complexity == "routine" or self.hardware.ram_gb < 32:
            return self.tiers[0]
        if self.hardware.ram_gb < 64 or self.hardware.vram_gb < 16:
            return self.tiers[min(1, len(self.tiers) - 1)]
        return self.tiers[-1]


class ProviderRouter:
    def __init__(self, mode: AIMode, local: AIProvider, cloud: AIProvider | None = None) -> None:
        self.mode = mode
        self.local = local
        self.cloud = cloud

    def provider_for(self, complexity: str = "routine") -> AIProvider:
        if self.mode is AIMode.LOCAL or self.cloud is None:
            return self.local
        if self.mode is AIMode.HYBRID and complexity != "routine":
            return self.cloud
        return self.local
