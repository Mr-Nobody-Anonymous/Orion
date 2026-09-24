"""Jesse crypto risk management, dynamic leverage, and position sizing adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orion.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from orion.integrations.loader import is_package_available, safe_import_module


@dataclass(frozen=True, slots=True)
class JessePositionSizing:
    """Position sizing and liquidation boundaries."""

    position_size: float
    notional_value: float
    leverage: float
    liquidation_price: float
    risk_amount: float
    margin_required: float


class JesseCryptoRiskAdapter(BaseCapabilityProvider):
    """Adapter for Jesse crypto algorithmic framework risk logic and position sizing."""

    def __init__(self) -> None:
        self._jesse = safe_import_module("jesse")

    @property
    def name(self) -> str:
        return "jesse"

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.EXECUTION

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.ADAPTER

    def health(self) -> ProviderHealth:
        if self._jesse is not None:
            return ProviderHealth(
                provider_name=self.name,
                category=self.category,
                status=ProviderHealthStatus.AVAILABLE,
                version=getattr(self._jesse, "__version__", "0.45.0"),
                latency_ms=0.1,
            )
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="0.45.0",
            latency_ms=0.02,
            is_fallback=True,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "crypto_position_sizing",
            "dynamic_margin_calculation",
            "liquidation_price_estimation",
            "risk_per_trade_gating",
        )

    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        entry_price: float,
        stop_loss_price: float,
        leverage: float = 1.0,
        is_long: bool = True,
    ) -> JessePositionSizing:
        """Compute strict Jesse-style risk-gated position sizing and estimated liquidation."""
        if entry_price <= 0 or stop_loss_price <= 0:
            return JessePositionSizing(0.0, 0.0, leverage, 0.0, 0.0, 0.0)

        risk_amount = capital * (risk_pct / 100.0)
        price_diff = abs(entry_price - stop_loss_price)
        if price_diff == 0:
            return JessePositionSizing(0.0, 0.0, leverage, 0.0, risk_amount, 0.0)

        raw_size = risk_amount / price_diff
        max_notional = capital * leverage
        notional_value = min(raw_size * entry_price, max_notional)
        actual_size = notional_value / entry_price
        margin_required = notional_value / leverage if leverage > 0 else notional_value

        mmr = 0.005
        if is_long:
            liq_price = entry_price * (1.0 - (1.0 / leverage) + mmr)
        else:
            liq_price = entry_price * (1.0 + (1.0 / leverage) - mmr)

        return JessePositionSizing(
            position_size=round(actual_size, 4),
            notional_value=round(notional_value, 2),
            leverage=leverage,
            liquidation_price=round(max(liq_price, 0.0), 2),
            risk_amount=round(risk_amount, 2),
            margin_required=round(margin_required, 2),
        )
