"""Base definitions and health metadata for the Orion Capability Layer.

Defines pure, typed interfaces for all capability providers, health telemetry,
and integration metadata.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Sequence


class ProviderHealthStatus(str, Enum):
    """Lifecycle and operational status of a capability provider."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    ISOLATED = "isolated"
    SIMULATED = "simulated"
    DEPRECATED = "deprecated"


class CapabilityCategory(str, Enum):
    """High-level functional domains of Orion capabilities."""

    FORECASTING = "forecasting"
    BACKTESTING = "backtesting"
    OPTIONS = "options"
    FIXED_INCOME = "fixed_income"
    PREDICTION_MARKETS = "prediction_markets"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    SENTIMENT = "sentiment"
    INFERENCE = "inference"
    EXECUTION = "execution"
    AGENT_MEMORY = "agent_memory"
    RESEARCH = "research"
    EVOLUTION = "evolution"


class IntegrationClass(str, Enum):
    """Architectural classification of the underlying implementation."""

    DEPENDENCY = "dependency"
    ADAPTER = "adapter"
    SIDECAR = "sidecar"
    OPTIONAL = "optional"
    RESEARCH = "research"
    BENCHMARK = "benchmark"
    FALLBACK = "fallback"
    CONCEPTUAL = "conceptual"
    ISOLATED = "isolated"
    DEPRECATED = "deprecated"
    NATIVE = "native"


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Standardized health snapshot for any integration provider."""

    provider_name: str
    category: CapabilityCategory
    status: ProviderHealthStatus
    version: str
    latency_ms: float
    last_error: str | None = None
    is_fallback: bool = False
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "category": self.category.value,
            "status": self.status.value,
            "version": self.version,
            "latency_ms": self.latency_ms,
            "last_error": self.last_error,
            "is_fallback": self.is_fallback,
            "checked_at": self.checked_at,
        }


class BaseCapabilityProvider(ABC):
    """Abstract base class for all Orion capability providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the provider (e.g. 'kronos', 'vectorbt', 'orion_native')."""

    @property
    @abstractmethod
    def category(self) -> CapabilityCategory:
        """The functional capability domain."""

    @property
    @abstractmethod
    def integration_class(self) -> IntegrationClass:
        """The architectural classification."""

    @property
    def is_native(self) -> bool:
        """True if this provider is a pure, zero-dependency Orion native implementation."""
        return self.integration_class == IntegrationClass.NATIVE

    @abstractmethod
    def health(self) -> ProviderHealth:
        """Perform a quick, non-destructive health check and return status."""

    @abstractmethod
    def capabilities(self) -> tuple[str, ...]:
        """List of fine-grained capability tokens provided."""

    @property
    def version(self) -> str:
        """Version string of the underlying engine."""
        return "1.0.0"

    @property
    def dependencies(self) -> tuple[str, ...]:
        """List of required third-party packages or services."""
        return ()

    def provenance(self) -> dict[str, Any]:
        """Provenance metadata linking back to source repository and licenses."""
        return {
            "name": self.name,
            "category": self.category.value,
            "integration": self.integration_class.value,
            "is_native": self.is_native,
            "dependencies": list(self.dependencies),
        }
