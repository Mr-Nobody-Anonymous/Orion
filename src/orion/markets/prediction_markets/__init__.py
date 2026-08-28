"""Prediction market specialist."""

from decimal import Decimal

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def prediction_market_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.PREDICTION_MARKET,
        preferred_lookback=3,
        max_position_fraction=0.05,
        min_volume=Decimal("0"),
        notes=("binary-outcome", "liquidity-thin"),
    )


__all__ = ["prediction_market_specialist"]
