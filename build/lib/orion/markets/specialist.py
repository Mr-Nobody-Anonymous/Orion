"""Asset-class specialists.

ORION remains asset-class agnostic at the executive layer, but uses
specialized routines for asset classes whose microstructure differs. The
specialist is a thin adapter that chooses an appropriate strategy and
risk parameter set for the asset.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..data.contracts import Asset, AssetClass


@dataclass(frozen=True, slots=True)
class SpecialistConfig:
    asset_class: AssetClass
    preferred_lookback: int
    max_position_fraction: float
    min_volume: Decimal
    notes: tuple[str, ...] = ()


def default_specialist(asset: Asset) -> SpecialistConfig:
    table: dict[AssetClass, SpecialistConfig] = {
        AssetClass.EQUITY: SpecialistConfig(
            asset_class=AssetClass.EQUITY,
            preferred_lookback=5,
            max_position_fraction=0.10,
            min_volume=Decimal("0"),
            notes=("session-hours", "fractional-shares-disabled"),
        ),
        AssetClass.ETF: SpecialistConfig(
            asset_class=AssetClass.ETF,
            preferred_lookback=10,
            max_position_fraction=0.20,
            min_volume=Decimal("0"),
            notes=("basket-diversification",),
        ),
        AssetClass.BOND: SpecialistConfig(
            asset_class=AssetClass.BOND,
            preferred_lookback=20,
            max_position_fraction=0.20,
            min_volume=Decimal("0"),
            notes=("duration-risk", "credit-risk"),
        ),
        AssetClass.FUTURE: SpecialistConfig(
            asset_class=AssetClass.FUTURE,
            preferred_lookback=5,
            max_position_fraction=0.05,
            min_volume=Decimal("0"),
            notes=("roll-yield", "leverage-amplified"),
        ),
        AssetClass.COMMODITY: SpecialistConfig(
            asset_class=AssetClass.COMMODITY,
            preferred_lookback=10,
            max_position_fraction=0.05,
            min_volume=Decimal("0"),
            notes=("contango-backwardation",),
        ),
        AssetClass.FOREX: SpecialistConfig(
            asset_class=AssetClass.FOREX,
            preferred_lookback=5,
            max_position_fraction=0.10,
            min_volume=Decimal("0"),
            notes=("24-hour-session", "carry-trade"),
        ),
        AssetClass.CRYPTO: SpecialistConfig(
            asset_class=AssetClass.CRYPTO,
            preferred_lookback=3,
            max_position_fraction=0.03,
            min_volume=Decimal("0"),
            notes=("24-hour-session", "high-volatility", "no-circuit-breakers"),
        ),
        AssetClass.OPTION: SpecialistConfig(
            asset_class=AssetClass.OPTION,
            preferred_lookback=3,
            max_position_fraction=0.02,
            min_volume=Decimal("0"),
            notes=("non-linear-payoff", "vega-gamma-theta"),
        ),
        AssetClass.VOLATILITY: SpecialistConfig(
            asset_class=AssetClass.VOLATILITY,
            preferred_lookback=10,
            max_position_fraction=0.02,
            min_volume=Decimal("0"),
            notes=("mean-reverting", "regime-sensitive"),
        ),
        AssetClass.PREDICTION_MARKET: SpecialistConfig(
            asset_class=AssetClass.PREDICTION_MARKET,
            preferred_lookback=3,
            max_position_fraction=0.05,
            min_volume=Decimal("0"),
            notes=("binary-outcome", "liquidity-thin"),
        ),
        AssetClass.ALTERNATIVE: SpecialistConfig(
            asset_class=AssetClass.ALTERNATIVE,
            preferred_lookback=10,
            max_position_fraction=0.05,
            min_volume=Decimal("0"),
            notes=("bespoke-microstructure",),
        ),
    }
    return table.get(asset.asset_class, table[AssetClass.EQUITY])


def specialist_for(
    asset: Asset, *, custom: dict[AssetClass, SpecialistConfig] | None = None
) -> SpecialistConfig:
    if custom and asset.asset_class in custom:
        return custom[asset.asset_class]
    return default_specialist(asset)
