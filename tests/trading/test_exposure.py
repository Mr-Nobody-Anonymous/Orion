"""Tests for the market-value exposure calculation.

These tests confirm:

* ``compute_exposure`` is dimensionally correct (currency / currency).
* Positions with no current market quote are reported as zero with
  ``missing_count`` bumped; they do not raise.
* Zero positions contribute nothing.
* Long and short positions both contribute via ``abs(qty * price)``.
* Equity of zero produces total=0, not division-by-zero.
* The breakdown serialises to a dict for audit logs.

The regression test at the bottom reproduces the reviewer's claim:
the previous ``sum(abs(quantity)) / equity`` implementation would
have produced a different, dimensionally meaningless number than
the market-value calculation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from orion.data.contracts import Asset, AssetClass, MarketQuote
from orion.trading.exposure import (
    ExposureBreakdown,
    compute_exposure,
    exposure_from_broker,
)


def _asset(symbol: str = "AAA") -> Asset:
    return Asset(symbol=symbol, asset_class=AssetClass.EQUITY, currency="USD")


def _quote(asset: Asset, last: str) -> MarketQuote:
    from datetime import datetime, timezone

    return MarketQuote(
        asset=asset,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bid=Decimal(last) - Decimal("0.01"),
        ask=Decimal(last) + Decimal("0.01"),
        last=Decimal(last),
        volume=Decimal("100"),
    )


# --------------------------------------------------------------------------- shape


def test_exposure_total_uses_market_value_not_share_count() -> None:
    """Holding 100 shares at $50 should produce 5000/10000 = 0.5 exposure,
    not 100/10000 = 0.01 (the old share-count formula)."""
    a = _asset()
    positions = {a: Decimal("100")}
    quotes = {a: _quote(a, "50")}
    breakdown = compute_exposure(positions, quotes, Decimal("10000"))
    assert breakdown.total == Decimal("5000") / Decimal("10000")
    assert breakdown.abs_market_value == Decimal("5000")
    assert breakdown.quoted_count == 1
    assert breakdown.missing_count == 0


def test_exposure_zero_equity_returns_zero_total() -> None:
    a = _asset()
    positions = {a: Decimal("100")}
    quotes = {a: _quote(a, "50")}
    breakdown = compute_exposure(positions, quotes, Decimal("0"))
    assert breakdown.total == Decimal("0")
    # abs_market_value is still computed so the audit log can see
    # the "exposure undefined, equity=0" condition.
    assert breakdown.abs_market_value == Decimal("5000")


def test_exposure_long_and_short_both_use_abs() -> None:
    a = _asset("A")
    b = _asset("B")
    positions = {a: Decimal("100"), b: Decimal("-50")}
    quotes = {a: _quote(a, "10"), b: _quote(b, "20")}
    breakdown = compute_exposure(positions, quotes, Decimal("1000"))
    # Long: 100*10=1000, short: |-50|*20=1000, total 2000/1000=2.0
    assert breakdown.abs_market_value == Decimal("2000")
    assert breakdown.total == Decimal("2")


def test_exposure_zero_position_contributes_nothing() -> None:
    a = _asset()
    positions = {a: Decimal("0")}
    quotes = {a: _quote(a, "100")}
    breakdown = compute_exposure(positions, quotes, Decimal("1000"))
    assert breakdown.total == Decimal("0")
    assert breakdown.quoted_count == 0


def test_exposure_missing_quote_counted_as_zero() -> None:
    a = _asset()
    b = _asset("B")
    positions = {a: Decimal("10"), b: Decimal("20")}
    quotes = {a: _quote(a, "100")}  # b has no quote
    breakdown = compute_exposure(positions, quotes, Decimal("1000"))
    assert breakdown.missing_count == 1
    assert breakdown.quoted_count == 1
    # Only a contributes: 10*100=1000, total 1.0
    assert breakdown.total == Decimal("1")


def test_exposure_missing_quote_flag_propagates() -> None:
    a = _asset()
    positions = {a: Decimal("10")}
    quotes: dict[Asset, MarketQuote] = {}
    breakdown = compute_exposure(positions, quotes, Decimal("1000"))
    assert breakdown.has_missing_quotes is True
    assert breakdown.missing_count == 1
    assert breakdown.total == Decimal("0")


def test_exposure_no_positions_is_zero() -> None:
    breakdown = compute_exposure({}, {}, Decimal("1000"))
    assert breakdown.total == Decimal("0")
    assert breakdown.quoted_count == 0
    assert breakdown.missing_count == 0
    assert breakdown.abs_market_value == Decimal("0")


def test_exposure_rejects_negative_equity() -> None:
    with pytest.raises(ValueError, match="equity must be non-negative"):
        compute_exposure({}, {}, Decimal("-1"))


def test_exposure_breakdown_serialises_to_dict() -> None:
    a = _asset()
    positions = {a: Decimal("10")}
    quotes = {a: _quote(a, "100")}
    breakdown = compute_exposure(positions, quotes, Decimal("1000"))
    out = breakdown.as_dict()
    assert out["total"] == "1"
    assert out["abs_market_value"] == "1000"
    assert out["equity"] == "1000"
    assert out["quoted_count"] == 1
    assert out["missing_count"] == 0
    assert "AAA" in out["per_position"]


# --------------------------------------------------------------------------- broker convenience


def test_exposure_from_broker_collects_quotes() -> None:
    a = _asset()

    class FakeBroker:
        def __init__(self) -> None:
            self._positions = {a: Decimal("10")}
            self._quote = _quote(a, "100")

        def get_positions(self) -> dict[Asset, Decimal]:
            return self._positions

        def get_market_data(self, asset: Asset) -> MarketQuote:
            if asset.symbol == "AAA":
                return self._quote
            raise LookupError("no quote")

    broker = FakeBroker()
    breakdown = exposure_from_broker(broker, Decimal("1000"))
    assert breakdown.total == Decimal("1")
    assert breakdown.missing_count == 0


def test_exposure_from_broker_swallows_missing_quotes() -> None:
    a = _asset()

    class FakeBroker:
        def get_positions(self) -> dict[Asset, Decimal]:
            return {a: Decimal("10")}

        def get_market_data(self, asset: Asset) -> MarketQuote:
            raise LookupError("not yet priced")

    breakdown = exposure_from_broker(FakeBroker(), Decimal("1000"))
    assert breakdown.total == Decimal("0")
    assert breakdown.missing_count == 1
    assert breakdown.has_missing_quotes is True


# --------------------------------------------------------------------------- regression: the previous bug


def test_old_share_count_formula_differs_from_market_value() -> None:
    """The previous orchestrator implementation used ``sum(abs(quantity)) /
    equity``. That is a *share count* divided by currency, which is
    dimensionally wrong: it can exceed 1.0 (over 100%) for a single
    position and is not comparable across instruments with different
    prices. The market-value implementation gives the same answer as
    a trader would compute by hand.
    """
    a = _asset()
    positions = {a: Decimal("100")}
    quotes = {a: _quote(a, "50")}
    equity = Decimal("10000")
    # Old (buggy) formula
    old_exposure = sum(abs(q) for q in positions.values()) / equity
    # New (correct) formula
    new_breakdown = compute_exposure(positions, quotes, equity)
    assert old_exposure == Decimal("100") / Decimal("10000")  # 0.01
    assert new_breakdown.total == Decimal("5000") / Decimal("10000")  # 0.5
    # The two are different by exactly the position's price (50x).
    assert new_breakdown.total == old_exposure * 50
