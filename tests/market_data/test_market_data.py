"""Tests for the point-in-time market-data layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from orion.data.market_data import (
    BadTickConfig,
    InMemoryMarketDataProvider,
    LineageRecord,
    LocalMarketDataStore,
    MissingDataPolicy,
    OHLCVRow,
    PITBundle,
    PITRecord,
    fill_gaps,
    filter_bad_ticks,
    make_version,
    to_utc,
)


# ----- PIT primitives ---------------------------------------------------

def test_pit_record_rejects_future_release() -> None:
    with pytest.raises(ValueError):
        PITRecord(
            value=1.0,
            observation_time=datetime(2025, 1, 5, tzinfo=timezone.utc),
            vendor_release_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )


def test_pit_bundle_as_of_returns_latest_admissible() -> None:
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = PITBundle.from_observations([
        (t0 + timedelta(days=0), 10.0, t0 + timedelta(days=1), "v1", "p"),
        (t0 + timedelta(days=1), 11.0, t0 + timedelta(days=2), "v1", "p"),
        (t0 + timedelta(days=2), 12.0, t0 + timedelta(days=3), "v1", "p"),
    ])
    # Asking "as of day 1.5" must return day 0's record (released at day 1)
    got = records.as_of(t0 + timedelta(days=1, hours=12))
    assert got is not None and got.value == 10.0
    # Asking "as of day 3" must return the most recent release
    got = records.as_of(t0 + timedelta(days=3))
    assert got is not None and got.value == 12.0
    # Asking before any release must return None
    assert records.as_of(t0 - timedelta(seconds=1)) is None


def test_pit_bundle_rejects_unsorted_records() -> None:
    with pytest.raises(ValueError):
        PITBundle((
            PITRecord(value=1.0, observation_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                       vendor_release_time=datetime(2025, 1, 2, tzinfo=timezone.utc)),
            PITRecord(value=0.0, observation_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                       vendor_release_time=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        ))


def test_pit_bundle_slice_for_window() -> None:
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = PITBundle.from_observations([
        (t0 + timedelta(days=d), float(d), t0 + timedelta(days=d), "v1", "p")
        for d in range(10)
    ])
    windowed = records.slice_for(t0 + timedelta(days=2), t0 + timedelta(days=5))
    assert [r.value for r in windowed.records] == [2.0, 3.0, 4.0, 5.0]


# ----- Normalization ----------------------------------------------------

def test_to_utc_makes_naive_aware() -> None:
    naive = datetime(2025, 1, 1, 12, 0, 0)
    assert to_utc(naive).tzinfo is not None


def test_filter_bad_ticks_rejects_spikes() -> None:
    rows = [
        (datetime(2025, 1, 1, tzinfo=timezone.utc), 100.0),
        (datetime(2025, 1, 2, tzinfo=timezone.utc), 101.0),
        (datetime(2025, 1, 3, tzinfo=timezone.utc), 102.0),
        (datetime(2025, 1, 4, tzinfo=timezone.utc), 50000.0),  # spike
        (datetime(2025, 1, 5, tzinfo=timezone.utc), 103.0),
        (datetime(2025, 1, 6, tzinfo=timezone.utc), 104.0),
    ]
    result = filter_bad_ticks(rows, config=BadTickConfig(max_price_jump_ratio=4.0))
    assert len(result.rejected) == 1
    assert result.rejected[0][1] == 50000.0
    assert len(result.cleaned) == 5


def test_filter_bad_ticks_rejects_non_positive() -> None:
    rows = [
        (datetime(2025, 1, 1, tzinfo=timezone.utc), 100.0),
        (datetime(2025, 1, 2, tzinfo=timezone.utc), 0.0),
        (datetime(2025, 1, 3, tzinfo=timezone.utc), 101.0),
    ]
    result = filter_bad_ticks(rows)
    assert any("non_positive_price" in r[2] for r in result.rejected)


def test_filter_bad_ticks_rejects_negative_volume() -> None:
    rows = [
        (datetime(2025, 1, 1, tzinfo=timezone.utc), 100.0),
        (datetime(2025, 1, 2, tzinfo=timezone.utc), 101.0),
    ]
    result = filter_bad_ticks(rows, volumes=[1000.0, -5.0])
    assert any("negative_volume" in r[2] for r in result.rejected)


def test_fill_gaps_forward_fill() -> None:
    rows = [
        (datetime(2025, 1, 1, tzinfo=timezone.utc), 10.0),
        (datetime(2025, 1, 2, tzinfo=timezone.utc), None),
        (datetime(2025, 1, 3, tzinfo=timezone.utc), 12.0),
    ]
    out = fill_gaps(rows, policy=MissingDataPolicy.FORWARD_FILL)
    assert [v for _, v in out] == [10.0, 10.0, 12.0]


def test_fill_gaps_drop() -> None:
    rows = [
        (datetime(2025, 1, 1, tzinfo=timezone.utc), 10.0),
        (datetime(2025, 1, 2, tzinfo=timezone.utc), None),
        (datetime(2025, 1, 3, tzinfo=timezone.utc), 12.0),
    ]
    out = fill_gaps(rows, policy=MissingDataPolicy.DROP)
    assert [v for _, v in out] == [10.0, 12.0]


# ----- Provider ---------------------------------------------------------

def test_in_memory_provider_status_and_ohlcv() -> None:
    p = InMemoryMarketDataProvider()
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = [OHLCVRow(t0 + timedelta(days=i), 100 + i, 101 + i, 99 + i, 100.5 + i, 1000.0) for i in range(5)]
    p.seed_ohlcv("AAPL", rows)
    out = p.fetch_ohlcv("AAPL", limit=3)
    assert len(out) == 3
    s = p.status()
    assert s["connected"] is True
    assert s["n_symbols_ohlcv"] == 1


def test_in_memory_provider_fundamentals_pit() -> None:
    p = InMemoryMarketDataProvider()
    t_obs = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t_rel = datetime(2025, 1, 5, tzinfo=timezone.utc)  # 4-day release lag
    p.seed_fundamental(
        "AAPL", t_obs, t_rel,
        FundamentalRow_pit(timestamp=t_obs, pe=20.0, pb=5.0, div=0.01, cap=2e12),
    )
    bundle = p.fetch_fundamentals("AAPL")
    # As of release time, the datum is available
    got = bundle.as_of(t_rel)
    assert got is not None
    # One day before release, the datum is NOT available
    assert bundle.as_of(t_rel - timedelta(days=1)) is None


# Helper: local re-export of the PIT field structure used by seed_fundamental
def FundamentalRow_pit(*, timestamp: datetime, pe: float, pb: float, div: float, cap: float):  # type: ignore[no-redef]
    from orion.data.market_data import FundamentalRow
    return FundamentalRow(timestamp=timestamp, pe_ratio=pe, pb_ratio=pb,
                            dividend_yield=div, market_cap=cap)


# ----- Versioning -------------------------------------------------------

def test_make_version_is_deterministic() -> None:
    rows = [{"x": 1}, {"x": 2}]
    v1 = make_version("ohlcv.v1", rows)
    v2 = make_version("ohlcv.v1", rows)
    assert v1.checksum == v2.checksum
    assert v1.n_rows == 2
    different = make_version("ohlcv.v1", [{"x": 1}, {"x": 3}])
    assert different.checksum != v1.checksum


def test_local_store_round_trip(tmp_path) -> None:
    from datetime import date as _date
    store = LocalMarketDataStore()
    lineage = LineageRecord(
        vendor="test", series_id="AAPL", vendor_release_time=datetime.now(timezone.utc),
        fetch_time=datetime.now(timezone.utc), sha256="x" * 64, n_obs=1,
    )
    store.put("AAPL", _date(2025, 1, 1), {"close": 100.0}, lineage=lineage)
    snap = store.snapshot(tmp_path)
    loaded = LocalMarketDataStore.from_snapshot(snap)
    assert loaded.get("AAPL", _date(2025, 1, 1)) == {"close": 100.0}
    assert loaded.lineage() == []
