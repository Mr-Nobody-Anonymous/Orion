from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CloudProviderUnavailable(RuntimeError):
    """Raised when a cloud capability was requested without a configured provider."""


@dataclass(frozen=True, slots=True)
class NullCloudProvider:
    """Explicit BLOCKED provider until credentials, budget, and evaluation controls are configured."""

    provider_name: str = "unconfigured-cloud-provider"

    def generate(self, request: str) -> str:
        raise CloudProviderUnavailable(f"{self.provider_name} is not configured in this environment")

    def embed(self, text: str) -> list[float]:
        raise CloudProviderUnavailable(f"{self.provider_name} is not configured in this environment")

    def analyze(self, data: Any) -> dict[str, Any]:
        raise CloudProviderUnavailable(f"{self.provider_name} is not configured in this environment")
