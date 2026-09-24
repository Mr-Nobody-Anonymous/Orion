"""Options market specialist."""

from decimal import Decimal

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def options_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.OPTION,
        preferred_lookback=3,
        max_position_fraction=0.02,
        min_volume=Decimal("0"),
        notes=("non-linear-payoff", "vega-gamma-theta"),
    )


__all__ = ["options_specialist"]
