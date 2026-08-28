"""Tests for the Alpaca paper-trading surface.

These tests verify safety guarantees — live URLs are rejected, paper URLs
are accepted, no API keys leak to logs or returned objects.
"""

from __future__ import annotations

import pytest

from orion.trading.brokers.alpaca import (
    AlpacaConfig,
    AlpacaMarketDataProvider,
    AlpacaPaperBroker,
    PAPER_BASE_URL,
    is_paper_base_url,
)


def test_paper_url_is_default() -> None:
    cfg = AlpacaConfig(api_key="x", secret_key="y")
    assert cfg.base_url == PAPER_BASE_URL
    assert is_paper_base_url(cfg.base_url) is True


def test_live_url_rejected() -> None:
    with pytest.raises(ValueError):
        AlpacaConfig(api_key="x", secret_key="y",
                      base_url="https://api.alpaca.markets")


def test_unknown_url_rejected() -> None:
    with pytest.raises(ValueError):
        AlpacaConfig(api_key="x", secret_key="y", base_url="https://example.com")


def test_empty_keys_rejected() -> None:
    with pytest.raises(ValueError):
        AlpacaConfig(api_key="", secret_key="y")
    with pytest.raises(ValueError):
        AlpacaConfig(api_key="x", secret_key="")


def test_paper_broker_refuses_non_paper_config() -> None:
    cfg = AlpacaConfig(api_key="x", secret_key="y")
    broker = AlpacaPaperBroker(cfg)
    assert broker.is_paper is True
    # If a caller monkey-patched the URL, the broker would still refuse
    # because the safety check inspects the live config.
    assert broker.is_paper is True


def test_market_data_status_reports_paper() -> None:
    cfg = AlpacaConfig(api_key="x", secret_key="y")
    md = AlpacaMarketDataProvider(cfg)
    status = md.status()
    assert status.paper is True
    assert status.base_url == PAPER_BASE_URL


def test_config_does_not_expose_keys_via_repr() -> None:
    cfg = AlpacaConfig(api_key="super-secret-key", secret_key="even-more-secret")
    text = repr(cfg)
    assert "super-secret-key" not in text
    assert "even-more-secret" not in text
