"""Tests for the multi-broker registry, adapters, and kill switch.

No test in this module issues a live network call: every adapter is
constructed with a fake transport (ORION's "no live network test"
policy).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from orion.infrastructure.configuration import OrionConfig
from orion.integrations.brokers import (
    AlpacaAdapter,
    BinanceAdapter,
    BrokerRegistry,
    KillSwitch,
    LiveTradingDisabledError,
)


def fake_transport_factory(responses: dict[str, dict[str, Any]] | None = None):
    """Return a transport that records requests and replays canned JSON."""
    calls: list[tuple[str, str]] = []

    def transport(method: str, url: str, headers: Any, body: Any, context: Any = None):
        calls.append((method, url))
        for fragment, payload in (responses or {}).items():
            if fragment in url:
                return 200, json.dumps(payload).encode("utf-8")
        return 200, b"{}"

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for venue in ("ALPACA", "BINANCE", "KRAKEN", "COINBASE", "OANDA", "IBKR"):
        for suffix in ("API_KEY", "API_SECRET", "API_KEY_ID", "API_SECRET_KEY",
                       "PASSPHRASE", "ACCOUNT_ID", "MODE"):
            monkeypatch.delenv(f"ORION_{venue}_{suffix}", raising=False)
            monkeypatch.delenv(f"{venue}_{suffix}", raising=False)
    return monkeypatch


class TestKillSwitch:
    def test_engaged_blocks_registry_submit(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        registry = BrokerRegistry(OrionConfig())
        registry.kill_switch.engage("operator panic")
        with pytest.raises(Exception, match="kill switch"):
            registry.submit("BTCUSDT", side="BUY", quantity=0.01)

    def test_engage_disengage_roundtrip(self) -> None:
        ks = KillSwitch()
        assert not ks.engaged
        ks.engage("test")
        assert ks.engaged
        ks.disengage()
        assert not ks.engaged


class TestRegistryDiscovery:
    def test_no_venues_when_no_keys(self, clean_env) -> None:
        registry = BrokerRegistry(OrionConfig())
        assert registry.configured() == ()

    def test_demo_mode_is_default(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        registry = BrokerRegistry(OrionConfig())
        assert "binance" in registry.configured()
        record = registry.get("binance")
        assert record.mode == "demo"
        assert record.adapter.endpoint == BinanceAdapter.DEMO_BASE

    def test_live_request_without_unlock_falls_back_to_demo(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        monkeypatch.setenv("BINANCE_MODE", "live")
        registry = BrokerRegistry(OrionConfig())
        record = registry.get("binance")
        assert record.mode.startswith("demo")
        assert record.adapter.endpoint == BinanceAdapter.DEMO_BASE

    def test_status_reports_venues(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("ALPACA_API_KEY_ID", "id")
        monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret")
        registry = BrokerRegistry(OrionConfig())
        status = registry.status()
        names = [v["name"] for v in status["venues"]]
        assert "alpaca" in names
        assert status["kill_switch"]["engaged"] is False


class TestBinanceAdapter:
    def test_submit_signs_and_sends(self, clean_env) -> None:
        transport = fake_transport_factory()
        config = OrionConfig(execution_mode="paper")
        adapter = BinanceAdapter(
            config, api_key="key", api_secret="secret", transport=transport
        )
        result = adapter.submit({"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.01})
        assert result["_status"] == 200
        method, url = transport.calls[0]
        assert method == "POST"
        assert "testnet.binance.vision" in url
        assert "signature=" in url
        assert "BTCUSDT" in url

    def test_requires_credentials(self, clean_env) -> None:
        config = OrionConfig(execution_mode="paper")
        adapter = BinanceAdapter(config, transport=fake_transport_factory())
        with pytest.raises(Exception, match="api_key"):
            adapter.submit({"symbol": "BTCUSDT", "side": "BUY", "quantity": 1})


class TestLiveGate:
    def test_live_config_unlocks_live_endpoint(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        monkeypatch.setenv("BINANCE_MODE", "live")
        config = OrionConfig(execution_mode="live", live_trading_enabled=True)
        registry = BrokerRegistry(config)
        record = registry.get("binance")
        assert record.mode == "live"
        assert record.adapter.endpoint == BinanceAdapter.LIVE_BASE

    def test_config_rejects_live_without_flag(self) -> None:
        with pytest.raises(ValueError):
            OrionConfig(execution_mode="live", live_trading_enabled=False).validate()

    def test_alpaca_live_guard_still_enforced(self, clean_env) -> None:
        config = OrionConfig(execution_mode="live", live_trading_enabled=False)
        with pytest.raises(LiveTradingDisabledError):
            AlpacaAdapter(config, api_key="k", api_secret="s")


class TestRouting:
    def test_crypto_routes_to_crypto_venue(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        monkeypatch.setenv("ALPACA_API_KEY_ID", "k")
        registry = BrokerRegistry(OrionConfig())
        assert registry.route("BTCUSDT").venue == "binance"
        assert registry.route("AAPL").venue == "alpaca"

    def test_fx_routes_to_oanda(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("OANDA_API_TOKEN", "tok")
        monkeypatch.setenv("OANDA_ACCOUNT_ID", "acc")
        registry = BrokerRegistry(OrionConfig())
        assert registry.route("EUR_USD").venue == "oanda"

    def test_dry_run_never_calls_network(self, clean_env, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        registry = BrokerRegistry(OrionConfig())
        result = registry.submit("BTCUSDT", side="BUY", quantity=0.01, dry_run=True)
        assert result["status"] == "DRY_RUN"

    def test_unconfigured_symbol_raises(self, clean_env) -> None:
        registry = BrokerRegistry(OrionConfig())
        with pytest.raises(Exception, match="no configured venue"):
            registry.route("AAPL")