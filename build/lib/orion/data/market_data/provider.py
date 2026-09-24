"""Provider protocol + a stdlib reference implementation.

A provider is anything that can answer:

  * ``fetch_ohlcv(asset, timeframe, limit)`` — historical OHLCV
  * ``fetch_fundamentals(asset)``             — point-in-time fundamentals
  * ``fetch_corporate_actions(asset)``        — splits & dividends
  * ``fetch_news(query)``                     — point-in-time news
  * ``status()``                              — connectivity

The reference :class:`InMemoryMarketDataProvider` is fully self-contained
and powers the test suite. Production providers (ccxt / alpaca / sec /
etc.) are layered on top without changing this protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Mapping, Protocol

from .lineage import LineageRecord
from .pit import PITBundle, PITRecord


@dataclass(frozen=True, slots=True)
class OHLCVRow:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class FundamentalRow:
    timestamp: datetime
    pe_ratio: float
    pb_ratio: float
    dividend_yield: float
    market_cap: float


@dataclass(frozen=True, slots=True)
class CorporateAction:
    timestamp: datetime
    kind: str  # "split" | "dividend"
    ratio: float  # 2.0 for 2:1 split; 0.02 for 2% dividend
    description: str = ""


@dataclass(frozen=True, slots=True)
class NewsItem:
    timestamp: datetime  # vendor release time, not the event time
    headline: str
    source: str
    url: str
    asset_symbol: str = ""


class MarketDataProvider(Protocol):
    def fetch_ohlcv(
        self, asset_symbol: str, *, timeframe: str = "1d", limit: int = 100
    ) -> tuple[OHLCVRow, ...]: ...

    def fetch_fundamentals(self, asset_symbol: str) -> PITBundle[FundamentalRow]: ...

    def fetch_corporate_actions(self, asset_symbol: str) -> PITBundle[CorporateAction]: ...

    def fetch_news(self, query: str) -> PITBundle[NewsItem]: ...

    def status(self) -> dict[str, object]: ...


@dataclass
class InMemoryMarketDataProvider:
    """Reference implementation backed by dicts; no I/O."""

    ohlcv: dict[str, list[OHLCVRow]] = field(default_factory=dict)
    fundamentals: dict[str, list[FundamentalRow]] = field(default_factory=dict)
    corporate_actions: dict[str, list[CorporateAction]] = field(default_factory=dict)
    news: list[NewsItem] = field(default_factory=list)
    vendor_name: str = "in-memory-reference"

    def seed_ohlcv(self, asset_symbol: str, rows: Iterable[OHLCVRow]) -> None:
        self.ohlcv.setdefault(asset_symbol, []).extend(sorted(rows, key=lambda r: r.timestamp))

    def seed_fundamental(
        self,
        asset_symbol: str,
        observation_time: datetime,
        vendor_release_time: datetime,
        row: FundamentalRow,
    ) -> None:
        rec = PITRecord(
            value=row,
            observation_time=observation_time,
            vendor_release_time=vendor_release_time,
            vendor=self.vendor_name,
            series_id=f"fund:{asset_symbol}",
        )
        self.fundamentals.setdefault(asset_symbol, []).append(rec)
        self.fundamentals[asset_symbol].sort(key=lambda r: r.vendor_release_time)

    def fetch_ohlcv(
        self, asset_symbol: str, *, timeframe: str = "1d", limit: int = 100
    ) -> tuple[OHLCVRow, ...]:
        rows = self.ohlcv.get(asset_symbol, [])
        return tuple(rows[-limit:])

    def fetch_fundamentals(self, asset_symbol: str) -> PITBundle[FundamentalRow]:
        return PITBundle(tuple(self.fundamentals.get(asset_symbol, [])))

    def fetch_corporate_actions(self, asset_symbol: str) -> PITBundle[CorporateAction]:
        return PITBundle(tuple(self.corporate_actions.get(asset_symbol, [])))

    def fetch_news(self, query: str) -> PITBundle[NewsItem]:
        q = query.lower()
        matches = [n for n in self.news if q in n.headline.lower() or q in n.asset_symbol.lower()]
        records = [
            PITRecord(
                value=n,
                observation_time=n.timestamp,
                vendor_release_time=n.timestamp,
                vendor=n.source,
                series_id=n.url,
            )
            for n in matches
        ]
        records.sort(key=lambda r: r.vendor_release_time)
        return PITBundle(tuple(records))

    def status(self) -> dict[str, object]:
        return {
            "vendor": self.vendor_name,
            "connected": True,
            "n_symbols_ohlcv": len(self.ohlcv),
            "n_symbols_fundamentals": len(self.fundamentals),
        }
