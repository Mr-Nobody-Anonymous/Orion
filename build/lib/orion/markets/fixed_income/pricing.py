"""Fixed Income Pricing, Duration, Convexity, and Credit Spread Analytics.

Bond pricing, Macaulay/Modified duration, DV01, convexity, yield curve discount factors,
and CDS implied default probability modeling.
Strictly in the Truth plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class BondMetrics:
    clean_price: Decimal
    macaulay_duration: Decimal
    modified_duration: Decimal
    dv01: Decimal  # Dollar Value of an 01 (price move per 1 bp change)
    convexity: Decimal
    yield_to_maturity: Decimal


@dataclass(frozen=True, slots=True)
class CDSSpreadMetrics:
    spread_bps: Decimal
    recovery_rate: Decimal  # e.g., 0.40 (40%)
    hazard_rate: Decimal  # Implied annual default intensity lambda
    survival_prob_1y: Decimal
    survival_prob_5y: Decimal


class FixedIncomeEngine:
    """Institutional bond pricing and term structure analytics."""

    @staticmethod
    def price_coupon_bond(
        par_value: Decimal,
        annual_coupon_rate: Decimal,
        ytm: Decimal,
        years_to_maturity: Decimal,
        frequency: int = 2,  # Semiannual by default
    ) -> BondMetrics:
        if par_value <= 0 or ytm <= 0 or years_to_maturity <= 0 or frequency <= 0:
            raise ValueError("Par, YTM, maturity, and frequency must be strictly positive")

        n_periods = int(years_to_maturity * frequency)
        period_rate = ytm / Decimal(frequency)
        coupon_payment = (par_value * annual_coupon_rate) / Decimal(frequency)

        pv_coupons = Decimal("0")
        weighted_pv_time = Decimal("0")
        convexity_sum = Decimal("0")

        for t in range(1, n_periods + 1):
            t_dec = Decimal(t)
            discount = (Decimal("1") + period_rate) ** t_dec
            pv_cf = coupon_payment / discount
            if t == n_periods:
                pv_cf += par_value / discount

            pv_coupons += pv_cf
            weighted_pv_time += (t_dec / Decimal(frequency)) * pv_cf
            convexity_sum += (t_dec * (t_dec + Decimal("1")) / (Decimal(frequency) ** 2)) * pv_cf

        clean_price = pv_coupons
        macaulay_dur = weighted_pv_time / clean_price
        modified_dur = macaulay_dur / (Decimal("1") + period_rate)
        dv01 = (clean_price * modified_dur * Decimal("0.0001")).quantize(Decimal("0.0001"))
        convexity = (convexity_sum / (clean_price * ((Decimal("1") + period_rate) ** 2))).quantize(Decimal("0.0001"))

        return BondMetrics(
            clean_price=clean_price.quantize(Decimal("0.01")),
            macaulay_duration=macaulay_dur.quantize(Decimal("0.001")),
            modified_duration=modified_dur.quantize(Decimal("0.001")),
            dv01=dv01,
            convexity=convexity,
            yield_to_maturity=ytm,
        )

    @staticmethod
    def calculate_cds_metrics(
        spread_bps: Decimal,
        recovery_rate: Decimal = Decimal("0.40"),  # 40% standard senior unsecured recovery
    ) -> CDSSpreadMetrics:
        if recovery_rate >= 1 or recovery_rate < 0:
            raise ValueError("Recovery rate must be in [0, 1)")

        # Standard approximation: s = lambda * (1 - R) -> lambda = s / (1 - R)
        spread_decimal = spread_bps / Decimal("10000")
        hazard_rate = spread_decimal / (Decimal("1") - recovery_rate)

        # Survival probability: S(t) = exp(-lambda * t)
        h_float = float(hazard_rate)
        s1 = Decimal(str(round(math.exp(-h_float * 1.0), 6)))
        s5 = Decimal(str(round(math.exp(-h_float * 5.0), 6)))

        return CDSSpreadMetrics(
            spread_bps=spread_bps,
            recovery_rate=recovery_rate,
            hazard_rate=hazard_rate.quantize(Decimal("0.0001")),
            survival_prob_1y=s1,
            survival_prob_5y=s5,
        )
