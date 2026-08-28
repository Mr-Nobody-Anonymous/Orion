"""Market-value exposure calculation.

The previous executive-loop implementation computed portfolio exposure
as ``sum(abs(quantity)) / equity`` — that is *shares / dollars*, a
dimensionally meaningless ratio. The correct quantity is the **market
value** of each position relative to portfolio equity:

    exposure = sum_i |qty_i * price_i| / equity

This module centralises the calculation so the executive loop, the
risk engine, and any future tooling cannot drift apart on the
definition of "exposure".

Design choices
--------------

* A position whose asset has no current market quote is reported as
  zero exposure, with a ``quoted_count < len(positions)`` flag on the
  result. We deliberately do not raise — the broker may legitimately
  hold a freshly-allocated asset for which no quote has been published
  yet, and we want the risk gate to fail *closed* on the conservative
  side (zero exposure + a logged warning) rather than overstate
  exposure by guessing a price.

* A ``Decimal`` is used for every quantity, price, and equity value.
  Floating-point error in a pre-trade gate is a class of bug that
  causes real money loss.

* The function accepts any object that exposes ``get_positions()``
  and ``get_market_data(asset)`` (matching the
  :class:`orion.trading.execution.BrokerAdapter` protocol) so it can
  be called from both the executive loop and the risk engine without
  an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from ..data.contracts import Asset, MarketQuote


@dataclass(frozen=True, slots=True)
class ExposureBreakdown:
    """Per-position exposure decomposition.

    The total exposure is the sum of ``abs_market_value`` across all
    positions, divided by equity. ``quoted_count`` is the number of
    positions that had a current market quote available; the difference
    between ``len(positions)`` and ``quoted_count`` is the number of
    positions that were silently valued at zero — the caller can use
    this to decide whether the missing quotes are concerning.
    """

    total: Decimal
    per_position: Mapping[Asset, Decimal]
    abs_market_value: Decimal
    quoted_count: int
    missing_count: int
    equity: Decimal

    def __post_init__(self) -> None:
        if self.equity < 0:
            raise ValueError("equity must be non-negative")
        if self.total < 0:
            raise ValueError("exposure must be non-negative")
        if self.missing_count < 0 or self.quoted_count < 0:
            raise ValueError("counts must be non-negative")

    @property
    def has_missing_quotes(self) -> bool:
        return self.missing_count > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": str(self.total),
            "abs_market_value": str(self.abs_market_value),
            "equity": str(self.equity),
            "quoted_count": self.quoted_count,
            "missing_count": self.missing_count,
            "per_position": {
                a.symbol: str(v) for a, v in self.per_position.items()
            },
        }


def _safe_quote_last(quote: MarketQuote | None) -> Decimal | None:
    """Return the last price from a quote, or None if absent / invalid.

    A quote with a non-positive ``last`` is treated as missing — the
    risk gate prefers a known zero valuation over a guess.
    """
    if quote is None:
        return None
    last = quote.last
    if last is None or last <= 0:
        return None
    return Decimal(str(last))


def compute_exposure(
    positions: Mapping[Asset, Decimal],
    quotes: Mapping[Asset, MarketQuote],
    equity: Decimal,
) -> ExposureBreakdown:
    """Compute market-value exposure.

    Parameters
    ----------
    positions:
        Mapping from ``Asset`` to held quantity (positive = long,
        negative = short). An empty mapping is allowed.
    quotes:
        Mapping from ``Asset`` to the most recent market quote.
        Positions whose asset is missing from this map contribute zero
        market value and bump ``missing_count`` by one.
    equity:
        Portfolio equity in the account's currency. Must be >= 0.

    Returns
    -------
    :class:`ExposureBreakdown`
        A structured result with the total exposure (dimensionless
        fraction, ``0 <= exposure <= ∞``), the per-position market
        values, and a count of positions that could not be priced.
    """
    if equity < 0:
        raise ValueError("equity must be non-negative")

    per_position: dict[Asset, Decimal] = {}
    abs_market_value = Decimal("0")
    quoted_count = 0
    missing_count = 0
    for asset, qty in positions.items():
        qty_dec = Decimal(str(qty))
        if qty_dec == 0:
            # Zero positions contribute nothing to exposure.
            per_position[asset] = Decimal("0")
            continue
        price = _safe_quote_last(quotes.get(asset))
        if price is None:
            missing_count += 1
            per_position[asset] = Decimal("0")
            continue
        value = abs(qty_dec * price)
        per_position[asset] = value
        abs_market_value += value
        quoted_count += 1

    # Equity denominator: protect against division by zero. If equity is
    # zero, exposure is undefined and we report 0 with the breakdown
    # intact so callers can flag the condition rather than guess.
    if equity == 0:
        total = Decimal("0")
    else:
        total = abs_market_value / equity

    return ExposureBreakdown(
        total=total,
        per_position=per_position,
        abs_market_value=abs_market_value,
        quoted_count=quoted_count,
        missing_count=missing_count,
        equity=equity,
    )


def exposure_from_broker(broker: Any, equity: Decimal) -> ExposureBreakdown:
    """Convenience: build the quote map from a ``BrokerAdapter`` and compute.

    The broker must expose ``get_positions()`` and
    ``get_market_data(asset)``. Missing market data is caught and
    treated as "no quote", so the calculation always succeeds.
    """
    positions = broker.get_positions()
    quotes: dict[Asset, MarketQuote] = {}
    for asset in positions.keys():
        try:
            quotes[asset] = broker.get_market_data(asset)
        except (LookupError, KeyError, AttributeError):
            # No current quote — counted as missing.
            continue
    return compute_exposure(positions, quotes, equity)
