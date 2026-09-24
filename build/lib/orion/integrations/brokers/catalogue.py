"""Catalogue of every broker venue ORION knows about (P4-2).

The catalogue is the single source of truth for:

* the venues ``BrokerRegistry`` can construct,
* the env keys each venue consumes,
* the demo and live endpoints,
* the per-venue HTTP ping used by the dashboard "venue
  health" card.

It is consumed by:

* the web dashboard (the venues card + the broker status
  pill),
* the TUI snapshot (the venues strip),
* the new ``orion brokers`` CLI subcommand,
* every per-venue evidence test under
  ``tests/integrations/``.

Nothing in this module issues a real order. The ping is
strictly a ``GET`` to the venue's *public* endpoint, so
running it without credentials is safe.
"""

from __future__ import annotations

import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class VenueEntry:
    """Static metadata for a single broker venue."""

    venue: str
    adapter: str
    demo_endpoint: str
    live_endpoint: str
    env_keys: tuple[str, ...]
    ping_path: str = "/"
    ping_method: str = "GET"
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "adapter": self.adapter,
            "demo_endpoint": self.demo_endpoint,
            "live_endpoint": self.live_endpoint,
            "env_keys": list(self.env_keys),
            "ping_path": self.ping_path,
            "ping_method": self.ping_method,
            "description": self.description,
        }


BROKERS: tuple[VenueEntry, ...] = (
    VenueEntry(
        venue="alpaca",
        adapter="AlpacaAdapter",
        demo_endpoint="https://paper-api.alpaca.markets",
        live_endpoint="https://api.alpaca.markets",
        env_keys=("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ORION_ALPACA_MODE"),
        ping_path="/v2/account",
        description="Equities / ETFs paper-trading API",
    ),
    VenueEntry(
        venue="binance",
        adapter="BinanceAdapter",
        demo_endpoint="https://testnet.binance.vision",
        live_endpoint="https://api.binance.com",
        env_keys=("BINANCE_API_KEY", "BINANCE_API_SECRET", "ORION_BINANCE_MODE"),
        ping_path="/api/v3/ping",
        description="Spot exchange (testnet demo)",
    ),
    VenueEntry(
        venue="kraken",
        adapter="KrakenAdapter",
        demo_endpoint="https://api.demo.kraken.com",
        live_endpoint="https://api.kraken.com",
        env_keys=("KRAKEN_API_KEY", "KRAKEN_API_SECRET", "ORION_KRAKEN_MODE"),
        ping_path="/0/public/Time",
        description="Spot exchange (demo gateway)",
    ),
    VenueEntry(
        venue="coinbase",
        adapter="CoinbaseAdapter",
        demo_endpoint="https://api-public.sandbox.exchange.coinbase.com",
        live_endpoint="https://api.exchange.coinbase.com",
        env_keys=("COINBASE_API_KEY", "COINBASE_API_SECRET", "COINBASE_PASSPHRASE", "ORION_COINBASE_MODE"),
        ping_path="/products",
        description="Exchange sandbox (demo)",
    ),
    VenueEntry(
        venue="oanda",
        adapter="OandaAdapter",
        demo_endpoint="https://api-fxpractice.oanda.com",
        live_endpoint="https://api-fxtrade.oanda.com",
        env_keys=("OANDA_API_TOKEN", "OANDA_ACCOUNT_ID", "ORION_OANDA_MODE"),
        ping_path="/v3/accounts",
        description="FX / CFD practice (demo)",
    ),
    VenueEntry(
        venue="ibkr",
        adapter="IBKRAdapter",
        demo_endpoint="https://localhost:5000",
        live_endpoint="https://localhost:5000",
        env_keys=("IBKR_ACCOUNT_ID", "IBKR_API_HOST", "ORION_IBKR_MODE"),
        ping_path="/v1/api/iserver/accounts",
        description="Client Portal Gateway (local)",
    ),
)


def get_venue(venue: str) -> VenueEntry | None:
    for entry in BROKERS:
        if entry.venue == venue.lower():
            return entry
    return None


def list_venues() -> tuple[str, ...]:
    return tuple(entry.venue for entry in BROKERS)


def missing_keys(entry: VenueEntry, environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = os.environ if environ is None else environ
    return tuple(key for key in entry.env_keys if not env.get(key))


def endpoint_for(entry: VenueEntry, *, live: bool) -> str:
    return entry.live_endpoint if live else entry.demo_endpoint


@dataclass(frozen=True, slots=True)
class VenueHealth:
    """Result of a per-venue ping (read-only, never an order)."""

    venue: str
    endpoint: str
    method: str
    path: str
    ok: bool
    status: int = 0
    latency_ms: float = 0.0
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "endpoint": self.endpoint,
            "method": self.method,
            "path": self.path,
            "ok": self.ok,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 2),
            "detail": self.detail,
        }


def _ping(venue: VenueEntry, *, live: bool, timeout: float = 2.0) -> VenueHealth:
    """Issue a single HTTP request to the venue's read-only endpoint.

    This is **never** an order. The goal is a connectivity
    signal for the dashboard's "venue health" card.
    """
    import time as _time

    url = endpoint_for(venue, live=live).rstrip("/") + venue.ping_path
    headers = {"User-Agent": f"ORION-Catalogue/{venue.venue}", "Accept": "application/json"}
    method = venue.ping_method.upper()
    started = _time.perf_counter()
    ctx = None
    if url.startswith("https://localhost") or "127.0.0.1" in url:
        ctx = ssl._create_unverified_context()  # noqa: SLF001 - IBKR gateway uses a self-signed cert
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:  # noqa: S310
            status = resp.status
            _ = resp.read(1)
            latency = (_time.perf_counter() - started) * 1000
            return VenueHealth(venue.venue, url, method, venue.ping_path, True, status=status, latency_ms=latency, detail="ok")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency = (_time.perf_counter() - started) * 1000
        return VenueHealth(venue.venue, url, method, venue.ping_path, False, latency_ms=latency, detail=f"{type(exc).__name__}: {exc}")


def ping_all(*, live: bool = False, timeout: float = 2.0) -> tuple[VenueHealth, ...]:
    """Ping every venue. Safe to call with no credentials configured."""
    return tuple(_ping(entry, live=live, timeout=timeout) for entry in BROKERS)


def catalogue_as_dict() -> dict[str, Any]:
    return {
        "venues": [entry.as_dict() for entry in BROKERS],
        "count": len(BROKERS),
    }


def missing_keys_all(environ: Mapping[str, str] | None = None) -> dict[str, list[str]]:
    return {entry.venue: list(missing_keys(entry, environ=environ)) for entry in BROKERS}