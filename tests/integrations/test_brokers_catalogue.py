"""Tests for the broker catalogue (P4-2)."""

from __future__ import annotations

import pytest

from orion.integrations.brokers import (
    BROKERS,
    BrokerRegistry,
    catalogue_as_dict,
    endpoint_for,
    get_venue,
    list_venues,
    missing_keys,
    missing_keys_all,
    ping_all,
)
from orion.infrastructure.configuration import OrionConfig


class TestCatalogueStatic:
    def test_six_venues_known(self) -> None:
        assert set(list_venues()) == {"alpaca", "binance", "kraken", "coinbase", "oanda", "ibkr"}

    def test_get_venue_case_insensitive(self) -> None:
        assert get_venue("ALPACA").venue == "alpaca"
        assert get_venue("missing") is None

    def test_endpoint_for_live_vs_demo(self) -> None:
        entry = get_venue("binance")
        assert endpoint_for(entry, live=False) == "https://testnet.binance.vision"
        assert endpoint_for(entry, live=True) == "https://api.binance.com"

    def test_missing_keys_reports_unset(self) -> None:
        entry = get_venue("kraken")
        assert "KRAKEN_API_KEY" in missing_keys(entry, environ={})
        assert "KRAKEN_API_SECRET" in missing_keys(entry, environ={})

    def test_missing_keys_all(self) -> None:
        report = missing_keys_all(environ={})
        for venue in ("alpaca", "binance", "kraken", "coinbase", "oanda", "ibkr"):
            assert venue in report
            assert report[venue], f"empty report for {venue}"

    def test_catalogue_as_dict_shape(self) -> None:
        data = catalogue_as_dict()
        assert data["count"] == 6
        assert {entry["venue"] for entry in data["venues"]} == set(list_venues())
        assert all("demo_endpoint" in entry and "live_endpoint" in entry for entry in data["venues"])

    def test_catalogue_adapters_map_to_real_classes(self) -> None:
        from orion.integrations.brokers import alpaca, binance, coinbase, ibkr, kraken, oanda

        modules = {
            "AlpacaAdapter": alpaca,
            "BinanceAdapter": binance,
            "KrakenAdapter": kraken,
            "CoinbaseAdapter": coinbase,
            "OandaAdapter": oanda,
            "IBKRAdapter": ibkr,
        }
        for entry in BROKERS:
            assert hasattr(modules[entry.adapter], entry.adapter), entry


class TestPingSafety:
    def test_ping_all_never_sends_orders(self) -> None:
        results = ping_all(timeout=0.2)
        assert len(results) == 6
        for health in results:
            assert health.venue in list_venues()
            assert health.method == "GET"
            assert health.latency_ms >= 0.0


class TestRegistryEnvironmentIntegration:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for venue in ("ALPACA", "BINANCE", "KRAKEN", "COINBASE", "OANDA", "IBKR"):
            for suffix in ("API_KEY", "API_SECRET", "API_KEY_ID", "API_SECRET_KEY",
                           "PASSPHRASE", "ACCOUNT_ID", "API_HOST", "MODE", "API_TOKEN"):
                monkeypatch.delenv(f"ORION_{venue}_{suffix}", raising=False)
                monkeypatch.delenv(f"{venue}_{suffix}", raising=False)

    def test_every_venue_discovers_with_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        creds = {
            "alpaca": (("ALPACA_API_KEY_ID", "k1"), ("ALPACA_API_SECRET_KEY", "s1")),
            "binance": (("BINANCE_API_KEY", "k1"), ("BINANCE_API_SECRET", "s1")),
            "kraken": (("KRAKEN_API_KEY", "k1"), ("KRAKEN_API_SECRET", "s1")),
            "coinbase": (
                ("COINBASE_API_KEY", "k1"),
                ("COINBASE_API_SECRET", "s1"),
                ("COINBASE_PASSPHRASE", "p1"),
            ),
            "oanda": (("OANDA_API_TOKEN", "t1"), ("OANDA_ACCOUNT_ID", "a1")),
            "ibkr": (("IBKR_ACCOUNT_ID", "a1"),),
        }
        for venue, pairs in creds.items():
            for key, value in pairs:
                monkeypatch.setenv(key, value)
        registry = BrokerRegistry(OrionConfig(execution_mode="paper"))
        configured = set(registry.configured())
        for venue in creds:
            assert venue in configured, f"{venue} not configured; got {configured}"
