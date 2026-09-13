"""ORION Canonical Machine Learning Engine."""

from __future__ import annotations

from typing import Any, Mapping
from orion.data.contracts import Asset, Forecast


class MachineLearningEngine:
    """Unified machine learning engine backed by Qlib factor models and LightGBM."""

    def predict_asset(
        self,
        asset: Asset,
        features: Mapping[str, float],
        model_family: str = "lightgbm",
    ) -> Forecast:
        from adapters.qlib import QlibAdapter

        adapter = QlibAdapter()
        return adapter.predict_cross_sectional(asset, features)
