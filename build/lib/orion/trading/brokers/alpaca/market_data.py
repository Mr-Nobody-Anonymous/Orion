"""Alpaca market-data provider (paper endpoint only).

Uses ``alpaca_trade_api`` to fetch bars, snapshots, and quotes. The provider
refuses to construct against any non-paper endpoint; see
:class:`orion.trading.brokers.alpaca.config.AlpacaConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from ....data.contracts import Asset, AssetClass, MarketQuote, OHLCV
from .config import AlpacaConfig, is_paper_base_url


def _alpaca_available() -> bool:
    try:
        import alpaca_trade_api  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


@dataclass(frozen=True, slots=True)
class AlpacaMarketDataStatus:
    available: bool
    base_url: str
    paper: bool
    detail: str


class AlpacaMarketDataProvider:
    """Read-only market-data provider for the Alpaca paper endpoint."""

    def __init__(self, config: AlpacaConfig) -> None:
        if not _alpaca_available():
            self._api = None
        else:
            if not is_paper_base_url(config.base_url):
                raise ValueError("AlpacaMarketDataProvider only accepts the paper endpoint")
            import alpaca_trade_api as tradeapi  # type: ignore
            self._api = tradeapi.REST(config.api_key, config.secret_key,
                                       config.base_url, api_version="v2")
        self._config = config

    def status(self) -> AlpacaMarketDataStatus:
        if self._api is None:
            return AlpacaMarketDataStatus(False, self._config.base_url, True, "alpaca_trade_api unavailable")
        return AlpacaMarketDataStatus(True, self._config.base_url, True,
                                       f"paper endpoint {self._config.base_url!r} ready")

    def _to_ohlcv(self, asset: Asset, bar) -> OHLCV:
        ts = bar.t if hasattr(bar, "t") else None
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif isinstance(ts, datetime):
            timestamp = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        return OHLCV(
            asset=asset,
            timestamp=timestamp,
            open=float(bar.o),
            high=float(bar.h),
            low=float(bar.l),
            close=float(bar.c),
            volume=float(bar.v) if hasattr(bar, "v") and bar.v is not None else 0.0,
            source="alpaca",
            quality="exchange",
        )

    def fetch_bars(self, asset: Asset, *, timeframe: str = "1Day",
                    limit: int = 100) -> tuple[OHLCV, ...]:
        if self._api is None:
            raise RuntimeError("alpaca_trade_api is not installed in this environment")
        barset = self._api.get_bars(asset.symbol, timeframe, limit=limit,
                                       adjustment="raw").df
        if barset.empty:
            return ()
        return tuple(
            OHLCV(
                asset=asset,
                timestamp=(ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]) if "volume" in row else 0.0,
                source="alpaca",
                quality="exchange",
            )
            for ts, row in barset.iterrows()
        )

    def fetch_quote(self, asset: Asset) -> MarketQuote:
        if self._api is None:
            raise RuntimeError("alpaca_trade_api is not installed in this environment")
        snapshot = self._api.get_snapshot(asset.symbol)
        latest_trade = snapshot.latest_trade
        latest_quote = snapshot.latest_quote
        ts = latest_trade.t if hasattr(latest_trade, "t") and latest_trade.t else None
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif isinstance(ts, datetime):
            timestamp = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        return MarketQuote(
            asset=asset,
            timestamp=timestamp,
            bid=float(latest_quote.bp) if latest_quote and latest_quote.bp else 0.0,
            ask=float(latest_quote.ap) if latest_quote and latest_quote.ap else 0.0,
            last=float(latest_trade.p) if latest_trade else 0.0,
            volume=float(latest_trade.s) if latest_trade and latest_trade.s else 0.0,
            source="alpaca",
            quality="exchange",
        )
