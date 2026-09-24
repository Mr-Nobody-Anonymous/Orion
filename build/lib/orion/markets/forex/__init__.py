"""Forex market specialist."""

from decimal import Decimal

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def forex_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.FOREX,
        preferred_lookback=5,
        max_position_fraction=0.10,
        min_volume=Decimal("0"),
        notes=("24-hour-session", "carry-trade"),
    )


__all__ = ["forex_specialist"]
