"""Crypto market specialist.

Crypto assets trade 24/7 with no circuit breakers and high volatility. The
specialist reduces default position size and shortens the preferred
lookback window.
"""

from ..specialist import SpecialistConfig
from ...data.contracts import Asset, AssetClass


def crypto_specialist(asset: Asset) -> SpecialistConfig:
    return SpecialistConfig(
        asset_class=AssetClass.CRYPTO,
        preferred_lookback=3,
        max_position_fraction=0.03,
        min_volume=__import__("decimal").Decimal("0"),
        notes=("24-hour-session", "high-volatility", "no-circuit-breakers"),
    )


__all__ = ["crypto_specialist"]
