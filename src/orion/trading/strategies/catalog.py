"""Strategy implementations that produce trade proposals.

Strategies are pure functions over market data. They never place orders
directly; the executive brain routes proposals through the deterministic
risk gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from ..data.contracts import Action, Asset, Order, TradeProposal


@dataclass(frozen=True, slots=True)
class StrategyContext:
    asset: Asset
    prices: tuple[float, ...]
    equity: Decimal
    exposure: Decimal


def momentum_strategy(context: StrategyContext, *, lookback: int = 5) -> TradeProposal:
    """Trend-following strategy: buy when recent momentum is positive."""
    if len(context.prices) <= lookback or context.prices[-1] <= 0 or context.prices[-1 - lookback] <= 0:
        raise ValueError("not enough history for momentum strategy")
    change = context.prices[-1] / context.prices[-1 - lookback] - 1
    side = Action.BUY if change > 0 else Action.SELL
    return TradeProposal(
        order=Order(
            asset=context.asset,
            quantity=Decimal("1"),
            side=side,
        ),
        rationale=f"momentum: {change:.4f}",
    )


def mean_reversion_strategy(context: StrategyContext, *, window: int = 20) -> TradeProposal:
    """Mean-reversion strategy: buy when below the rolling mean, sell when above."""
    if len(context.prices) < 3 or context.prices[-1] <= 0:
        raise ValueError("not enough history for mean-reversion strategy")
    window = min(window, len(context.prices))
    rolling_mean = sum(context.prices[-window:]) / window
    diff = (context.prices[-1] - rolling_mean) / context.prices[-1]
    side = Action.BUY if diff < 0 else Action.SELL
    return TradeProposal(
        order=Order(asset=context.asset, quantity=Decimal("1"), side=side),
        rationale=f"mean-reversion deviation={diff:.4f}",
    )


def volatility_breakout_strategy(context: StrategyContext, *, lookback: int = 10, k: float = 1.5) -> TradeProposal:
    """Volatility breakout strategy: long on upper-band break, short on lower-band break."""
    if len(context.prices) < lookback or context.prices[-1] <= 0:
        raise ValueError("not enough history for volatility breakout")
    window = context.prices[-lookback:]
    mean = sum(window) / len(window)
    variance = sum((p - mean) ** 2 for p in window) / len(window)
    sd = variance ** 0.5
    upper = mean + k * sd
    lower = mean - k * sd
    last = context.prices[-1]
    if last > upper:
        side = Action.BUY
        rationale = f"volatility breakout: last {last} > upper {upper:.4f}"
    elif last < lower:
        side = Action.SELL
        rationale = f"volatility breakout: last {last} < lower {lower:.4f}"
    else:
        side = Action.HOLD
        rationale = "volatility breakout: within band"
    return TradeProposal(
        order=Order(asset=context.asset, quantity=Decimal("1"), side=side),
        rationale=rationale,
    )


def equal_weight_rebalance(
    assets: Sequence[Asset], current_quantities: dict[Asset, Decimal], target_value: Decimal, price_lookup
) -> list[Order]:
    """Produce a list of orders to rebalance to equal-weight."""
    if not assets or target_value <= 0:
        raise ValueError("assets and positive target_value are required")
    per_asset = target_value / Decimal(len(assets))
    orders: list[Order] = []
    for asset in assets:
        price = Decimal(str(price_lookup(asset)))
        if price <= 0:
            continue
        target_qty = (per_asset / price).quantize(Decimal("0.0001"))
        current_qty = current_quantities.get(asset, Decimal("0"))
        delta = target_qty - current_qty
        if delta == 0:
            continue
        side = Action.BUY if delta > 0 else Action.SELL
        orders.append(Order(asset=asset, quantity=abs(delta), side=side))
    return orders


def risk_parity_weights(returns_by_asset: dict[str, Sequence[float]]) -> dict[str, float]:
    """Compute inverse-volatility weights as a simple risk-parity approximation."""
    weights: dict[str, float] = {}
    variances: dict[str, float] = {}
    for key, returns in returns_by_asset.items():
        if len(returns) < 2:
            variances[key] = float("inf")
            continue
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        variances[key] = var
    inv = {k: 1.0 / (v if v > 0 else 1e-9) for k, v in variances.items()}
    total = sum(inv.values()) or 1.0
    return {k: v / total for k, v in inv.items()}
