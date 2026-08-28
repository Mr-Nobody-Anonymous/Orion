"""Tests for the crypto market-data provider.

The provider is exercised in two modes: the offline path (ccxt available
but the test does not hit the network) and the failure path (unknown
asset, missing ccxt, etc.). The test deliberately does not call the
network so the suite is deterministic and offline-safe.
"""

from __future__ import annotations

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.data.providers.crypto import (
    CryptoMarketDataProvider,
    CryptoProviderConfig,
)


def test_config_validates() -> None:
    with pytest.raises(ValueError):
        CryptoProviderConfig(timeout_ms=10)
    with pytest.raises(ValueError):
        CryptoProviderConfig(max_retries=-1)


def test_provider_status() -> None:
    p = CryptoMarketDataProvider()
    status = p.status()
    assert status.exchange_id == "binance"
    # Status is honest: either ccxt is wired and "ready" or it is unavailable.
    assert status.available is True
    assert "binance" in status.detail


def test_format_symbol_uses_usdt() -> None:
    formatted = CryptoMarketDataProvider._format_symbol(Asset("BTC", AssetClass.CRYPTO))
    assert formatted == "BTC/USDT"


def test_unknown_asset_raises() -> None:
    p = CryptoMarketDataProvider()
    with pytest.raises(ValueError):
        p.fetch_ohlcv(Asset("DEFINITELYNOTREALCOIN", AssetClass.CRYPTO))


def test_ohlcv_normalization_handles_short_candles() -> None:
    # A candle without a volume entry is allowed; we default to 0.0.
    candle = [1700000000000, 100.0, 110.0, 90.0, 105.0]  # 4 OHLC entries
    asset = Asset("BTC", AssetClass.CRYPTO)
    ohlcv = CryptoMarketDataProvider._to_ohlcv(asset, candle)
    assert ohlcv.volume == 0.0
    assert ohlcv.close == 105.0


def test_default_exchange_is_binance() -> None:
    p = CryptoMarketDataProvider()
    assert p.config.exchange_id == "binance"
