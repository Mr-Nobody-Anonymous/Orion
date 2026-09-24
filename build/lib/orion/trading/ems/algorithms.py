"""Execution Management System (EMS) and Algorithmic Trading.

Provides TWAP, VWAP, POV, Iceberg, Smart Order Routing (SOR), and Transaction Cost Analysis (TCA).
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence

from ...data.contracts import Action, Asset, Order


@dataclass(frozen=True, slots=True)
class ChildOrderSlice:
    slice_index: int
    quantity: Decimal
    target_time_offset_seconds: int
    order_type: str = "limit"
    limit_price: Decimal | None = None


class AlgorithmicExecutionEngine:
    """Slices parent orders into optimal child order schedules."""

    @staticmethod
    def twap(
        parent_quantity: Decimal,
        total_duration_seconds: int,
        num_slices: int,
    ) -> list[ChildOrderSlice]:
        if num_slices <= 0:
            raise ValueError("num_slices must be at least 1")
        if parent_quantity <= 0:
            return []

        base_qty = (parent_quantity / Decimal(num_slices)).quantize(Decimal("0.0001"))
        interval = total_duration_seconds // num_slices
        slices: list[ChildOrderSlice] = []
        allocated = Decimal("0")

        for i in range(num_slices):
            qty = base_qty if i < num_slices - 1 else parent_quantity - allocated
            allocated += qty
            slices.append(ChildOrderSlice(
                slice_index=i + 1,
                quantity=qty,
                target_time_offset_seconds=i * interval,
            ))
        return slices

    @staticmethod
    def vwap(
        parent_quantity: Decimal,
        volume_curve_weights: Sequence[Decimal],  # Hourly or interval percentage weights summing to ~1.0
        interval_seconds: int = 300,
    ) -> list[ChildOrderSlice]:
        if not volume_curve_weights:
            raise ValueError("volume_curve_weights cannot be empty")
        total_weight = sum(volume_curve_weights)
        if total_weight <= 0:
            raise ValueError("Total volume weights must be positive")

        slices: list[ChildOrderSlice] = []
        allocated = Decimal("0")
        n = len(volume_curve_weights)

        for i, w in enumerate(volume_curve_weights):
            if i == n - 1:
                qty = parent_quantity - allocated
            else:
                qty = (parent_quantity * (w / total_weight)).quantize(Decimal("0.0001"))
            allocated += qty
            slices.append(ChildOrderSlice(
                slice_index=i + 1,
                quantity=qty,
                target_time_offset_seconds=i * interval_seconds,
            ))
        return slices

    @staticmethod
    def calculate_pov_slice(
        remaining_quantity: Decimal,
        recent_market_volume: Decimal,
        target_participation_rate: Decimal = Decimal("0.10"),  # 10% of volume
    ) -> Decimal:
        """Determines next child order size targeting a constant Percentage of Volume (POV)."""
        target_qty = (recent_market_volume * target_participation_rate).quantize(Decimal("0.0001"))
        return min(remaining_quantity, max(Decimal("0"), target_qty))


@dataclass(frozen=True, slots=True)
class VenueQuote:
    venue_id: str
    bid: Decimal
    ask: Decimal
    bid_depth: Decimal
    ask_depth: Decimal
    taker_fee_bps: Decimal = Decimal("10")


class SmartOrderRouter:
    """Routes child orders across multi-venue liquidity pools to minimize all-in execution cost."""

    @staticmethod
    def route(
        side: Action,
        quantity: Decimal,
        venue_quotes: Sequence[VenueQuote],
    ) -> dict[str, Decimal]:
        """Splits quantity across venues prioritizing price and available depth."""
        if not venue_quotes or quantity <= 0:
            return {}

        allocations: dict[str, Decimal] = {}
        rem = quantity

        # For BUY: sort venues by lowest effective ask (ask price + taker fee)
        # For SELL: sort venues by highest effective bid (bid price - taker fee)
        if side in (Action.BUY, Action.SHORT):
            sorted_venues = sorted(
                venue_quotes,
                key=lambda v: v.ask * (Decimal("1") + v.taker_fee_bps / Decimal("10000")),
            )
            for v in sorted_venues:
                if rem <= 0:
                    break
                fillable = min(rem, v.ask_depth)
                if fillable > 0:
                    allocations[v.venue_id] = fillable
                    rem -= fillable
        else:
            sorted_venues = sorted(
                venue_quotes,
                key=lambda v: v.bid * (Decimal("1") - v.taker_fee_bps / Decimal("10000")),
                reverse=True,
            )
            for v in sorted_venues:
                if rem <= 0:
                    break
                fillable = min(rem, v.bid_depth)
                if fillable > 0:
                    allocations[v.venue_id] = fillable
                    rem -= fillable

        # If residual quantity remains due to insufficient depth, assign remainder to top venue
        if rem > 0 and sorted_venues:
            top = sorted_venues[0].venue_id
            allocations[top] = allocations.get(top, Decimal("0")) + rem

        return allocations


@dataclass(frozen=True, slots=True)
class TCAReport:
    arrival_price: Decimal
    execution_avg_price: Decimal
    market_vwap: Decimal
    arrival_slippage_bps: Decimal
    vwap_slippage_bps: Decimal
    total_fees: Decimal
    implementation_shortfall: Decimal


class TransactionCostAnalyzer:
    """Calculates post-trade execution benchmarks and slippage decomposition."""

    @staticmethod
    def analyze(
        side: Action,
        total_quantity: Decimal,
        arrival_price: Decimal,
        execution_avg_price: Decimal,
        market_vwap: Decimal,
        total_fees: Decimal = Decimal("0"),
    ) -> TCAReport:
        sign = Decimal("1") if side in (Action.BUY, Action.SHORT) else Decimal("-1")
        # Arrival slippage: (P_exec - P_arrival) / P_arrival * 10000 (signed)
        arrival_diff = (execution_avg_price - arrival_price) * sign
        arr_slip_bps = (arrival_diff / arrival_price * Decimal("10000")).quantize(Decimal("0.01")) if arrival_price > 0 else Decimal("0")

        # VWAP slippage: (P_exec - VWAP) / VWAP * 10000 (signed)
        vwap_diff = (execution_avg_price - market_vwap) * sign
        vwap_slip_bps = (vwap_diff / market_vwap * Decimal("10000")).quantize(Decimal("0.01")) if market_vwap > 0 else Decimal("0")

        # Implementation Shortfall in dollars = (P_exec - P_arrival) * Q + fees
        implementation_shortfall = (arrival_diff * total_quantity) + total_fees

        return TCAReport(
            arrival_price=arrival_price,
            execution_avg_price=execution_avg_price,
            market_vwap=market_vwap,
            arrival_slippage_bps=arr_slip_bps,
            vwap_slippage_bps=vwap_slip_bps,
            total_fees=total_fees,
            implementation_shortfall=implementation_shortfall,
        )
