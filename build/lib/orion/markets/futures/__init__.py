"""Futures market specialist."""

from decimal import Decimal

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def futures_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.FUTURE,
        preferred_lookback=5,
        max_position_fraction=0.05,
        min_volume=Decimal("0"),
        notes=("roll-yield", "leverage-amplified"),
    )


__all__ = ["futures_specialist"]
