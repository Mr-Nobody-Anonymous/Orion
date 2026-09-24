"""Fixed income, yield curves, and bond analytics capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class YieldCurveRequest:
    """Request to fit or interpolate a sovereign yield curve."""

    maturities_years: Sequence[float]
    rates: Sequence[float]
    target_maturities: Sequence[float]
    method: str = "cubic_spline"  # linear, cubic_spline, nelson_siegel


@dataclass(frozen=True, slots=True)
class BondPricingRequest:
    """Request to price a fixed coupon or zero-coupon bond."""

    face_value: float
    coupon_rate_pct: float
    years_to_maturity: float
    yield_to_maturity_pct: float
    frequency: int = 2  # semi-annual


@dataclass(frozen=True, slots=True)
class BondPricingResult:
    """Standardized analytical output for fixed income instruments."""

    provider_name: str
    clean_price: float
    dirty_price: float
    macaulay_duration_years: float
    modified_duration: float
    convexity: float
    dv01: float  # dollar value of a basis point

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "clean_price": self.clean_price,
            "dirty_price": self.dirty_price,
            "macaulay_duration_years": self.macaulay_duration_years,
            "modified_duration": self.modified_duration,
            "convexity": self.convexity,
            "dv01": self.dv01,
        }


@dataclass(frozen=True, slots=True)
class YieldCurveResult:
    """Interpolated zero-coupon term structure curve."""

    provider_name: str
    maturities: tuple[float, ...]
    discount_factors: tuple[float, ...]
    zero_rates: tuple[float, ...]
    forward_rates: tuple[float, ...]


class FixedIncomeProvider(BaseCapabilityProvider):
    """Abstract interface for fixed income and term structure modeling (QuantLib / native)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.FIXED_INCOME

    @abstractmethod
    def price_bond(self, request: BondPricingRequest) -> BondPricingResult:
        """Price a bond and calculate duration, convexity, and DV01."""

    @abstractmethod
    def interpolate_yield_curve(self, request: YieldCurveRequest) -> YieldCurveResult:
        """Fit a continuous term structure curve across benchmark tenors."""
