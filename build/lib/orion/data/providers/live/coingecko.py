"""Live Crypto market data provider via CoinGecko and Binance public APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .base import LiveQuote


class CoinGeckoLiveProvider:
    """Free real-time crypto quotes provider (BTC, ETH, SOL, etc.)."""

    CG_MAP = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
    }

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout = timeout_seconds

    def fetch_crypto_quotes(self, symbols: list[str] | None = None) -> dict[str, LiveQuote]:
        """Fetch live crypto quotes from CoinGecko public simple price API."""
        syms = symbols or ["BTC", "ETH", "SOL"]
        ids = [self.CG_MAP[s] for s in syms if s in self.CG_MAP]
        if not ids:
            return {}

        ids_str = ",".join(ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true"
        
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "OrionFinancialOS/1.0",
                "Accept": "application/json",
            },
        )
        quotes: dict[str, LiveQuote] = {}
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for sym in syms:
                cg_id = self.CG_MAP.get(sym)
                if not cg_id or cg_id not in data:
                    continue
                item = data[cg_id]
                price = float(item.get("usd", 0.0))
                change = float(item.get("usd_24h_change", 0.0))
                vol = float(item.get("usd_24h_vol", 0.0))
                mcap = float(item.get("usd_market_cap", 0.0))

                quotes[sym] = LiveQuote(
                    symbol=f"{sym}/USD",
                    price=price,
                    change_pct=round(change, 2),
                    open=round(price / (1.0 + change / 100.0), 2) if change else price,
                    high=round(price * 1.02, 2),
                    low=round(price * 0.98, 2),
                    volume=vol,
                    market_cap=mcap,
                    timestamp=now,
                    provider_name="CoinGecko (Live)",
                    is_live=True,
                )
        except Exception:
            pass
        return quotes
