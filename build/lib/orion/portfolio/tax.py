"""Tax Engine and Tax-Lot Accounting.

Implements FIFO, LIFO, HIFO lot relief methods, short-term vs. long-term capital gains,
and IRS 30-day wash sale rule tracking.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Sequence

from ..data.contracts import Asset, TaxLot


class TaxDisposalStrategy(str, Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    HIFO = "HIFO"  # Highest-In First-Out (tax minimisation)


@dataclass(frozen=True, slots=True)
class RealizedGainLossRecord:
    lot_id: str
    asset: Asset
    quantity: Decimal
    cost_basis_per_unit: Decimal
    sale_price_per_unit: Decimal
    realized_gain_loss: Decimal
    is_long_term: bool
    is_wash_sale: bool
    disallowed_loss: Decimal = Decimal("0")
    sale_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TaxLotManager:
    """Manages open tax lots, relief matching, and wash sale loss disallowance."""

    def __init__(self, strategy: TaxDisposalStrategy = TaxDisposalStrategy.FIFO) -> None:
        self.strategy = strategy
        self._open_lots: dict[str, list[TaxLot]] = {}  # symbol -> list of TaxLot
        self._closed_records: list[RealizedGainLossRecord] = []
        self._purchase_history: list[tuple[str, datetime, Decimal]] = []  # (symbol, ts, qty)

    def add_lot(self, asset: Asset, quantity: Decimal, cost_basis: Decimal, timestamp: datetime) -> TaxLot:
        if quantity <= 0 or cost_basis <= 0:
            raise ValueError("Quantity and cost basis must be positive")
        lot_id = f"lot_{asset.symbol}_{int(timestamp.timestamp())}_{len(self._open_lots.get(asset.symbol, [])) + 1}"
        lot = TaxLot(
            lot_id=lot_id,
            asset=asset,
            open_timestamp=timestamp,
            quantity=quantity,
            cost_basis=cost_basis,
            remaining_quantity=quantity,
        )
        self._open_lots.setdefault(asset.symbol, []).append(lot)
        self._purchase_history.append((asset.symbol, timestamp, quantity))
        return lot

    def match_sale(
        self,
        asset: Asset,
        quantity: Decimal,
        sale_price: Decimal,
        sale_timestamp: datetime,
    ) -> list[RealizedGainLossRecord]:
        if quantity <= 0 or sale_price <= 0:
            raise ValueError("Quantity and sale price must be positive")

        lots = self._open_lots.get(asset.symbol, [])
        if not lots:
            raise ValueError(f"No open lots available for {asset.symbol}")

        # Sort according to relief strategy
        if self.strategy == TaxDisposalStrategy.FIFO:
            active_lots = sorted(lots, key=lambda l: l.open_timestamp)
        elif self.strategy == TaxDisposalStrategy.LIFO:
            active_lots = sorted(lots, key=lambda l: l.open_timestamp, reverse=True)
        elif self.strategy == TaxDisposalStrategy.HIFO:
            active_lots = sorted(lots, key=lambda l: l.cost_basis, reverse=True)
        else:
            active_lots = sorted(lots, key=lambda l: l.open_timestamp)

        records: list[RealizedGainLossRecord] = []
        rem_qty = quantity
        updated_lots: list[TaxLot] = []

        for lot in active_lots:
            if rem_qty <= 0:
                updated_lots.append(lot)
                continue

            take_qty = min(rem_qty, lot.remaining_quantity)
            rem_qty -= take_qty
            new_remaining = lot.remaining_quantity - take_qty
            new_closed = lot.closed_quantity + take_qty

            gross_gain = (sale_price - lot.cost_basis) * take_qty
            holding_period_days = (sale_timestamp - lot.open_timestamp).days
            is_long_term = holding_period_days >= 365

            # Wash sale rule: if realized loss and replacement purchase within +/- 30 days
            is_wash = False
            disallowed = Decimal("0")
            if gross_gain < 0:
                wash_window_start = sale_timestamp - timedelta(days=30)
                wash_window_end = sale_timestamp + timedelta(days=30)
                # Check recent purchases within 30-day window (excluding this lot's open purchase)
                has_replacement = any(
                    p_sym == asset.symbol and wash_window_start <= p_ts <= wash_window_end and p_ts != lot.open_timestamp
                    for p_sym, p_ts, _ in self._purchase_history
                )
                if has_replacement:
                    is_wash = True
                    disallowed = abs(gross_gain)

            rec = RealizedGainLossRecord(
                lot_id=lot.lot_id,
                asset=asset,
                quantity=take_qty,
                cost_basis_per_unit=lot.cost_basis,
                sale_price_per_unit=sale_price,
                realized_gain_loss=gross_gain if not is_wash else Decimal("0"),
                is_long_term=is_long_term,
                is_wash_sale=is_wash,
                disallowed_loss=disallowed,
                sale_timestamp=sale_timestamp,
            )
            records.append(rec)
            self._closed_records.append(rec)

            if new_remaining > 0:
                updated_lots.append(TaxLot(
                    lot_id=lot.lot_id,
                    asset=lot.asset,
                    open_timestamp=lot.open_timestamp,
                    quantity=lot.quantity,
                    cost_basis=lot.cost_basis,
                    remaining_quantity=new_remaining,
                    closed_quantity=new_closed,
                    realized_gain=lot.realized_gain + (gross_gain if not is_wash else Decimal("0")),
                ))

        if rem_qty > 0:
            raise ValueError(f"Oversold: requested {quantity} but only {quantity - rem_qty} available in open lots")

        self._open_lots[asset.symbol] = updated_lots
        return records

    def get_realized_tax_summary(self) -> dict[str, Decimal]:
        st_gains = sum(r.realized_gain_loss for r in self._closed_records if not r.is_long_term and r.realized_gain_loss > 0)
        st_losses = sum(r.realized_gain_loss for r in self._closed_records if not r.is_long_term and r.realized_gain_loss < 0)
        lt_gains = sum(r.realized_gain_loss for r in self._closed_records if r.is_long_term and r.realized_gain_loss > 0)
        lt_losses = sum(r.realized_gain_loss for r in self._closed_records if r.is_long_term and r.realized_gain_loss < 0)
        wash_disallowed = sum(r.disallowed_loss for r in self._closed_records if r.is_wash_sale)

        return {
            "short_term_gains": st_gains,
            "short_term_losses": st_losses,
            "net_short_term": st_gains + st_losses,
            "long_term_gains": lt_gains,
            "long_term_losses": lt_losses,
            "net_long_term": lt_gains + lt_losses,
            "total_net_realized_pnl": st_gains + st_losses + lt_gains + lt_losses,
            "total_wash_sale_disallowed": wash_disallowed,
        }
