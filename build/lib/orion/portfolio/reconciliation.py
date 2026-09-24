"""Automated Multi-Venue Position and Cash Reconciliation.

Reconciles internal double-entry ledger positions and cash balances against
external broker/exchange statements, detecting breaks and discrepancies.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Sequence

from ..data.contracts import Asset


@dataclass(frozen=True, slots=True)
class ReconciliationBreak:
    item_type: str  # "POSITION" or "CASH"
    identifier: str  # symbol or "CASH_USD"
    internal_value: Decimal
    broker_value: Decimal
    discrepancy: Decimal
    severity: str  # "WARNING" or "CRITICAL"


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    venue: str
    timestamp: datetime
    is_clean: bool
    breaks: tuple[ReconciliationBreak, ...]
    matched_positions_count: int
    matched_cash_accounts_count: int


class ReconciliationEngine:
    """Automated end-of-day / real-time reconciliation engine."""

    @staticmethod
    def reconcile(
        venue: str,
        internal_positions: Mapping[str, Decimal],  # symbol -> qty
        broker_positions: Mapping[str, Decimal],  # symbol -> qty
        internal_cash: Decimal,
        broker_cash: Decimal,
        position_tolerance: Decimal = Decimal("0.0001"),
        cash_tolerance: Decimal = Decimal("0.01"),
    ) -> ReconciliationReport:
        breaks: list[ReconciliationBreak] = []
        matched_positions = 0
        matched_cash = 0

        # 1. Cash reconciliation
        cash_diff = abs(internal_cash - broker_cash)
        if cash_diff > cash_tolerance:
            breaks.append(ReconciliationBreak(
                item_type="CASH",
                identifier="CASH_BALANCE",
                internal_value=internal_cash,
                broker_value=broker_cash,
                discrepancy=broker_cash - internal_cash,
                severity="CRITICAL" if cash_diff > Decimal("10.00") else "WARNING",
            ))
        else:
            matched_cash = 1

        # 2. Position reconciliation
        all_symbols = set(internal_positions.keys()) | set(broker_positions.keys())
        for sym in sorted(all_symbols):
            int_qty = internal_positions.get(sym, Decimal("0"))
            brk_qty = broker_positions.get(sym, Decimal("0"))
            diff = abs(int_qty - brk_qty)
            if diff > position_tolerance:
                breaks.append(ReconciliationBreak(
                    item_type="POSITION",
                    identifier=sym,
                    internal_value=int_qty,
                    broker_value=brk_qty,
                    discrepancy=brk_qty - int_qty,
                    severity="CRITICAL" if diff >= Decimal("1.0") else "WARNING",
                ))
            else:
                matched_positions += 1

        return ReconciliationReport(
            venue=venue,
            timestamp=datetime.now(timezone.utc),
            is_clean=len(breaks) == 0,
            breaks=tuple(breaks),
            matched_positions_count=matched_positions,
            matched_cash_accounts_count=matched_cash,
        )
