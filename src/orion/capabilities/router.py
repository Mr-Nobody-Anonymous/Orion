"""Central Capability Router: dynamic intent routing and resilient fallback management."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from .base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ExecutionAuditRecord:
    """Telemetry record for an invoked capability."""

    category: str
    selected_provider: str
    fallback_used: bool
    fallback_provider: str | None
    latency_ms: float
    success: bool
    error: str | None = None


class CapabilityRouter:
    """The central capability dispatch router.

    Maintains provider priority chains:
    Primary External Engine -> Secondary External Engine -> Native Resilient Fallback
    """

    def __init__(self) -> None:
        self._providers: dict[CapabilityCategory, list[BaseCapabilityProvider]] = {
            cat: [] for cat in CapabilityCategory
        }
        self._audit_log: list[ExecutionAuditRecord] = []

    def register_provider(self, provider: BaseCapabilityProvider, priority: int = 50) -> None:
        """Register a provider for a capability category."""
        providers_list = self._providers.setdefault(provider.category, [])
        # Insert avoiding duplicates
        existing = [p for p in providers_list if p.name == provider.name]
        if existing:
            providers_list.remove(existing[0])
        providers_list.append(provider)

    def get_providers(self, category: CapabilityCategory) -> list[BaseCapabilityProvider]:
        """Return all registered providers for a category, sorted by priority (adapters first, native fallback last)."""
        providers = self._providers.get(category, [])
        # Sort so non-native (adapters/dependencies) are tried before native fallbacks
        return sorted(providers, key=lambda p: (1 if p.is_native else 0, p.name))

    def get_provider(self, category: CapabilityCategory, name: str) -> BaseCapabilityProvider | None:
        """Fetch a specific provider by category and name."""
        for p in self._providers.get(category, []):
            if p.name == name:
                return p
        return None

    def get_native_fallback(self, category: CapabilityCategory) -> BaseCapabilityProvider | None:
        """Fetch the pure zero-dependency native fallback for a category."""
        for p in self._providers.get(category, []):
            if p.is_native:
                return p
        return None

    def execute_with_fallback(
        self,
        category: CapabilityCategory,
        preferred_provider_name: str | None,
        operation: Callable[[BaseCapabilityProvider], T],
    ) -> tuple[T, ExecutionAuditRecord]:
        """Execute an operation with guaranteed multi-tier fallback protection."""
        start_time = time.monotonic()
        providers = self.get_providers(category)
        
        if not providers:
            raise RuntimeError(f"No providers registered for capability category {category.value}")

        # If a preferred provider is specified, try it first
        candidate_queue: list[BaseCapabilityProvider] = []
        if preferred_provider_name:
            pref = [p for p in providers if p.name == preferred_provider_name]
            if pref:
                candidate_queue.extend(pref)
        
        # Add remaining providers
        for p in providers:
            if p not in candidate_queue:
                candidate_queue.append(p)

        last_error: Exception | None = None
        executed_provider: BaseCapabilityProvider | None = None
        fallback_used = False
        fallback_name: str | None = None

        for idx, provider in enumerate(candidate_queue):
            try:
                # Check health before invoking (unless it's the native fallback)
                if not provider.is_native:
                    health = provider.health()
                    if health.status in (ProviderHealthStatus.UNAVAILABLE, ProviderHealthStatus.ISOLATED):
                        continue

                result = operation(provider)
                executed_provider = provider
                if idx > 0:
                    fallback_used = True
                    fallback_name = provider.name
                
                latency_ms = round((time.monotonic() - start_time) * 1000, 2)
                audit = ExecutionAuditRecord(
                    category=category.value,
                    selected_provider=executed_provider.name,
                    fallback_used=fallback_used,
                    fallback_provider=fallback_name,
                    latency_ms=latency_ms,
                    success=True,
                )
                self._audit_log.append(audit)
                return result, audit

            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"Provider {provider.name} failed for {category.value}: {exc}. Triggering next candidate..."
                )
                continue

        # If all candidates failed
        latency_ms = round((time.monotonic() - start_time) * 1000, 2)
        audit = ExecutionAuditRecord(
            category=category.value,
            selected_provider="NONE",
            fallback_used=fallback_used,
            fallback_provider=None,
            latency_ms=latency_ms,
            success=False,
            error=str(last_error),
        )
        self._audit_log.append(audit)
        raise RuntimeError(f"All providers failed for {category.value}. Last error: {last_error}") from last_error

    def health_overview(self) -> dict[str, Any]:
        """Aggregate health status across all registered capability providers."""
        report: dict[str, list[dict[str, Any]]] = {}
        total_providers = 0
        available_providers = 0

        for cat, providers in self._providers.items():
            cat_list = []
            for p in providers:
                total_providers += 1
                h = p.health()
                if h.status in (ProviderHealthStatus.AVAILABLE, ProviderHealthStatus.SIMULATED):
                    available_providers += 1
                cat_list.append(h.as_dict())
            report[cat.value] = cat_list

        return {
            "total_providers": total_providers,
            "available_providers": available_providers,
            "coverage_pct": round((available_providers / max(1, total_providers)) * 100, 1),
            "categories": report,
            "recent_audit_log": [
                {
                    "category": r.category,
                    "provider": r.selected_provider,
                    "fallback": r.fallback_used,
                    "latency_ms": r.latency_ms,
                    "success": r.success,
                }
                for r in self._audit_log[-20:]
            ],
        }
