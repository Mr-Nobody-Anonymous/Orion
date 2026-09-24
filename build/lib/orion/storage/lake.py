"""Historical Market Data Lake for institutional multi-asset storage.

Provides partitioned, point-in-time queryable storage for high-frequency ticks,
multi-timeframe OHLCV bars, L2 order books, corporate fundamentals, macro series,
and news events.
Strictly in the Truth plane.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from ..data.contracts import (
    Asset,
    AssetClass,
    EconomicEvent,
    FundamentalData,
    NewsEvent,
    OHLCV,
    OrderBook,
    Tick,
)


@dataclass(frozen=True, slots=True)
class LakePartition:
    dataset_type: str  # "ticks", "bars", "order_books", "fundamentals", "macro", "news"
    venue: str
    asset_class: str
    symbol: str
    year: int
    month: int

    @property
    def relative_path(self) -> Path:
        return Path(self.dataset_type) / self.venue / self.asset_class / self.symbol / str(self.year) / f"{self.month:02d}.jsonl"


@dataclass(frozen=True, slots=True)
class LakeDatasetMetadata:
    symbol: str
    dataset_type: str
    venue: str
    total_records: int
    earliest_timestamp: datetime
    latest_timestamp: datetime
    partitions_count: int


class HistoricalDataLake:
    """Zero-dependency partitioned historical data lake with point-in-time query capabilities."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._catalog_file = self.root / "_catalog.json"
        self._catalog: dict[str, dict[str, Any]] = self._load_catalog()

    def _load_catalog(self) -> dict[str, dict[str, Any]]:
        if self._catalog_file.exists():
            try:
                return json.loads(self._catalog_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_catalog(self) -> None:
        self._catalog_file.write_text(json.dumps(self._catalog, indent=2, default=str), encoding="utf-8")

    def _to_partition(self, dataset_type: str, asset: Asset, ts: datetime) -> LakePartition:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return LakePartition(
            dataset_type=dataset_type,
            venue=asset.venue or "default",
            asset_class=asset.asset_class.value if isinstance(asset.asset_class, AssetClass) else str(asset.asset_class),
            symbol=asset.symbol.upper(),
            year=ts.year,
            month=ts.month,
        )

    # ------------------------------------------------------------------ Writers
    def write_ticks(self, asset: Asset, ticks: Sequence[Tick]) -> int:
        if not ticks:
            return 0
        written = 0
        by_partition: dict[LakePartition, list[dict[str, Any]]] = {}
        for t in ticks:
            part = self._to_partition("ticks", asset, t.timestamp)
            row = {
                "symbol": asset.symbol,
                "timestamp": t.timestamp.isoformat(),
                "price": str(t.price),
                "size": str(t.size),
                "source": t.source,
                "quality": t.quality,
            }
            by_partition.setdefault(part, []).append(row)

        for part, rows in by_partition.items():
            dest = self.root / part.relative_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
                    written += 1
            self._update_catalog_entry("ticks", asset, len(rows), ticks[0].timestamp, ticks[-1].timestamp)
        self._save_catalog()
        return written

    def write_bars(self, asset: Asset, timeframe: str, bars: Sequence[OHLCV]) -> int:
        if not bars:
            return 0
        written = 0
        dataset_name = f"bars_{timeframe}"
        by_partition: dict[LakePartition, list[dict[str, Any]]] = {}
        for b in bars:
            part = self._to_partition(dataset_name, asset, b.timestamp)
            row = {
                "symbol": asset.symbol,
                "timestamp": b.timestamp.isoformat(),
                "open": str(b.open),
                "high": str(b.high),
                "low": str(b.low),
                "close": str(b.close),
                "volume": str(b.volume),
                "source": b.source,
                "quality": b.quality,
            }
            by_partition.setdefault(part, []).append(row)

        for part, rows in by_partition.items():
            dest = self.root / part.relative_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
                    written += 1
            self._update_catalog_entry(dataset_name, asset, len(rows), bars[0].timestamp, bars[-1].timestamp)
        self._save_catalog()
        return written

    def write_macro(self, events: Sequence[EconomicEvent]) -> int:
        if not events:
            return 0
        dest = self.root / "macro" / "events.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as f:
            for e in events:
                row = {
                    "name": e.name,
                    "timestamp": e.timestamp.isoformat(),
                    "actual": str(e.actual) if e.actual is not None else None,
                    "forecast": str(e.forecast) if e.forecast is not None else None,
                    "previous": str(e.previous) if e.previous is not None else None,
                    "source": e.source,
                }
                f.write(json.dumps(row) + "\n")
        return len(events)

    def _update_catalog_entry(self, dataset_type: str, asset: Asset, count: int, start_ts: datetime, end_ts: datetime) -> None:
        key = f"{dataset_type}:{asset.symbol}"
        entry = self._catalog.setdefault(key, {
            "dataset_type": dataset_type,
            "symbol": asset.symbol,
            "venue": asset.venue or "default",
            "total_records": 0,
            "earliest_timestamp": start_ts.isoformat(),
            "latest_timestamp": end_ts.isoformat(),
        })
        entry["total_records"] += count
        if start_ts.isoformat() < entry["earliest_timestamp"]:
            entry["earliest_timestamp"] = start_ts.isoformat()
        if end_ts.isoformat() > entry["latest_timestamp"]:
            entry["latest_timestamp"] = end_ts.isoformat()

    # ------------------------------------------------------------------ Readers
    def read_bars(
        self,
        asset: Asset,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        as_of: datetime | None = None,
    ) -> list[OHLCV]:
        """Reads OHLCV bars strictly within [start, end] and strictly before or at as_of."""
        dataset_name = f"bars_{timeframe}"
        venue = asset.venue or "default"
        asset_class = asset.asset_class.value if isinstance(asset.asset_class, AssetClass) else str(asset.asset_class)
        symbol = asset.symbol.upper()

        symbol_dir = self.root / dataset_name / venue / asset_class / symbol
        if not symbol_dir.exists():
            return []

        bars: list[OHLCV] = []
        for file in symbol_dir.rglob("*.jsonl"):
            with file.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    ts = datetime.fromisoformat(r["timestamp"])
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if start and ts < start:
                        continue
                    if end and ts > end:
                        continue
                    if as_of and ts > as_of:
                        continue
                    bars.append(OHLCV(
                        asset=asset,
                        timestamp=ts,
                        open=Decimal(r["open"]),
                        high=Decimal(r["high"]),
                        low=Decimal(r["low"]),
                        close=Decimal(r["close"]),
                        volume=Decimal(r["volume"]),
                        source=r.get("source", "lake"),
                        quality=r.get("quality", "verified"),
                    ))
        bars.sort(key=lambda b: b.timestamp)
        return bars

    def get_catalog_metadata(self) -> dict[str, dict[str, Any]]:
        return dict(self._catalog)
