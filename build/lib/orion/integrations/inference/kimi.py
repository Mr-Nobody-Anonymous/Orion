"""Kimi K3 in C isolated reference provider."""

from __future__ import annotations

from typing import Any

from ...capabilities.base import (
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from ...capabilities.inference import InferenceProvider, InferenceRequest, InferenceResponse


class KimiInferenceAdapter(InferenceProvider):
    """Isolated experimental provider for Kimi K3 in C (1.56TB checkpoint - kept isolated)."""

    @property
    def name(self) -> str:
        return "kimi_k3"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.ISOLATED

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.ISOLATED,
            version="1.0.0",
            latency_ms=0.0,
            last_error="Checkpoint requires 1.56 TB model weights; marked isolated for research provenance",
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "c_inference_kernel",
            "low_level_memory_mapping",
        )

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        raise NotImplementedError(
            "Kimi K3 in C is isolated due to 1.56 TB checkpoint requirements. Use Ollama or AirLLM instead."
        )
