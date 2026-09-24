from __future__ import annotations

from typing import Any, Protocol

from ...infrastructure.hardware import detect_hardware
from ...models.local import OllamaConfig, OllamaProvider
from ...models.routing import HardwareProfile, LocalModelRouter


class LLMProvider(Protocol):
    def generate(self, request: str) -> str: ...

    def embed(self, text: str) -> list[float]: ...

    def analyze(self, data: Any) -> dict[str, Any]: ...


def detect_hardware_profile() -> HardwareProfile:
    return detect_hardware()


def create_local_llm_provider(model: str | None = None) -> tuple[LLMProvider, LocalModelRouter, HardwareProfile]:
    hardware = detect_hardware_profile()
    router = LocalModelRouter(hardware)
    return OllamaProvider(OllamaConfig(model=model or "qwen2.5:7b")), router, hardware
