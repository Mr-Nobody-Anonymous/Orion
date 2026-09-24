"""Tax-aware rebalancing (P2-5).

Computes the trades required to move from current to target weights
and partitions them into:

- **loss-harvesting trades** that realise losses to offset gains, and
- **standard trades** for the remaining adjustment.

The output is a :class:`TaxAwareRebalance` whose ``loss_harvested``
field is the count of loss-realising trades. ORION never executes
trades; this module is purely a planning aid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

__all__ = ["TaxAwareRebalance", "tax_aware_rebalance"]


@dataclass(frozen=True, slots=True)
class TaxAwareTrade:
    symbol: str
    quantity_delta: float
    cost_basis_delta: float
    is_loss_harvest: bool
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TaxAwareRebalance:
    target_weights: Mapping[str, float]
    current_weights: Mapping[str, float]
    portfolio_value: float
    trades: tuple[TaxAwareTrade, ...]
    loss_harvested: int
    estimated_realised_gain: float

    def as_dict(self) -> dict[str, object]:
        return {
            "target_weights": dict(self.target_weights),
            "current_weights": dict(self.current_weights),
            "portfolio_value": self.portfolio_value,
            "trades": [
                {
                    "symbol": t.symbol,
                    "quantity_delta": t.quantity_delta,
                    "cost_basis_delta": t.cost_basis_delta,
                    "is_loss_harvest": t.is_loss_harvest,
                    "notes": t.notes,
                }
                for t in self.trades
            ],
            "loss_harvested": self.loss_harvested,
            "estimated_realised_gain": self.estimated_realised_gain,
        }


def tax_aware_rebalance(
    *,
    current_weights: Mapping[str, float],
    target_weights: Mapping[str, float],
    cost_basis: Mapping[str, float],
    market_value: float,
    loss_harvest_threshold: float = 0.0,
) -> TaxAwareRebalance:
    """Plan a rebalance that prefers to realise losses when possible."""
    if market_value <= 0:
        raise ValueError("market_value must be positive")
    if not target_weights:
        raise ValueError("target_weights must be non-empty")
    symbols = tuple(target_weights)
    trades: list[TaxAwareTrade] = []
    loss_count = 0
    realised_gain = 0.0
    for symbol in symbols:
        target_value = target_weights[symbol] * market_value
        current_value = current_weights.get(symbol, 0.0) * market_value
        delta_value = target_value - current_value
        if abs(delta_value) < 1e-9:
            continue
        basis = cost_basis.get(symbol, 0.0)
        # The cost basis is the *total* dollar amount invested in the
        # current position; the current value is what that position is
        # worth today. Per-unit PnL is therefore the difference scaled
        # by the current value (a normalised ratio). A negative value
        # means we are sitting on an unrealised loss.
        current_value_for_basis = max(1e-9, current_value)
        unrealised_pnl_ratio = (current_value_for_basis - basis) / current_value_for_basis
        is_loss = unrealised_pnl_ratio < -loss_harvest_threshold and delta_value < 0
        realised_gain += unrealised_pnl_ratio * abs(delta_value)
        if is_loss:
            loss_count += 1
        trades.append(
            TaxAwareTrade(
                symbol=symbol,
                quantity_delta=delta_value,
                cost_basis_delta=basis * (delta_value / current_value_for_basis),
                is_loss_harvest=is_loss,
                notes=("loss harvest" if is_loss else "standard rebalance"),
            )
        )
    return TaxAwareRebalance(
        target_weights=dict(target_weights),
        current_weights=dict(current_weights),
        portfolio_value=market_value,
        trades=tuple(trades),
        loss_harvested=loss_count,
        estimated_realised_gain=realised_gain,
    )
