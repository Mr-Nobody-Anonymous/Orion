"""Model inference capability contract for local and cloud runtimes."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """Request to invoke an LLM or reasoning model."""

    prompt: str
    system_prompt: str = ""
    max_tokens: int = 1024
    temperature: float = 0.2
    model_name: str = "default"
    stop_sequences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InferenceResponse:
    """Output of an LLM or reasoning engine."""

    provider_name: str
    model_name: str
    text: str
    tokens_generated: int
    latency_ms: float
    finish_reason: str
    is_local: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "text": self.text,
            "tokens_generated": self.tokens_generated,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "is_local": self.is_local,
        }


class InferenceProvider(BaseCapabilityProvider):
    """Abstract interface for model execution runtimes (Ollama / AirLLM / Cloud / Native)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.INFERENCE

    @abstractmethod
    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Run inference and return structured response."""
