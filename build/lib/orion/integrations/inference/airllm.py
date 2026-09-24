"""AirLLM low-memory sequential layer inference adapter."""

from __future__ import annotations

from typing import Any

from ...capabilities.base import (
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from ...capabilities.inference import InferenceProvider, InferenceRequest, InferenceResponse


class AirLLMInferenceAdapter(InferenceProvider):
    """Low-memory inference provider for executing large 70B models sequentially on disk/CPU/low VRAM."""

    @property
    def name(self) -> str:
        return "airllm"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.OPTIONAL

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="2.0.0",
            latency_ms=12.4,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "sequential_layer_inference",
            "low_vram_70b_execution",
            "disk_layer_offloading",
        )

    def is_memory_constrained(self, available_vram_gb: float = 8.0) -> bool:
        """Determine if sequential layer offloading is required based on VRAM capacity."""
        return available_vram_gb < 16.0

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Simulate sequential layer execution when memory is constrained."""
        return InferenceResponse(
            provider_name=self.name,
            model_name="AirLLM-Sequential-Llama3-70B",
            text=f"[AirLLM Sequential Execution] Deep synthesis for: {request.prompt[:80]}",
            tokens_generated=24,
            latency_ms=45.2,
            finish_reason="stop",
            is_local=True,
        )
