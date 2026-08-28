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
    # Status is honest: ``available`` reflects the actual environment
    # (True when ccxt is installed, False otherwise). It must never claim
    # availability the system does not have.
    import importlib.util
    ccxt_installed = importlib.util.find_spec("ccxt") is not None
    assert status.available is ccxt_installed
    if status.available:
        assert "binance" in status.detail
    else:
        # Honest "unavailable" report — exchange_id still carried but
        # the detail surfaces the missing dependency.
        assert status.detail  # non-empty


def test_format_symbol_uses_usdt() -> None:
    formatted = CryptoMarketDataProvider._format_symbol(Asset("BTC", AssetClass.CRYPTO))
    assert formatted == "BTC/USDT"


def test_unknown_asset_raises() -> None:
    p = CryptoMarketDataProvider()
    import importlib.util
    if importlib.util.find_spec("ccxt") is None:
        # When ccxt is unavailable the provider raises RuntimeError, not
        # ValueError, because it cannot enumerate markets to validate the
        # symbol. We assert that misconfiguration still surfaces as an
        # exception (the "do not hide failures" contract).
        with pytest.raises(RuntimeError):
            p.fetch_ohlcv(Asset("DEFINITELYNOTREALCOIN", AssetClass.CRYPTO))
    else:
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
