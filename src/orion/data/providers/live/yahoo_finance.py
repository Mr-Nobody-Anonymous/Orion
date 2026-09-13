"""Live Yahoo Finance market data provider.

Fetches real-time equity/ETF quotes, historical candle series, and company profiles
directly from Yahoo Finance public endpoints using stdlib urllib or optional yfinance.
Requires zero API keys.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .base import LiveCandleSeries, LiveQuote


class YahooFinanceLiveProvider:
    """Zero-key real-time equity, ETF, and index provider."""

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout = timeout_seconds

    def fetch_quote_and_series(
        self, symbol: str, range_str: str = "1mo", interval: str = "1d"
    ) -> tuple[LiveQuote | None, LiveCandleSeries | None]:
        """Fetch live quote and price series from Yahoo Finance."""
        sym = symbol.upper().replace("/", "-")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={range_str}"
        
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            result = data.get("chart", {}).get("result", [])[0]
            meta = result.get("meta", {})
            regular_price = float(meta.get("regularMarketPrice", 0.0))
            prev_close = float(meta.get("chartPreviousClose", regular_price) or regular_price)
            change_pct = round(((regular_price - prev_close) / prev_close) * 100.0, 2) if prev_close else 0.0

            indicators = result.get("indicators", {}).get("quote", [])[0]
            closes_raw = indicators.get("close", [])
            closes = [float(c) for c in closes_raw if c is not None]
            
            timestamps_raw = result.get("timestamp", [])
            timestamps = [
                datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                for ts in timestamps_raw
            ][:len(closes)]

            quote = LiveQuote(
                symbol=sym,
                price=regular_price,
                change_pct=change_pct,
                open=float(meta.get("regularMarketDayLow", regular_price)),
                high=float(meta.get("regularMarketDayHigh", regular_price)),
                low=float(meta.get("regularMarketDayLow", regular_price)),
                volume=float(meta.get("regularMarketVolume", 0.0)),
                market_cap=float(meta.get("marketCap", 0.0)),
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                provider_name="Yahoo Finance (Live)",
                is_live=True,
                currency=meta.get("currency", "USD"),
            )
            series = LiveCandleSeries(
                symbol=sym,
                timeframe=interval,
                prices=tuple(closes),
                timestamps=tuple(timestamps),
                provider_name="Yahoo Finance (Live)",
                is_live=True,
            )
            return quote, series
        except Exception:
            # Graceful offline / fallback return
            return None, None
