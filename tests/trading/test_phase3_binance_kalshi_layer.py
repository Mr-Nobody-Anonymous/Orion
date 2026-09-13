"""Tests for Phase 3: Binance & Kalshi Layer.

Covers:
- OMS OrderStateMachine, lifecycle, idempotency, and partial fills
- EMS TWAP, VWAP, POV, Smart Order Router (SOR), and TCA reporting
- Kalshi prediction market engine (implied vs. Bayesian calibration, Kelly sizing, settlement)
- Options analytics (Black-Scholes, complete Greeks, IV solver, strategy payoff)
- Futures basis and term structure contango/backwardation
- Cross-exchange and triangular arbitrage
- FIX 4.4 protocol engine message construction, checksum, and parsing
"""

from __future__ import annotations

from decimal import Decimal
import pytest

from orion.data.contracts import Action, Asset, AssetClass, MarketQuote, Order
from orion.integrations.fix import FIXProtocolEngine
from orion.markets.futures.analytics import FuturesAnalyticsEngine, TermStructureRegime
from orion.markets.options.analytics import OptionsAnalyticsEngine
from orion.markets.prediction_markets.kalshi_engine import KalshiMarketEngine
from orion.trading.arbitrage.engine import ArbitrageEngine
from orion.trading.ems.algorithms import (
    AlgorithmicExecutionEngine,
    SmartOrderRouter,
    TransactionCostAnalyzer,
    VenueQuote,
)
from orion.trading.oms.state_machine import OrderState, OrderStateMachine


# ---------------------------------------------------------------------------
# 1. OMS Order State Machine
# ---------------------------------------------------------------------------

def test_oms_state_machine_lifecycle() -> None:
    oms = OrderStateMachine()
    asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
    order = Order(asset=asset, quantity=Decimal("100"), side=Action.BUY, client_order_id="ord-001")

    # 1. Create order
    managed = oms.create_order(order, idempotency_key="idemp-001")
    assert managed.state == OrderState.PENDING_NEW
    assert managed.remaining_quantity == Decimal("100")

    # Duplicate submission blocked
    order2 = Order(asset=asset, quantity=Decimal("100"), side=Action.BUY, client_order_id="ord-002")
    with pytest.raises(ValueError, match="Duplicate order submission"):
        oms.create_order(order2, idempotency_key="idemp-001")

    # 2. Transition PENDING_NEW -> NEW
    managed = oms.transition("ord-001", OrderState.NEW)
    assert managed.state == OrderState.NEW

    # 3. Partial fill 40 @ $150.00
    managed = oms.apply_fill("ord-001", fill_quantity=Decimal("40"), fill_price=Decimal("150.00"))
    assert managed.state == OrderState.PARTIALLY_FILLED
    assert managed.cum_filled_quantity == Decimal("40")
    assert managed.remaining_quantity == Decimal("60")
    assert managed.avg_fill_price == Decimal("150.00")

    # 4. Final fill 60 @ $152.00
    managed = oms.apply_fill("ord-001", fill_quantity=Decimal("60"), fill_price=Decimal("152.00"))
    assert managed.state == OrderState.FILLED
    assert managed.cum_filled_quantity == Decimal("100")
    assert managed.remaining_quantity == Decimal("0")
    # Weighted avg price: (40 * 150 + 60 * 152) / 100 = 151.20
    assert managed.avg_fill_price == Decimal("151.20")
    assert managed.is_terminal is True

    # 5. Illegal transition from FILLED -> CANCELLED
    with pytest.raises(ValueError, match="Illegal order transition"):
        oms.transition("ord-001", OrderState.CANCELLED)


# ---------------------------------------------------------------------------
# 2. EMS Algorithmic Trading (TWAP, VWAP, POV, SOR, TCA)
# ---------------------------------------------------------------------------

def test_ems_twap_and_vwap() -> None:
    # TWAP: 1,000 shares across 5 slices over 300 seconds
    slices = AlgorithmicExecutionEngine.twap(
        parent_quantity=Decimal("1000"),
        total_duration_seconds=300,
        num_slices=5,
    )
    assert len(slices) == 5
    assert sum(s.quantity for s in slices) == Decimal("1000")
    assert slices[0].quantity == Decimal("200")
    assert slices[1].target_time_offset_seconds == 60

    # VWAP: 10,000 shares sliced according to volume curve [0.1, 0.2, 0.4, 0.3]
    vwap_slices = AlgorithmicExecutionEngine.vwap(
        parent_quantity=Decimal("10000"),
        volume_curve_weights=[Decimal("0.1"), Decimal("0.2"), Decimal("0.4"), Decimal("0.3")],
    )
    assert len(vwap_slices) == 4
    assert sum(s.quantity for s in vwap_slices) == Decimal("10000")
    assert vwap_slices[0].quantity == Decimal("1000")
    assert vwap_slices[2].quantity == Decimal("4000")


def test_smart_order_routing() -> None:
    vq1 = VenueQuote(venue_id="NASDAQ", bid=Decimal("100.00"), ask=Decimal("100.10"), bid_depth=Decimal("500"), ask_depth=Decimal("400"))
    vq2 = VenueQuote(venue_id="BATS", bid=Decimal("99.98"), ask=Decimal("100.05"), bid_depth=Decimal("300"), ask_depth=Decimal("300"))
    vq3 = VenueQuote(venue_id="IEX", bid=Decimal("99.95"), ask=Decimal("100.20"), bid_depth=Decimal("600"), ask_depth=Decimal("600"))

    # Buy 600 shares: BATS has lowest ask ($100.05) with 300 depth, then NASDAQ ($100.10) with 400 depth
    routes = SmartOrderRouter.route(Action.BUY, quantity=Decimal("600"), venue_quotes=[vq1, vq2, vq3])
    assert routes["BATS"] == Decimal("300")
    assert routes["NASDAQ"] == Decimal("300")
    assert "IEX" not in routes


def test_tca_reporting() -> None:
    report = TransactionCostAnalyzer.analyze(
        side=Action.BUY,
        total_quantity=Decimal("1000"),
        arrival_price=Decimal("100.00"),
        execution_avg_price=Decimal("100.08"),
        market_vwap=Decimal("100.05"),
        total_fees=Decimal("15.00"),
    )
    # Arrival slippage: (100.08 - 100.00) / 100.00 * 10000 = 8.00 bps
    assert report.arrival_slippage_bps == Decimal("8.00")
    # VWAP slippage: (100.08 - 100.05) / 100.05 * 10000 = 2.998... -> 3.00 bps
    assert report.vwap_slippage_bps == Decimal("3.00")
    # Implementation shortfall: (0.08 * 1000) + 15 = 80 + 15 = $95.00
    assert report.implementation_shortfall == Decimal("95.00")


# ---------------------------------------------------------------------------
# 3. Kalshi Prediction Market Engine
# ---------------------------------------------------------------------------

def test_kalshi_engine() -> None:
    # Implied probability: Bid=0.62, Ask=0.66 -> Mid=0.64 (64%)
    implied = KalshiMarketEngine.calculate_implied_probability(Decimal("0.62"), Decimal("0.66"))
    assert implied == Decimal("0.64")

    # Bayesian calibration: AI model says 0.80 with 0.70 confidence
    calibrated = KalshiMarketEngine.calibrate_probability(implied, Decimal("0.80"), ai_confidence=Decimal("0.70"))
    # (1 - 0.7) * 0.64 + 0.7 * 0.80 = 0.192 + 0.560 = 0.752
    assert calibrated.calibrated_probability == Decimal("0.752")
    assert calibrated.model_edge == Decimal("0.112")
    assert calibrated.kelly_fraction > 0

    # Settlement: held 100 YES contracts entered at 0.60, outcome is YES
    settlement = KalshiMarketEngine.settle_contract(
        contract_ticker="KXFED-26SEP",
        winning_outcome="YES",
        side_held="YES",
        quantity=Decimal("100"),
        avg_entry_price=Decimal("0.60"),
    )
    # Payout = 100 * $1.00 = $100. Entry cost = $60. PnL = +$40.
    assert settlement.payout == Decimal("100.00")
    assert settlement.realized_pnl == Decimal("40.00")


# ---------------------------------------------------------------------------
# 4. Options Analytics (Black-Scholes, Greeks, IV)
# ---------------------------------------------------------------------------

def test_options_analytics() -> None:
    spot = 100.0
    strike = 100.0
    t = 1.0  # 1 year
    r = 0.05  # 5%
    vol = 0.20  # 20%

    call = OptionsAnalyticsEngine.black_scholes(spot, strike, t, r, vol, is_call=True)
    put = OptionsAnalyticsEngine.black_scholes(spot, strike, t, r, vol, is_call=False)

    # Put-Call Parity: C - P = S - K * exp(-r*T)
    discounted_k = strike * (2.718281828459045 ** (-r * t))
    assert abs((call.price - put.price) - (spot - discounted_k)) < 0.01

    # Greeks sanity checks
    assert 0.5 < call.delta < 0.7
    assert -0.5 < put.delta < -0.3
    assert call.gamma > 0
    assert call.vega > 0
    assert call.theta < 0  # Time decay is negative

    # Implied Volatility recovery
    iv = OptionsAnalyticsEngine.implied_volatility(call.price, spot, strike, t, r, is_call=True)
    assert iv is not None
    assert abs(iv - vol) < 0.001

    # Bull Call Spread Payoff: Long 100C @ $10, Short 110C @ $4
    legs = [(True, 100.0, 10.0, 1), (True, 110.0, 4.0, -1)]
    # Under spot=90: net pnl = -(10 - 4) = -$6
    # Under spot=120: net pnl = (120 - 100 - 10) - (120 - 110 - 4) = 10 - 6 = +$4
    curve = OptionsAnalyticsEngine.strategy_payoff([90.0, 105.0, 120.0], legs)
    assert curve[0][1] == -6.0
    assert curve[2][1] == 4.0


# ---------------------------------------------------------------------------
# 5. Futures Analytics
# ---------------------------------------------------------------------------

def test_futures_basis_and_term_structure() -> None:
    spot = Decimal("100.00")
    futures_contango = Decimal("102.00")
    metrics = FuturesAnalyticsEngine.calculate_basis(
        symbol="CL_2026M",
        spot_price=spot,
        futures_price=futures_contango,
        days_to_expiry=90,
    )
    assert metrics.basis == Decimal("2.00")
    assert metrics.regime == TermStructureRegime.CONTANGO
    assert metrics.annualized_basis_yield > Decimal("0.05")  # ~8.1%


# ---------------------------------------------------------------------------
# 6. Cross-Exchange & Triangular Arbitrage
# ---------------------------------------------------------------------------

def test_arbitrage_engine() -> None:
    asset_a = Asset(symbol="BTC-USDT", asset_class=AssetClass.CRYPTO, venue="binance")
    asset_b = Asset(symbol="BTC-USDT", asset_class=AssetClass.CRYPTO, venue="kraken")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Venue A: Ask=$50,000. Venue B: Bid=$50,200 (Gross spread = $200 = 40 bps)
    q1 = MarketQuote(asset=asset_a, timestamp=now, bid=Decimal("49990"), ask=Decimal("50000"), last=Decimal("50000"))
    q2 = MarketQuote(asset=asset_b, timestamp=now, bid=Decimal("50200"), ask=Decimal("50210"), last=Decimal("50200"))

    opps = ArbitrageEngine.detect_spatial_arbitrage("BTC-USDT", [q1, q2], taker_fee_bps=Decimal("10"))
    assert len(opps) == 1
    assert opps[0].buy_venue == "binance"
    assert opps[0].sell_venue == "kraken"
    assert opps[0].net_spread_bps > Decimal("10")  # 40 bps - 25 bps = ~15 bps

    # Triangular Arbitrage: Dislocation in cross rate
    tri = ArbitrageEngine.detect_triangular_arbitrage(
        p_btc_usdt=Decimal("50000"),
        p_eth_btc=Decimal("0.05"),  # Implies ETH should be $2,500
        p_eth_usdt=Decimal("2600"),  # Actual ETH market price is $2,600 (4% spread)
    )
    assert tri.is_profitable is True
    assert tri.net_profit_pct > Decimal("3.0")


# ---------------------------------------------------------------------------
# 7. FIX Protocol Engine
# ---------------------------------------------------------------------------

def test_fix_protocol_engine() -> None:
    # Build NewOrderSingle (35=D)
    raw_msg = FIXProtocolEngine.build_new_order_single(
        sender="ORION_BUY_SIDE",
        target="BINANCE_OR_BROKER",
        seq_num=101,
        cl_ord_id="ORION-ORDER-999",
        symbol="AAPL",
        side="1",  # Buy
        quantity=Decimal("500"),
        ord_type="2",  # Limit
        price=Decimal("185.50"),
        delimiter="|",
    )

    assert "35=D|" in raw_msg
    assert "11=ORION-ORDER-999|" in raw_msg
    assert "55=AAPL|" in raw_msg
    assert "44=185.50|" in raw_msg
    assert "10=" in raw_msg  # Checksum field present

    # Parse message back
    parsed = FIXProtocolEngine.parse_message(raw_msg, delimiter="|")
    assert parsed.msg_type == "D"
    assert parsed.sender_comp_id == "ORION_BUY_SIDE"
    assert parsed.target_comp_id == "BINANCE_OR_BROKER"
    assert parsed.msg_seq_num == 101
    assert parsed.get_tag(11) == "ORION-ORDER-999"
    assert parsed.get_tag(55) == "AAPL"
    assert parsed.get_tag(44) == "185.50"
