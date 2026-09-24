"""Fundamental Valuation Engine.

Provides DCF, FCFF/FCFE, Dividend Discount Models, and Comparable Company Analysis (Comps).
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class DCFResult:
    enterprise_value: Decimal
    equity_value: Decimal
    implied_share_price: Decimal
    pv_projected_cash_flows: Decimal
    pv_terminal_value: Decimal
    wacc: Decimal
    terminal_growth_rate: Decimal
    shares_outstanding: Decimal


class ValuationEngine:
    """Institutional valuation models: DCF, DDM, Comps multiples."""

    @staticmethod
    def dcf(
        projected_fcf: Sequence[Decimal],
        wacc: Decimal,
        terminal_growth_rate: Decimal,
        net_debt: Decimal,
        shares_outstanding: Decimal,
    ) -> DCFResult:
        """Calculates Discounted Cash Flow valuation using perpetuity growth method."""
        if wacc <= terminal_growth_rate:
            raise ValueError(f"WACC ({wacc}) must be strictly greater than terminal growth rate ({terminal_growth_rate})")
        if shares_outstanding <= 0:
            raise ValueError(f"Shares outstanding ({shares_outstanding}) must be positive")

        pv_cash_flows = Decimal("0")
        for t, fcf in enumerate(projected_fcf, start=1):
            discount_factor = (Decimal("1") + wacc) ** Decimal(t)
            pv_cash_flows += fcf / discount_factor

        final_fcf = projected_fcf[-1] if projected_fcf else Decimal("0")
        terminal_fcf = final_fcf * (Decimal("1") + terminal_growth_rate)
        terminal_value = terminal_fcf / (wacc - terminal_growth_rate)
        final_discount = (Decimal("1") + wacc) ** Decimal(len(projected_fcf))
        pv_terminal = terminal_value / final_discount

        enterprise_value = pv_cash_flows + pv_terminal
        equity_value = enterprise_value - net_debt
        implied_share_price = equity_value / shares_outstanding

        return DCFResult(
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            implied_share_price=implied_share_price,
            pv_projected_cash_flows=pv_cash_flows,
            pv_terminal_value=pv_terminal,
            wacc=wacc,
            terminal_growth_rate=terminal_growth_rate,
            shares_outstanding=shares_outstanding,
        )

    @staticmethod
    def ddm_gordon_growth(
        next_dividend: Decimal,
        cost_of_equity: Decimal,
        dividend_growth_rate: Decimal,
    ) -> Decimal:
        """Gordon Growth Dividend Discount Model: P0 = D1 / (r - g)."""
        if cost_of_equity <= dividend_growth_rate:
            raise ValueError("Cost of equity must be strictly greater than dividend growth rate")
        return next_dividend / (cost_of_equity - dividend_growth_rate)

    @staticmethod
    def comparable_multiples(
        target_metrics: Mapping[str, Decimal],
        peer_multiples: Mapping[str, Sequence[Decimal]],
    ) -> dict[str, dict[str, Decimal]]:
        """Calculates implied valuations based on median peer multiples (EV/EBITDA, P/E, P/B, FCF Yield)."""
        results: dict[str, dict[str, Decimal]] = {}
        for multiple_name, peers in peer_multiples.items():
            if not peers:
                continue
            sorted_peers = sorted(peers)
            mid = len(sorted_peers) // 2
            median_val = sorted_peers[mid] if len(sorted_peers) % 2 != 0 else (sorted_peers[mid - 1] + sorted_peers[mid]) / Decimal("2")
            target_metric = target_metrics.get(multiple_name, Decimal("0"))

            implied_val = target_metric * median_val
            results[multiple_name] = {
                "peer_median": median_val,
                "target_metric": target_metric,
                "implied_valuation": implied_val,
            }
        return results
