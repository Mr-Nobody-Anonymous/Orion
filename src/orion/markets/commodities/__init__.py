"""Commodity market specialist."""

from decimal import Decimal

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def commodity_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.COMMODITY,
        preferred_lookback=10,
        max_position_fraction=0.05,
        min_volume=Decimal("0"),
        notes=("contango-backwardation",),
    )


__all__ = ["commodity_specialist"]
