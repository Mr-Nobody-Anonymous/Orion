"""Event Study Analysis Engine.

Calculates Abnormal Returns (AR), Cumulative Abnormal Returns (CAR), and statistical
significance around corporate events (Earnings, FDA approvals, M&A, FOMC decisions).
Strictly in the Truth plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class EventStudyResult:
    event_id: str
    symbol: str
    alpha: float
    beta: float
    residual_variance: float
    abnormal_returns: tuple[float, ...]  # Daily AR in event window
    car: float  # Cumulative Abnormal Return over event window
    t_statistic: float
    p_value: float
    is_statistically_significant: bool  # p < 0.05


class EventStudyEngine:
    """Standard Campbell, Lo, MacKinlay (1997) event study methodology."""

    @staticmethod
    def run_event_study(
        event_id: str,
        symbol: str,
        estimation_asset_returns: Sequence[float],
        estimation_market_returns: Sequence[float],
        event_asset_returns: Sequence[float],
        event_market_returns: Sequence[float],
    ) -> EventStudyResult:
        if len(estimation_asset_returns) != len(estimation_market_returns):
            raise ValueError("Estimation returns must have identical lengths")
        if len(event_asset_returns) != len(event_market_returns):
            raise ValueError("Event window returns must have identical lengths")
        if len(estimation_asset_returns) < 20:
            raise ValueError("Estimation window must contain at least 20 periods")

        # 1. Estimate market model: R_i = alpha + beta * R_m
        n = len(estimation_market_returns)
        mean_m = sum(estimation_market_returns) / n
        mean_a = sum(estimation_asset_returns) / n

        var_m = sum((m - mean_m) ** 2 for m in estimation_market_returns) / (n - 1)
        cov_am = sum((a - mean_a) * (m - mean_m) for a, m in zip(estimation_asset_returns, estimation_market_returns)) / (n - 1)

        beta = cov_am / var_m if var_m > 0 else 1.0
        alpha = mean_a - beta * mean_m

        # Residual variance in estimation window
        residuals = [a - (alpha + beta * m) for a, m in zip(estimation_asset_returns, estimation_market_returns)]
        res_var = sum(r ** 2 for r in residuals) / max(1, (n - 2))

        # 2. Abnormal returns in event window
        ar_series: list[float] = []
        for a, m in zip(event_asset_returns, event_market_returns):
            expected = alpha + beta * m
            ar_series.append(a - expected)

        car = sum(ar_series)
        l2 = len(ar_series)
        var_car = res_var * l2
        se_car = math.sqrt(var_car) if var_car > 0 else 1e-6

        t_stat = car / se_car if se_car > 0 else 0.0

        # Normal CDF approximation for p-value
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat) / math.sqrt(2.0))))
        is_sig = p_val < 0.05

        return EventStudyResult(
            event_id=event_id,
            symbol=symbol,
            alpha=float(alpha),
            beta=float(beta),
            residual_variance=float(res_var),
            abnormal_returns=tuple(ar_series),
            car=float(car),
            t_statistic=float(t_stat),
            p_value=float(p_val),
            is_statistically_significant=is_sig,
        )
