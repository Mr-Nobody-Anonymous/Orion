"""Base contracts and data models for live market and macro data providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class LiveQuote:
    """Standardized real-time market quote."""

    symbol: str
    price: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: float
    market_cap: float
    timestamp: str
    provider_name: str
    is_live: bool = True
    currency: str = "USD"

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "change_pct": self.change_pct,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "market_cap": self.market_cap,
            "timestamp": self.timestamp,
            "provider_name": self.provider_name,
            "is_live": self.is_live,
            "currency": self.currency,
        }


@dataclass(frozen=True, slots=True)
class LiveCandleSeries:
    """Historical candle series for chart rendering and quantitative models."""

    symbol: str
    timeframe: str
    prices: tuple[float, ...]
    timestamps: tuple[str, ...]
    provider_name: str
    is_live: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "prices": list(self.prices),
            "timestamps": list(self.timestamps),
            "provider_name": self.provider_name,
            "is_live": self.is_live,
        }


@dataclass(frozen=True, slots=True)
class LiveMacroMetric:
    """Standardized macroeconomic metric (yields, inflation, employment)."""

    series_id: str
    name: str
    current_value: float
    prior_value: float
    unit: str
    last_updated: str
    provider_name: str
    is_live: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "name": self.name,
            "current_value": self.current_value,
            "prior_value": self.prior_value,
            "unit": self.unit,
            "last_updated": self.last_updated,
            "provider_name": self.provider_name,
            "is_live": self.is_live,
        }
