import os

from .infrastructure.hardware import detect_hardware
from .intelligence.llm.ollama import OllamaConfig, OllamaProvider
from .intelligence.llm.providers import create_local_llm_provider
from .models.routing.router import AIProvider, HardwareProfile, LocalModelRouter

__all__ = ["AIProvider", "HardwareProfile", "LocalModelRouter", "OllamaConfig", "OllamaProvider", "create_local_provider", "detect_hardware"]


def create_local_provider() -> tuple[AIProvider, LocalModelRouter, HardwareProfile]:
    return create_local_llm_provider(model=os.getenv("ORION_OLLAMA_MODEL", "qwen2.5:7b"))
