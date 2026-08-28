"""Crypto market-data provider.

A thin adapter over the public ``ccxt`` interface. ORION only uses public
market-data endpoints — private trading endpoints are deliberately
unimplemented. The provider normalises every response into ORION's
canonical :class:`~orion.data.contracts.OHLCV` and
:class:`~orion.data.contracts.MarketQuote` contracts.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from ....data.contracts import Asset, AssetClass, MarketQuote, OHLCV


def _ccxt_available() -> bool:
    try:
        import ccxt  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


@dataclass(frozen=True, slots=True)
class CryptoProviderConfig:
    exchange_id: str = "binance"
    timeout_ms: int = 5000
    rate_limit_pause_seconds: float = 0.25
    default_quote_currency: str = "USDT"
    max_retries: int = 2

    def __post_init__(self) -> None:
        if self.timeout_ms < 100:
            raise ValueError("timeout_ms must be >= 100")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")


@dataclass(frozen=True, slots=True)
class CryptoProviderStatus:
    available: bool
    exchange_id: str
    detail: str


@dataclass(frozen=True, slots=True)
class SymbolMetadata:
    exchange: str
    symbol: str
    base: str
    quote: str
    active: bool
    info: dict[str, object] = field(default_factory=dict)


def _sanitize_price(value: float, fallback: float) -> float:
    if not math.isfinite(value) or value <= 0.0:
        return fallback if math.isfinite(fallback) and fallback > 0.0 else 0.0
    return value


def _sanitize_volume(value: float) -> float:
    if not math.isfinite(value) or value < 0.0:
        return 0.0
    return value


class CryptoMarketDataProvider:
    """Read-only market-data provider. **No private endpoints.**"""

    def __init__(self, config: CryptoProviderConfig | None = None) -> None:
        self.config = config or CryptoProviderConfig()
        if not _ccxt_available():
            self._exchange = None
        else:
            import ccxt  # type: ignore
            try:
                exchange_class = getattr(ccxt, self.config.exchange_id)
                self._exchange = exchange_class({"timeout": self.config.timeout_ms,
                                                   "enableRateLimit": True})
            except Exception:  # noqa: BLE001
                self._exchange = None

    def status(self) -> CryptoProviderStatus:
        if self._exchange is None:
            return CryptoProviderStatus(False, self.config.exchange_id, "ccxt unavailable")
        return CryptoProviderStatus(True, self.config.exchange_id,
                                       f"ccxt exchange {self.config.exchange_id!r} ready")

    def list_symbols(self) -> tuple[SymbolMetadata, ...]:
        if self._exchange is None:
            return ()
        markets = self._exchange.load_markets()
        return tuple(
            SymbolMetadata(
                exchange=self.config.exchange_id,
                symbol=key,
                base=info.get("base", ""),
                quote=info.get("quote", ""),
                active=bool(info.get("active", True)),
                info=dict(info),
            )
            for key, info in markets.items()
        )

    def _symbol_supported(self, asset: Asset) -> bool:
        if self._exchange is None:
            return False
        if not hasattr(self._exchange, "markets") or not self._exchange.markets:
            try:
                self._exchange.load_markets()
            except Exception:  # noqa: BLE001
                return False
        return self._format_symbol(asset) in self._exchange.markets

    @staticmethod
    def _format_symbol(asset: Asset) -> str:
        return f"{asset.symbol}/USDT"


    def fetch_ohlcv(self, asset: Asset, *, timeframe: str = "1d",
                      limit: int = 100) -> tuple[OHLCV, ...]:
        if self._exchange is None:
            raise RuntimeError("ccxt is not available in this environment")
        if not self._symbol_supported(asset):
            raise ValueError(f"asset {asset.symbol!r} is not in the {self.config.exchange_id} market catalogue")
        symbol = self._format_symbol(asset)
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                raw = self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(self.config.rate_limit_pause_seconds)
        else:
            raise RuntimeError(f"ccxt fetch_ohlcv failed after retries: {last_error}")
        return tuple(self._to_ohlcv(asset, candle) for candle in raw)

    def fetch_quote(self, asset: Asset) -> MarketQuote:
        if self._exchange is None:
            raise RuntimeError("ccxt is not available in this environment")
        if not self._symbol_supported(asset):
            raise ValueError(f"asset {asset.symbol!r} is not in the {self.config.exchange_id} market catalogue")
        symbol = self._format_symbol(asset)
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                ticker = self._exchange.fetch_ticker(symbol)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(self.config.rate_limit_pause_seconds)
        else:
            raise RuntimeError(f"ccxt fetch_ticker failed after retries: {last_error}")
        bid = float(ticker.get("bid") or 0.0)
        ask = float(ticker.get("ask") or 0.0)
        last = float(ticker.get("last") or 0.0)
        volume = float(ticker.get("baseVolume") or 0.0)
        timestamp = ticker.get("timestamp")
        ts = (datetime.fromtimestamp(timestamp / 1000.0, tz=timezone.utc)
               if timestamp else datetime.now(timezone.utc))
        return MarketQuote(
            asset=asset,
            timestamp=ts,
            bid=_sanitize_price(bid, last),
            ask=_sanitize_price(ask, last),
            last=_sanitize_price(last, last),
            volume=_sanitize_volume(volume),
            source=f"ccxt:{self.config.exchange_id}",
            quality="exchange",
        )

    @staticmethod
    def _to_ohlcv(asset: Asset, candle: Sequence[float]) -> OHLCV:
        timestamp = datetime.fromtimestamp(candle[0] / 1000.0, tz=timezone.utc)
        return OHLCV(
            asset=asset,
            timestamp=timestamp,
            open=float(candle[1]),
            high=float(candle[2]),
            low=float(candle[3]),
            close=float(candle[4]),
            volume=float(candle[5]) if len(candle) > 5 else 0.0,
            source="ccxt",
            quality="exchange",
        )

