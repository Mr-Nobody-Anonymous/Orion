"""Tests for the ORION storage layer (SQLite + Parquet/CSV)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orion.storage import ParquetStore, SqliteStore, TimeSeriesFrame
from orion.storage.parquet_store import new_version_id


# ----- SqliteStore ------------------------------------------------------


def test_sqlite_in_memory_round_trip() -> None:
    store = SqliteStore(":memory:")
    rid = store.insert("decisions", {"asset": "AAPL", "action": "BUY", "qty": 10.0})
    assert rid
    rows = store.query("decisions")
    assert len(rows) == 1
    record = rows[0]
    assert record.id == rid
    assert record.data["asset"] == "AAPL"
    assert record.data["action"] == "BUY"
    assert record.version_id  # always present
    assert record.created_at


def test_sqlite_query_with_where() -> None:
    store = SqliteStore(":memory:")
    store.insert("decisions", {"asset": "AAPL", "action": "BUY"})
    store.insert("decisions", {"asset": "MSFT", "action": "SELL"})
    rows = store.query("decisions", where={"asset": "AAPL"})
    assert len(rows) == 1
    assert rows[0].data["asset"] == "AAPL"


def test_sqlite_query_with_limit() -> None:
    store = SqliteStore(":memory:")
    for i in range(5):
        store.insert("predictions", {"asset": f"SYM{i}", "model": "ridge", "expected": 0.01, "confidence": 0.5})
    rows = store.query("predictions", limit=3)
    assert len(rows) == 3


def test_sqlite_count() -> None:
    store = SqliteStore(":memory:")
    assert store.count("decisions") == 0
    store.insert("decisions", {"asset": "AAPL", "action": "BUY"})
    assert store.count("decisions") == 1


def test_sqlite_rejects_unknown_table() -> None:
    store = SqliteStore(":memory:")
    with pytest.raises(ValueError):
        store.insert("bogus", {"x": 1})
    with pytest.raises(ValueError):
        store.query("bogus")
    with pytest.raises(ValueError):
        store.count("bogus")


def test_sqlite_version_id_override() -> None:
    store = SqliteStore(":memory:")
    store.insert("audit_events", {"event_type": "test", "actor": "pytest"}, version_id="v-fixed")
    [row] = store.query("audit_events")
    assert row.version_id == "v-fixed"


def test_sqlite_persists_to_file(tmp_path: Path) -> None:
    db_path = tmp_path / "orion.db"
    store = SqliteStore(db_path)
    store.insert("decisions", {"asset": "AAPL", "action": "BUY"})
    store.close()

    reopened = SqliteStore(db_path)
    assert reopened.count("decisions") == 1
    reopened.close()


# ----- ParquetStore (CSV back end is always available) -----------------


def _frame(symbol: str, version_id: str, n: int = 5) -> TimeSeriesFrame:
    columns = ("ts", "open", "high", "low", "close", "volume")
    rows = []
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        ts = base.replace(day=i + 1).isoformat()
        rows.append({
            "ts": ts,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000 * (i + 1),
        })
    return TimeSeriesFrame(symbol=symbol, version_id=version_id, columns=columns, rows=tuple(rows))


def test_parquet_csv_round_trip(tmp_path: Path) -> None:
    # Force CSV by passing prefer_parquet=False; this also tests
    # the fallback code path.
    store = ParquetStore(tmp_path, prefer_parquet=False)
    frame = _frame("AAPL", "v1")
    path = store.write_frame(frame)
    assert path.exists()
    assert path.suffix == ".csv"

    loaded = store.read_frame("AAPL", "v1")
    assert loaded is not None
    assert loaded.symbol == "AAPL"
    assert loaded.version_id == "v1"
    assert loaded.columns == frame.columns
    assert len(loaded.rows) == len(frame.rows)
    # CSV is a string protocol: every value is string-typed after
    # a round-trip.  Compare on string forms to validate the
    # back-end preserves the data faithfully.
    for got, want in zip(loaded.rows, frame.rows):
        for col in frame.columns:
            assert str(got[col]) == str(want[col])


def test_parquet_csv_lists_versions(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path, prefer_parquet=False)
    store.write_frame(_frame("AAPL", "v1"))
    store.write_frame(_frame("AAPL", "v2"))
    store.write_frame(_frame("MSFT", "v1"))
    assert set(store.list_versions("AAPL")) == {"v1", "v2"}
    assert set(store.list_versions("MSFT")) == {"v1"}


def test_parquet_csv_read_missing_returns_none(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path, prefer_parquet=False)
    assert store.read_frame("DOES_NOT_EXIST", "v1") is None


def test_parquet_csv_handles_nested_values(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path, prefer_parquet=False)
    frame = TimeSeriesFrame(
        symbol="AAPL",
        version_id="v1",
        columns=("ts", "features", "label"),
        rows=(
            {
                "ts": "2025-01-01",
                "features": {"momentum": 0.1, "volatility": 0.02},
                "label": "buy",
            },
        ),
    )
    path = store.write_frame(frame)
    assert path.exists()
    loaded = store.read_frame("AAPL", "v1")
    assert loaded is not None
    # The CSV back end stringifies nested values via JSON; verify
    # the round-trip survives the parse.
    [row] = loaded.rows
    assert json.loads(row["features"]) == {"momentum": 0.1, "volatility": 0.02}
    assert row["label"] == "buy"


@pytest.mark.skipif(
    ParquetStore(Path("/tmp")).has_parquet is False,
    reason="pyarrow not installed",
)
def test_parquet_preferred_when_available(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    if not store.using_parquet:
        pytest.skip("pyarrow not installed in this environment")
    frame = _frame("AAPL", "v1")
    path = store.write_frame(frame)
    assert path.suffix == ".parquet"
    loaded = store.read_frame("AAPL", "v1")
    assert loaded is not None
    assert len(loaded.rows) == len(frame.rows)


def test_new_version_id_is_unique() -> None:
    ids = {new_version_id() for _ in range(100)}
    assert len(ids) == 100
