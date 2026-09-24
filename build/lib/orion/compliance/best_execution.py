"""Best-execution reporting (P2-3).

Compares per-venue execution quality for a list of fills. A venue is
"best" on a per-fill basis if its slippage is lowest among the venues
that executed the same order; the report summarises slippage, fees,
and price improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class VenueExecution:
    venue: str
    order_id: str
    expected_price: float
    fill_price: float
    quantity: float
    fee: float

    @property
    def slippage(self) -> float:
        return self.fill_price - self.expected_price

    @property
    def total_cost(self) -> float:
        return self.slippage * self.quantity + self.fee

    def as_dict(self) -> dict[str, object]:
        return {
            "venue": self.venue,
            "order_id": self.order_id,
            "expected_price": self.expected_price,
            "fill_price": self.fill_price,
            "quantity": self.quantity,
            "fee": self.fee,
            "slippage": self.slippage,
            "total_cost": self.total_cost,
        }


@dataclass(frozen=True, slots=True)
class BestExecutionReport:
    executions: tuple[VenueExecution, ...]
    best_venue_by_order: Mapping[str, str]
    average_slippage: float
    average_total_cost: float

    def as_dict(self) -> dict[str, object]:
        return {
            "executions": [e.as_dict() for e in self.executions],
            "best_venue_by_order": dict(self.best_venue_by_order),
            "average_slippage": self.average_slippage,
            "average_total_cost": self.average_total_cost,
        }


def build_best_execution_report(
    executions: Sequence[VenueExecution],
) -> BestExecutionReport:
    if not executions:
        return BestExecutionReport(
            executions=(),
            best_venue_by_order={},
            average_slippage=0.0,
            average_total_cost=0.0,
        )
    by_order: dict[str, list[VenueExecution]] = {}
    for ex in executions:
        by_order.setdefault(ex.order_id, []).append(ex)
    best: dict[str, str] = {}
    for order_id, venues in by_order.items():
        chosen = min(venues, key=lambda e: e.total_cost)
        best[order_id] = chosen.venue
    avg_slip = sum(e.slippage for e in executions) / len(executions)
    avg_cost = sum(e.total_cost for e in executions) / len(executions)
    return BestExecutionReport(
        executions=tuple(executions),
        best_venue_by_order=best,
        average_slippage=avg_slip,
        average_total_cost=avg_cost,
    )
