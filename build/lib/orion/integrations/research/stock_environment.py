"""Historical stock trading Gym environment provenance and research benchmark adapter."""

from __future__ import annotations

from typing import Any

from orion.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)


class StockTradingEnvironmentProvenance(BaseCapabilityProvider):
    """Archived historical reference provider for OpenAI Gym stock trading environments.
    
    Status: DEPRECATED / PROVENANCE
    Superseded By: FinRL-Meta, FinRL, and Orion Native Market Simulators
    """

    @property
    def name(self) -> str:
        return "stock_trading_environment"

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.REINFORCEMENT_LEARNING

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.DEPRECATED

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.DEPRECATED,
            version="0.1.0",
            latency_ms=0.0,
            last_error="Archived historical benchmark repository preserved for algorithmic provenance",
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "historical_gym_trading_environment",
            "legacy_discrete_action_spaces",
        )

    def get_provenance_metadata(self) -> dict[str, Any]:
        return {
            "repository": "Stock-Trading-Environment",
            "category": "experimental",
            "original_author": "notadamking",
            "license": "MIT",
            "status": "deprecated",
            "superseded_by": ["finrl_meta", "finrl", "orion_native_backtest"],
            "preservation_reason": "Historical baseline for custom Gym discrete action trading environments",
        }
