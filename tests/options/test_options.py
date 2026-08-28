"""Tests for the options adapter."""

from __future__ import annotations

import math

import pytest

from orion.data.contracts import AssetClass
from orion.trading.options import (
    OptionAnalytics,
    OptionContract,
    OptionQuote,
    implied_volatility,
    price_and_greeks,
)


def _contract(is_call: bool = True, *, strike: float = 100.0, t: float = 0.5) -> OptionContract:
    return OptionContract(symbol="X100", underlying="X", strike=strike,
                           time_to_expiry=t, is_call=is_call, asset_class=AssetClass.OPTION)


def _quote(underlying_price: float = 100.0, *, r: float = 0.05, q: float = 0.0,
            market_price: float | None = None) -> OptionQuote:
    return OptionQuote(symbol="X100", underlying_price=underlying_price,
                        risk_free_rate=r, dividend_yield=q, market_price=market_price)


def test_call_price_is_at_least_intrinsic() -> None:
    a = price_and_greeks(_contract(strike=100, t=0.5), _quote(underlying_price=110), sigma=0.3)
    assert a.price >= 10.0  # intrinsic


def test_put_price_is_at_least_intrinsic() -> None:
    a = price_and_greeks(_contract(is_call=False, strike=100, t=0.5),
                          _quote(underlying_price=90), sigma=0.3)
    assert a.price >= 10.0


def test_delta_in_bounds() -> None:
    call = price_and_greeks(_contract(strike=100, t=0.5), _quote(100), sigma=0.3)
    put = price_and_greeks(_contract(is_call=False, strike=100, t=0.5),
                            _quote(100), sigma=0.3)
    assert 0.0 <= call.delta <= 1.0
    assert -1.0 <= put.delta <= 0.0


def test_gamma_is_non_negative() -> None:
    a = price_and_greeks(_contract(strike=100, t=0.5), _quote(100), sigma=0.3)
    assert a.gamma >= 0.0


def test_vega_is_non_negative() -> None:
    a = price_and_greeks(_contract(strike=100, t=0.5), _quote(100), sigma=0.3)
    assert a.vega >= 0.0


def test_theta_is_negative_for_long_options() -> None:
    a = price_and_greeks(_contract(strike=100, t=0.5), _quote(100), sigma=0.3)
    assert a.theta < 0.0


def test_implied_volatility_round_trips_price() -> None:
    contract = _contract(strike=100, t=0.5)
    quote = _quote(100, r=0.04)
    a = price_and_greeks(contract, quote, sigma=0.25)
    iv = implied_volatility(contract, OptionQuote(symbol="X100", underlying_price=100,
                                                     risk_free_rate=0.04, market_price=a.price))
    assert iv is not None
    assert abs(iv - 0.25) < 1e-3


def test_atm_call_iv_recovers_known_value() -> None:
    contract = _contract(strike=100, t=0.5, is_call=True)
    sigma = 0.20
    a = price_and_greeks(contract, _quote(100, r=0.04), sigma=sigma)
    iv = implied_volatility(contract, OptionQuote(symbol="X100", underlying_price=100,
                                                     risk_free_rate=0.04, market_price=a.price))
    assert iv is not None
    assert abs(iv - sigma) < 1e-3


def test_iv_none_when_no_market_price() -> None:
    assert implied_volatility(_contract(), _quote(100)) is None
    a = price_and_greeks(_contract(), _quote(100))
    assert a.implied_volatility is None


def test_degenerate_inputs_return_zero_greeks() -> None:
    a = price_and_greeks(_contract(t=0.0), _quote(100))
    assert a.gamma == 0.0 and a.vega == 0.0


def test_options_kind_helper() -> None:
    assert _contract(is_call=True).kind() == "call"
    assert _contract(is_call=False).kind() == "put"
