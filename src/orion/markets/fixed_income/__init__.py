"""Fixed-income market specialist."""

from decimal import Decimal

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def fixed_income_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.BOND,
        preferred_lookback=20,
        max_position_fraction=0.20,
        min_volume=Decimal("0"),
        notes=("duration-risk", "credit-risk"),
    )


__all__ = ["fixed_income_specialist"]
