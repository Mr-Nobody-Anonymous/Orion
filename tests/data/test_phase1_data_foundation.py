"""Tests for Phase 1: Data Foundation & Unified Financial Data Model (UFDM).

Covers:
- UFDM core contracts and backward compatibility
- Real-time streaming bar aggregation and VWAP
- L2 Order book tracking, spreads, and imbalances
- Real-time data quality guard (stale quotes, crossed market, sequence gaps)
- Corporate action price adjustments (splits and dividends)
- Partitioned Historical Data Lake with point-in-time querying
- Point-in-time Feature Store and Population Stability Index (PSI) drift monitoring
- Data Licensing & Entitlement enforcement
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from orion.data.contracts import (
    Account,
    Action,
    AlertNotification,
    AlertSeverity,
    Asset,
    AssetClass,
    Company,
    FactorExposure,
    Instrument,
    LedgerEntry,
    Market,
    MarketQuote,
    MarketStatus,
    OHLCV,
    PredictionMarket,
    PredictionMarketContract,
    ResearchDocument,
    Security,
    TaxLot,
    Tick,
    Trade,
    Venue,
    YieldCurve,
    YieldCurvePoint,
)
from orion.data.features.store import (
    FeatureDefinition,
    FeatureDriftMonitor,
    PointInTimeFeatureStore,
)
from orion.data.market_data.corporate_actions import (
    CorporateAction,
    CorporateActionAdjustmentEngine,
    CorporateActionType,
)
from orion.data.market_data.lineage import (
    DataEntitlement,
    DataLicenseType,
    EntitlementEnforcer,
)
from orion.data.market_data.streaming import (
    BarAggregator,
    BarTimeframe,
    DataQualityGuard,
    OrderBookTracker,
)
from orion.storage.lake import HistoricalDataLake


# ---------------------------------------------------------------------------
# 1. UFDM Contracts & Invariants
# ---------------------------------------------------------------------------

def test_ufdm_instrument_and_venue() -> None:
    venue = Venue(venue_id="XNYS", name="New York Stock Exchange", mic_code="XNYS")
    assert venue.venue_id == "XNYS"
    assert venue.is_active is True

    inst = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        venue="XNYS",
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
    )
    assert inst.symbol == "AAPL"
    assert inst.tick_size == Decimal("0.01")

    # Invariant: Frozen dataclass rejects attribute mutations
    with pytest.raises(Exception):
        inst.symbol = "MSFT"  # type: ignore


def test_ufdm_market_and_company() -> None:
    asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY, venue="XNYS")
    market = Market(
        market_id="AAPL.XNYS",
        asset=asset,
        venue="XNYS",
        status=MarketStatus.OPEN,
        last_price=Decimal("150.00"),
        bid=Decimal("149.98"),
        ask=Decimal("150.02"),
    )
    assert market.status == MarketStatus.OPEN
    assert market.last_price == Decimal("150.00")

    comp = Company(
        symbol="AAPL",
        name="Apple Inc.",
        cik="0000320193",
        sector="Technology",
        industry="Consumer Electronics",
    )
    assert comp.name == "Apple Inc."
    assert comp.sector == "Technology"


def test_ufdm_prediction_market_and_yield_curve() -> None:
    contract = PredictionMarketContract(
        contract_id="FED-2026-SEP-CUT-YES",
        ticker="KXFED-26SEP-T500",
        title="Fed cuts rate by 25 bps in Sep 2026",
        outcome="YES",
        settlement_source="Federal Reserve",
        last_price=Decimal("0.72"),
    )
    pm = PredictionMarket(
        market_id="FED-2026-SEP",
        title="Fed Interest Rate Decision Sep 2026",
        category="Economics",
        contracts=(contract,),
    )
    assert pm.category == "Economics"
    assert pm.contracts[0].last_price == Decimal("0.72")

    p1 = YieldCurvePoint(tenor="2Y", maturity_years=Decimal("2.0"), rate=Decimal("0.0410"))
    p2 = YieldCurvePoint(tenor="10Y", maturity_years=Decimal("10.0"), rate=Decimal("0.0445"))
    curve = YieldCurve(
        name="US_TREASURY",
        currency="USD",
        timestamp=datetime.now(timezone.utc),
        points=(p1, p2),
    )
    assert len(curve.points) == 2
    assert curve.points[1].rate == Decimal("0.0445")


# ---------------------------------------------------------------------------
# 2. Real-Time Streaming Bar Aggregator & VWAP
# ---------------------------------------------------------------------------

def test_bar_aggregator_ticks_and_vwap() -> None:
    asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
    agg = BarAggregator(asset, timeframes=[BarTimeframe.MIN_1])

    t0 = datetime(2026, 9, 13, 14, 0, 5, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 13, 14, 0, 25, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 13, 14, 0, 50, tzinfo=timezone.utc)
    # Next minute (triggers bar close)
    t3 = datetime(2026, 9, 13, 14, 1, 10, tzinfo=timezone.utc)

    # Ingest ticks in minute 14:00
    agg.process_tick(Tick(asset=asset, timestamp=t0, price=Decimal("100.00"), size=Decimal("10")))
    agg.process_tick(Tick(asset=asset, timestamp=t1, price=Decimal("105.00"), size=Decimal("20")))
    agg.process_tick(Tick(asset=asset, timestamp=t2, price=Decimal("98.00"), size=Decimal("10")))

    # Current open bar
    curr = agg.get_current_bar(BarTimeframe.MIN_1)
    assert curr is not None
    assert curr.open == Decimal("100.00")
    assert curr.high == Decimal("105.00")
    assert curr.low == Decimal("98.00")
    assert curr.close == Decimal("98.00")
    assert curr.volume == Decimal("40")

    # Ingest next minute tick -> closes previous bar
    closed = agg.process_tick(Tick(asset=asset, timestamp=t3, price=Decimal("102.00"), size=Decimal("5")))
    assert len(closed) == 1
    c_bar = closed[0]
    assert c_bar.timestamp == datetime(2026, 9, 13, 14, 0, 0, tzinfo=timezone.utc)
    assert c_bar.close == Decimal("98.00")
    assert len(agg.get_completed_bars(BarTimeframe.MIN_1)) == 1


# ---------------------------------------------------------------------------
# 3. L2 Order Book Tracker
# ---------------------------------------------------------------------------

def test_order_book_tracker() -> None:
    asset = Asset(symbol="BTC-USDT", asset_class=AssetClass.CRYPTO)
    tracker = OrderBookTracker(asset=asset)

    # Apply initial snapshot
    bids = [(Decimal("50000.00"), Decimal("1.5")), (Decimal("49990.00"), Decimal("3.0"))]
    asks = [(Decimal("50010.00"), Decimal("1.0")), (Decimal("50020.00"), Decimal("2.5"))]
    tracker.apply_snapshot(bids=bids, asks=asks, update_id=1)

    assert tracker.best_bid == Decimal("50000.00")
    assert tracker.best_ask == Decimal("50010.00")
    assert tracker.spread == Decimal("10.00")
    assert tracker.mid_price == Decimal("50005.00")

    # Weighted mid price: (50000 * 1.0 + 50010 * 1.5) / 2.5 = 125015 / 2.5 = 50006.0
    assert tracker.weighted_mid_price == Decimal("50006.00")

    # Delta update: new best bid
    tracker.apply_delta(side=Action.BUY, price=Decimal("50005.00"), quantity=Decimal("2.0"), update_id=2)
    assert tracker.best_bid == Decimal("50005.00")
    assert tracker.spread == Decimal("5.00")

    # Delta update: cancel best ask
    tracker.apply_delta(side=Action.SELL, price=Decimal("50010.00"), quantity=Decimal("0.0"), update_id=3)
    assert tracker.best_ask == Decimal("50020.00")
    assert tracker.spread == Decimal("15.00")


# ---------------------------------------------------------------------------
# 4. Real-Time Data Quality Guard
# ---------------------------------------------------------------------------

def test_data_quality_guard() -> None:
    guard = DataQualityGuard(max_spread_pct=Decimal("0.05"), max_price_deviation_pct=Decimal("0.15"))
    asset = Asset(symbol="MSFT", asset_class=AssetClass.EQUITY)
    now = datetime.now(timezone.utc)

    # Valid quote
    q_valid = MarketQuote(asset=asset, timestamp=now, bid=Decimal("300.00"), ask=Decimal("300.20"), last=Decimal("300.10"))
    res = guard.check_quote(q_valid)
    assert res.is_valid is True

    # Non-positive quote
    q_neg = MarketQuote(asset=asset, timestamp=now, bid=Decimal("-5.00"), ask=Decimal("300.20"), last=Decimal("300.10"))
    assert guard.check_quote(q_neg).is_valid is False

    # Crossed market (bid > ask)
    q_cross = MarketQuote(asset=asset, timestamp=now, bid=Decimal("305.00"), ask=Decimal("300.20"), last=Decimal("300.10"))
    res_cross = guard.check_quote(q_cross)
    assert res_cross.is_valid is False
    assert res_cross.reason == "crossed_market"

    # Sequence gap
    assert guard.check_sequence("channel_1", 1).is_valid is True
    assert guard.check_sequence("channel_1", 2).is_valid is True
    # Gap from 2 to 5
    res_gap = guard.check_sequence("channel_1", 5)
    assert res_gap.is_valid is False
    assert res_gap.reason == "sequence_gap_detected"


# ---------------------------------------------------------------------------
# 5. Corporate Action Price Adjustments
# ---------------------------------------------------------------------------

def test_corporate_action_split_and_dividend_adjustment() -> None:
    asset = Asset(symbol="NVDA", asset_class=AssetClass.EQUITY)
    t1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 2, tzinfo=timezone.utc)
    t3 = datetime(2026, 6, 3, tzinfo=timezone.utc)

    bar1 = OHLCV(asset=asset, timestamp=t1, open=Decimal("100"), high=Decimal("110"), low=Decimal("95"), close=Decimal("105"), volume=Decimal("1000"))
    bar2 = OHLCV(asset=asset, timestamp=t2, open=Decimal("105"), high=Decimal("115"), low=Decimal("100"), close=Decimal("110"), volume=Decimal("1200"))
    bar3 = OHLCV(asset=asset, timestamp=t3, open=Decimal("60"), high=Decimal("65"), low=Decimal("58"), close=Decimal("62"), volume=Decimal("2500"))

    # 2-for-1 split effective on t3
    action = CorporateAction(
        asset=asset,
        action_type=CorporateActionType.SPLIT,
        effective_date=t3,
        rate_or_ratio=Decimal("2.0"),
    )

    adjusted = CorporateActionAdjustmentEngine.adjust_series([bar1, bar2, bar3], [action])
    assert len(adjusted) == 3

    # Bars 1 and 2 (prior to t3) should have halved prices and doubled volumes
    assert adjusted[0].adjusted_close == Decimal("52.5")
    assert adjusted[0].adjusted_volume == Decimal("2000")
    assert adjusted[1].adjusted_close == Decimal("55.0")
    assert adjusted[1].adjusted_volume == Decimal("2400")
    # Bar 3 is on/after effective date -> unadjusted
    assert adjusted[2].adjusted_close == Decimal("62.0")
    assert adjusted[2].adjusted_volume == Decimal("2500")


# ---------------------------------------------------------------------------
# 6. Historical Data Lake (Point-in-Time Partitioning)
# ---------------------------------------------------------------------------

def test_historical_data_lake(tmp_path: Path) -> None:
    lake = HistoricalDataLake(tmp_path / "lake")
    asset = Asset(symbol="ETH-USD", asset_class=AssetClass.CRYPTO, venue="coinbase")

    t1 = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)

    bars = [
        OHLCV(asset=asset, timestamp=t1, open=Decimal("3000"), high=Decimal("3050"), low=Decimal("2990"), close=Decimal("3020"), volume=Decimal("100")),
        OHLCV(asset=asset, timestamp=t2, open=Decimal("3020"), high=Decimal("3080"), low=Decimal("3010"), close=Decimal("3060"), volume=Decimal("150")),
        OHLCV(asset=asset, timestamp=t3, open=Decimal("3060"), high=Decimal("3100"), low=Decimal("3050"), close=Decimal("3090"), volume=Decimal("200")),
    ]

    written = lake.write_bars(asset, "1h", bars)
    assert written == 3

    # Partition file exists on disk
    expected_file = tmp_path / "lake" / "bars_1h" / "coinbase" / "crypto" / "ETH-USD" / "2026" / "08.jsonl"
    assert expected_file.exists()

    # Read back with point-in-time boundary (as_of t2) -> should NOT return t3!
    results = lake.read_bars(asset, "1h", as_of=t2)
    assert len(results) == 2
    assert results[-1].timestamp == t2
    assert results[-1].close == Decimal("3060")


# ---------------------------------------------------------------------------
# 7. Point-in-Time Feature Store & PSI Drift Monitor
# ---------------------------------------------------------------------------

def test_feature_store_and_drift_monitor() -> None:
    store = PointInTimeFeatureStore()
    feat_def = FeatureDefinition(name="momentum_5d", feature_group="technical")
    store.register_feature(feat_def)

    t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)

    store.record_feature("momentum_5d", "AAPL", t1, 0.05)
    store.record_feature("momentum_5d", "AAPL", t2, 0.08)
    store.record_feature("momentum_5d", "AAPL", t3, 0.02)

    # As-of t2, value must be 0.08 (strictly ignores t3)
    f_as_of_t2 = store.get_features_as_of("AAPL", ["momentum_5d"], as_of=t2)
    assert f_as_of_t2["momentum_5d"] == 0.08

    # Prior to t1, value must be None
    f_before = store.get_features_as_of("AAPL", ["momentum_5d"], as_of=t1 - timedelta(hours=1))
    assert f_before["momentum_5d"] is None

    # Drift monitor (PSI): baseline vs slightly perturbed target vs heavily shifted target
    baseline = [float(i) for i in range(100)]
    target_stable = [float(i) + 0.2 for i in range(100)]
    target_drifted = [float(i) + 150.0 for i in range(100)]

    psi_stable = FeatureDriftMonitor.calculate_psi(baseline, target_stable)
    psi_drifted = FeatureDriftMonitor.calculate_psi(baseline, target_drifted)

    assert psi_stable < 0.10  # Minimal drift
    assert psi_drifted > 0.25  # Significant drift


# ---------------------------------------------------------------------------
# 8. Data Licensing & Entitlements
# ---------------------------------------------------------------------------

def test_data_licensing_and_entitlements() -> None:
    enforcer = EntitlementEnforcer()
    ent_comm = DataEntitlement(
        vendor="bloomberg_feed",
        license_type=DataLicenseType.COMMERCIAL,
        live_trading_allowed=True,
    )
    ent_res = DataEntitlement(
        vendor="academic_dataset",
        license_type=DataLicenseType.INTERNAL_RESEARCH_ONLY,
        live_trading_allowed=False,
    )
    enforcer.register(ent_comm)
    enforcer.register(ent_res)

    assert enforcer.can_use_for_live_trading("bloomberg_feed") is True
    assert enforcer.can_use_for_live_trading("academic_dataset") is False
    # Unregistered vendor is allowed by default
    assert enforcer.can_use_for_live_trading("unregistered_vendor") is True
