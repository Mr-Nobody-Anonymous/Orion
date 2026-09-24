"""Deterministic portfolio construction and position sizing.

ORION's allocation layer is deliberately simple, transparent, and
asset-class agnostic: every rule here is a pure function of inputs so the
risk engine and audit trail can reproduce any allocation decision exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from ...data.contracts import Asset

__all__ = [
    "Allocation",
    "equal_weight",
    "inverse_volatility_weights",
    "kelly_weights",
    "apply_constraints",
    "target_position_sizes",
]


@dataclass(frozen=True, slots=True)
class Allocation:
    """A resolved weight vector with the reason it was produced."""

    weights: tuple[tuple[str, float], ...]
    method: str
    rationale: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "rationale": self.rationale,
            "weights": {name: round(w, 6) for name, w in self.weights},
        }


def _normalize(raw: Sequence[float]) -> tuple[float, ...]:
    total = sum(w for w in raw if w > 0)
    if total <= 0:
        n = len(raw)
        return tuple(1.0 / n for _ in range(n))
    return tuple(max(0.0, w) / total for w in raw)


def equal_weight(symbols: Sequence[str]) -> Allocation:
    """Uniform allocation across a non-empty symbol list."""
    if not symbols:
        raise ValueError("at least one symbol is required")
    w = 1.0 / len(symbols)
    return Allocation(
        weights=tuple((s, w) for s in symbols),
        method="equal_weight",
        rationale=f"uniform {len(symbols)}-asset allocation",
    )


def inverse_volatility_weights(vols: Mapping[str, float]) -> Allocation:
    """Low-volatility assets receive proportionally more capital.

    This is the classic risk-parity approximation: weight_i ∝ 1/vol_i.
    """
    if not vols:
        raise ValueError("at least one volatility estimate is required")
    if any(v <= 0 for v in vols.values()):
        raise ValueError("all volatility estimates must be positive")
    raw = [1.0 / vols[s] for s in vols]
    normalized = _normalize(raw)
    return Allocation(
        weights=tuple((s, w) for s, w in zip(vols, normalized)),
        method="inverse_volatility",
        rationale="capital allocated inversely to per-asset volatility",
    )


def kelly_weights(
    expected_returns: Mapping[str, float],
    vols: Mapping[str, float],
    fraction: float = 0.5,
) -> Allocation:
    """Fractional-Kelly allocation from expected returns and volatilities.

    Uses the single-asset Kelly approximation w_i ∝ mu_i / vol_i^2, scaled by
    `fraction` (half-Kelly by default) and capped so no single weight exceeds
    the conservative bound. Negative-edge assets get zero weight.
    """
    if not expected_returns:
        raise ValueError("at least one expected return is required")
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    raw: list[float] = []
    for s in expected_returns:
        vol = vols.get(s)
        if vol is None or vol <= 0:
            raise ValueError(f"missing or non-positive volatility for {s}")
        edge = expected_returns[s] / (vol * vol)
        raw.append(max(0.0, edge))
    normalized = _normalize(raw)
    scaled = [w * fraction for w in normalized]
    return Allocation(
        weights=tuple((s, w) for s, w in zip(expected_returns, scaled)),
        method=f"kelly_{fraction:g}",
        rationale="fractional Kelly from expected return over variance",
    )


def apply_constraints(
    allocation: Allocation,
    *,
    max_weight: float = 0.25,
    min_weight: float = 0.0,
) -> Allocation:
    """Cap and floor weights, then renormalize the surplus.

    Iterative redistribution: excess above `max_weight` is shared across
    assets still below the cap, so the result always sums to at most 1.
    """
    if not 0 <= min_weight <= max_weight <= 1:
        raise ValueError("require 0 <= min_weight <= max_weight <= 1")
    weights = {s: min(max(w, min_weight), max_weight) for s, w in allocation.weights}
    for _ in range(32):
        total = sum(weights.values())
        if total <= 1.0 + 1e-12:
            break
        excess = total - 1.0
        reducible = [s for s, w in weights.items() if w > max_weight]
        if not reducible:
            scale = 1.0 / total
            weights = {s: w * scale for s, w in weights.items()}
            break
        cut = excess / len(reducible)
        for s in reducible:
            weights[s] = max(weights[s] - cut, max_weight)
    return Allocation(
        weights=tuple(weights.items()),
        method=allocation.method + "+constrained",
        rationale=f"weights capped at {max_weight}, floored at {min_weight}",
    )


def target_position_sizes(
    allocation: Allocation,
    equity: Decimal,
    prices: Mapping[str, Decimal],
    *,
    lot: Decimal = Decimal("1"),
) -> dict[str, Decimal]:
    """Convert weights into whole-lot position sizes given current prices."""
    if equity <= 0:
        raise ValueError("equity must be positive")
    sizes: dict[str, Decimal] = {}
    for symbol, weight in allocation.weights:
        price = prices.get(symbol)
        if price is None or price <= 0:
            raise ValueError(f"missing or non-positive price for {symbol}")
        notional = equity * Decimal(str(weight))
        raw_units = notional / price
        sizes[symbol] = (raw_units // lot) * lot
    return sizes


def build_asset_universe(symbols: Sequence[str], asset_class: str = "equity") -> tuple[Asset, ...]:
    """Convenience constructor for a uniform asset-class universe."""
    from ...data.contracts import AssetClass

    cls = AssetClass(asset_class)
    return tuple(Asset(symbol=s, asset_class=cls) for s in symbols)
