"""Microsoft Qlib Adapter for ORION.

Translates Qlib alpha discovery, cross-sectional factor ranking, and LightGBM models
into canonical Orion ModelPrediction and Forecast schemas.
"""

from __future__ import annotations

from typing import Any, Mapping
from orion.data.contracts import Asset, Forecast


class QlibAdapter:
    """Canonical adapter facade for Microsoft Qlib."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "Microsoft Qlib"
        self.version = "0.9.3.99"

    def predict_cross_sectional(
        self,
        asset: Asset,
        factors: Mapping[str, float],
        horizon: str = "5d",
    ) -> Forecast:
        """Score an asset using multi-factor ranking model."""
        from orion.integrations.forecasting.qlib import QlibForecastingAdapter

        adapter = QlibForecastingAdapter()
        return adapter.predict_asset(asset, factors, horizon=horizon)
