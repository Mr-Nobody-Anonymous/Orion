"""ETF market specialist.

ETFs are treated as diversified baskets with longer preferred lookback
windows than individual equities.
"""

from ...data.contracts import Asset, AssetClass
from ..specialist import SpecialistConfig


def etf_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.ETF,
        preferred_lookback=10,
        max_position_fraction=0.20,
        min_volume=__import__("decimal").Decimal("0"),
        notes=("basket-diversification",),
    )


__all__ = ["etf_specialist"]
