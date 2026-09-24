"""Master Live Market Data Gateway for ORION.

Coordinates real-time market data across equities, crypto, macro, and prediction markets
with intelligent caching, rate-limit protection, and resilient zero-dependency fallback.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from .base import LiveCandleSeries, LiveQuote
from .coingecko import CoinGeckoLiveProvider
from .fred import FredLiveProvider
from .polymarket import PredictionMarketsLiveProvider
from .yahoo_finance import YahooFinanceLiveProvider


class LiveMarketDataGateway:
    """Singleton gateway coordinating all external live financial data feeds."""

    _instance: LiveMarketDataGateway | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.yahoo = YahooFinanceLiveProvider(timeout_seconds=4.0)
        self.coingecko = CoinGeckoLiveProvider(timeout_seconds=4.0)
        self.fred = FredLiveProvider(timeout_seconds=4.0)
        self.pm = PredictionMarketsLiveProvider(timeout_seconds=4.0)
        
        self._quotes_cache: dict[str, tuple[float, LiveQuote]] = {}
        self._series_cache: dict[str, tuple[float, LiveCandleSeries]] = {}
        self._cache_ttl_seconds = 15.0

    @classmethod
    def default(cls) -> LiveMarketDataGateway:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def get_quote(self, symbol: str) -> LiveQuote | None:
        """Get live quote with caching."""
        sym = symbol.upper().strip()
        now = time.time()
        with self._lock:
            if sym in self._quotes_cache:
                cached_time, cached_quote = self._quotes_cache[sym]
                if now - cached_time < self._cache_ttl_seconds:
                    return cached_quote

        # Crypto check
        if sym in ("BTC", "ETH", "SOL", "BTC/USD", "ETH/USD", "SOL/USD"):
            clean_sym = sym.split("/")[0]
            quotes = self.coingecko.fetch_crypto_quotes([clean_sym])
            if clean_sym in quotes:
                q = quotes[clean_sym]
                with self._lock:
                    self._quotes_cache[sym] = (now, q)
                return q

        # Equities / ETFs
        q, s = self.yahoo.fetch_quote_and_series(sym)
        if q is not None:
            with self._lock:
                self._quotes_cache[sym] = (now, q)
                if s is not None:
                    self._series_cache[sym] = (now, s)
            return q

        return None

    def get_series(self, symbol: str, range_str: str = "1mo") -> LiveCandleSeries | None:
        """Get candle series with caching."""
        sym = symbol.upper().strip()
        now = time.time()
        with self._lock:
            if sym in self._series_cache:
                cached_time, cached_series = self._series_cache[sym]
                if now - cached_time < self._cache_ttl_seconds:
                    return cached_series

        q, s = self.yahoo.fetch_quote_and_series(sym, range_str=range_str)
        if s is not None:
            with self._lock:
                self._series_cache[sym] = (now, s)
                if q is not None:
                    self._quotes_cache[sym] = (now, q)
            return s
        return None

    def get_live_prediction_events(self) -> list[dict[str, Any]]:
        """Fetch live prediction market contracts."""
        return self.pm.fetch_polymarket_events(limit=6)

    def get_live_treasury_yields(self) -> dict[str, float]:
        """Fetch live Treasury yields from FRED."""
        yields: dict[str, float] = {}
        for tenor, series_id in [("2Y", "DGS2"), ("10Y", "DGS10"), ("30Y", "DGS30"), ("3M", "DGS3MO")]:
            metric = self.fred.fetch_series(series_id)
            if metric is not None and metric.current_value > 0:
                yields[tenor] = metric.current_value
        return yields
