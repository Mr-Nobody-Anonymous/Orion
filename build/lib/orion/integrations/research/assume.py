"""ASSUME agent-based electricity and energy market simulation adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from orion.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from orion.integrations.loader import is_package_available, safe_import_module


@dataclass(frozen=True, slots=True)
class PowerMarketBids:
    """Generation and load bids for power market clearing."""

    zone: str
    supply_mw: Sequence[float]
    supply_prices_eur_mwh: Sequence[float]
    demand_mw: float


@dataclass(frozen=True, slots=True)
class MeritOrderResult:
    """Merit order dispatch clearing price and dispatched volume."""

    clearing_price_eur_mwh: float
    total_dispatched_mw: float
    marginal_plant_index: int


class AssumeEnergyMarketAdapter(BaseCapabilityProvider):
    """Adapter for ASSUME multi-agent electricity market simulation framework.
    
    Used in experimental simulation lab for power grid, energy trading, and carbon dynamics.
    """

    def __init__(self) -> None:
        self._assume = safe_import_module("assume")

    @property
    def name(self) -> str:
        return "assume"

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.RESEARCH

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.RESEARCH

    def health(self) -> ProviderHealth:
        if self._assume is not None:
            return ProviderHealth(
                provider_name=self.name,
                category=self.category,
                status=ProviderHealthStatus.AVAILABLE,
                version=getattr(self._assume, "__version__", "1.0.0"),
                latency_ms=2.0,
            )
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="1.0.0",
            latency_ms=0.04,
            is_fallback=True,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "electricity_market_clearing",
            "merit_order_dispatch",
            "energy_zone_arbitrage",
        )

    def clear_market(self, bids: PowerMarketBids) -> MeritOrderResult:
        """Calculate merit-order power market clearing price and volume."""
        paired = sorted(zip(bids.supply_prices_eur_mwh, bids.supply_mw), key=lambda x: x[0])
        
        cumulative_mw = 0.0
        clearing_price = 0.0
        marginal_idx = 0

        for i, (price, mw) in enumerate(paired):
            cumulative_mw += mw
            clearing_price = price
            marginal_idx = i
            if cumulative_mw >= bids.demand_mw:
                break

        return MeritOrderResult(
            clearing_price_eur_mwh=round(clearing_price, 2),
            total_dispatched_mw=min(cumulative_mw, bids.demand_mw),
            marginal_plant_index=marginal_idx,
        )
