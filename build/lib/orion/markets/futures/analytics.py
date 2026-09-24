"""Futures Term Structure and Basis Analytics.

Calculates cash-and-carry basis, annualized roll yield, and detects Contango / Backwardation.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Sequence


class TermStructureRegime(str, Enum):
    CONTANGO = "CONTANGO"
    BACKWARDATION = "BACKWARDATION"
    FLAT = "FLAT"


@dataclass(frozen=True, slots=True)
class FuturesBasisMetrics:
    symbol: str
    spot_price: Decimal
    futures_price: Decimal
    days_to_expiry: int
    basis: Decimal  # Futures - Spot
    basis_percentage: Decimal
    annualized_basis_yield: Decimal
    regime: TermStructureRegime


class FuturesAnalyticsEngine:
    """Futures term structure and basis modeling."""

    @staticmethod
    def calculate_basis(
        symbol: str,
        spot_price: Decimal,
        futures_price: Decimal,
        days_to_expiry: int,
    ) -> FuturesBasisMetrics:
        if spot_price <= 0:
            raise ValueError("Spot price must be positive")
        if days_to_expiry <= 0:
            raise ValueError("Days to expiry must be at least 1")

        basis = futures_price - spot_price
        basis_pct = (basis / spot_price).quantize(Decimal("0.0001"))

        # Annualized yield: (basis / spot) * (365 / dte)
        annualized = (basis_pct * (Decimal("365") / Decimal(days_to_expiry))).quantize(Decimal("0.0001"))

        if basis > Decimal("0.001"):
            regime = TermStructureRegime.CONTANGO
        elif basis < Decimal("-0.001"):
            regime = TermStructureRegime.BACKWARDATION
        else:
            regime = TermStructureRegime.FLAT

        return FuturesBasisMetrics(
            symbol=symbol,
            spot_price=spot_price,
            futures_price=futures_price,
            days_to_expiry=days_to_expiry,
            basis=basis,
            basis_percentage=basis_pct,
            annualized_basis_yield=annualized,
            regime=regime,
        )
