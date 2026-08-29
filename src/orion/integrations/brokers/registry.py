"""Broker registry, kill switch, and env-driven venue discovery.

The :class:`BrokerRegistry` is the single trading surface the web
dashboard and the orchestrator use. It:

* Discovers every venue whose credentials exist in the environment
  (``.env`` file or OS env) and constructs it in **demo mode by
  default** — a venue only runs live when ``ORION_ALLOW_LIVE_TRADING``
  is ``true`` AND the :class:`OrionConfig` says ``execution_mode ==
  "live"`` with ``live_trading_enabled``.
* Enforces a :class:`KillSwitch`: once engaged, no order leaves the
  process until a human disengages it.
* Routes orders by symbol hint (BTC/ETH -> crypto venues, EUR/USD ->
  FX, else equity) with manual override.
"""

from __future__ import annotations

import dataclasses
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .alpaca import AlpacaAdapter
from .base import BaseBrokerAdapter, BrokerAdapterError, BrokerHealth, LiveTradingDisabledError
from .binance import BinanceAdapter
from .coinbase import CoinbaseAdapter
from .ibkr import IBKRAdapter
from .kraken import KrakenAdapter
from .oanda import OandaAdapter

_CRYPTO_HINTS = ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK")
_FX_PAIR_SEPARATORS = ("/", "-", "_")


class KillSwitch:
    """Process-wide trading kill switch (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engaged = False
        self._reason = ""
        self._engaged_at: datetime | None = None

    def engage(self, reason: str = "manual") -> None:
        with self._lock:
            self._engaged = True
            self._reason = reason
            self._engaged_at = datetime.now(tz=timezone.utc)

    def disengage(self) -> None:
        with self._lock:
            self._engaged = False
            self._reason = ""
            self._engaged_at = None

    @property
    def engaged(self) -> bool:
        with self._lock:
            return self._engaged

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "engaged": self._engaged,
                "reason": self._reason,
                "engaged_at": self._engaged_at.isoformat() if self._engaged_at else None,
            }


@dataclasses.dataclass
class VenueRecord:
    adapter: BaseBrokerAdapter
    venue: str
    mode: str

    def as_dict(self) -> dict[str, Any]:
        health = self.adapter.health()
        return {"venue": self.venue, "mode": self.mode, **health.as_dict()}


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _mode_for(venue: str, config: OrionConfig) -> str:
    """Resolve venue mode. Demo by default; live requires every gate."""
    requested = (_env(f"ORION_{venue.upper()}_MODE") or _env(f"{venue.upper()}_MODE") or "demo").lower()
    if requested == "live":
        if config.execution_mode == "live" and config.live_trading_enabled:
            return "live"
        return "demo (live requested but not unlocked)"
    return "demo"
class BrokerRegistry:
    """Discovers configured venues and routes orders to them."""

    VENUES: tuple[str, ...] = ("alpaca", "binance", "kraken", "coinbase", "oanda", "ibkr")

    def __init__(self, config: OrionConfig | None = None, *, kill_switch: KillSwitch | None = None) -> None:
        self.config = config or OrionConfig()
        self.kill_switch = kill_switch or KillSwitch()
        self._venues: dict[str, VenueRecord] = {}
        self._discover()

    # ------------------------------------------------------------- discovery

    def _credentials_for(self, venue: str) -> dict[str, str | None]:
        prefix = venue.upper()

        def pick(*names: str) -> str | None:
            for name in names:
                value = _env(name)
                if value:
                    return value
            return None

        return {
            "api_key": pick(f"ORION_{prefix}_API_KEY", f"{prefix}_API_KEY", f"{prefix}_API_KEY_ID"),
            "api_secret": pick(f"ORION_{prefix}_API_SECRET", f"{prefix}_API_SECRET", f"{prefix}_API_SECRET_KEY"),
            "passphrase": _env(f"{prefix}_PASSPHRASE"),
            "account_id": pick(f"ORION_{prefix}_ACCOUNT_ID", f"{prefix}_ACCOUNT_ID"),
        }

    def _construct(self, venue: str, creds: Mapping[str, str | None], endpoint: str | None = None) -> BaseBrokerAdapter:
        mode = _mode_for(venue, self.config)
        cfg = self.config
        if mode != "live" and self.config.execution_mode not in ("paper", "demo"):
            # Adapt the frozen config to the demo surface the adapters accept.
            cfg = dataclasses.replace(self.config, execution_mode="paper")
        common: dict[str, Any] = {"endpoint": endpoint} if endpoint else {}
        if venue == "alpaca":
            return AlpacaAdapter(
                cfg,
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                endpoint=endpoint
                or (AlpacaAdapter.PAPER_BASE if mode != "live" else AlpacaAdapter.LIVE_BASE),
            )
        if venue == "binance":
            return BinanceAdapter(cfg, api_key=creds["api_key"], api_secret=creds["api_secret"], **common)
        if venue == "kraken":
            return KrakenAdapter(cfg, api_key=creds["api_key"], api_secret=creds["api_secret"], **common)
        if venue == "coinbase":
            return CoinbaseAdapter(
                cfg,
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                passphrase=creds["passphrase"],
                **common,
            )
        if venue == "oanda":
            return OandaAdapter(cfg, api_key=creds["api_key"], account_id=creds["account_id"], **common)
        if venue == "ibkr":
            return IBKRAdapter(cfg, account_id=creds["account_id"], **common)
        raise BrokerAdapterError(f"registry: unknown venue {venue!r}")

    def _discover(self) -> None:
        for venue in self.VENUES:
            creds = self._credentials_for(venue)
            if not creds["api_key"] and not creds["account_id"]:
                continue  # venue simply not configured
            try:
                adapter = self._construct(venue, creds)
            except LiveTradingDisabledError:
                self._venues[venue] = VenueRecord(_BlockedAdapter(venue), venue, "blocked")
                continue
            self._venues[venue] = VenueRecord(adapter, venue, _mode_for(venue, self.config))

    # ------------------------------------------------------------- surfaces

    def configured(self) -> tuple[str, ...]:
        return tuple(sorted(self._venues))

    def get(self, venue: str) -> VenueRecord:
        record = self._venues.get(venue.lower())
        if record is None:
            raise BrokerAdapterError(
                f"registry: venue {venue!r} is not configured (set its API key in .env)"
            )
        return record

    def route(self, symbol: str, *, venue: str | None = None) -> VenueRecord:
        """Pick the venue for a symbol (manual override wins)."""
        if venue:
            return self.get(venue)
        upper = symbol.upper()
        is_crypto = (
            any(h in upper for h in _CRYPTO_HINTS)
            or upper.endswith("USDT")
            or "-USD" in upper
            or (upper.endswith("USD") and not any(sep in upper for sep in _FX_PAIR_SEPARATORS))
        )
        is_fx = any(sep in upper for sep in _FX_PAIR_SEPARATORS) and not is_crypto
        if is_crypto:
            for candidate in ("binance", "kraken", "coinbase", "alpaca"):
                if candidate in self._venues:
                    return self._venues[candidate]
        if is_fx:
            for candidate in ("oanda", "kraken"):
                if candidate in self._venues:
                    return self._venues[candidate]
        for candidate in ("alpaca", "ibkr", "coinbase"):
            if candidate in self._venues:
                return self._venues[candidate]
        raise BrokerAdapterError(
            f"registry: no configured venue can trade {symbol!r}; set an API key in .env"
        )

    def submit(
        self,
        symbol: str,
        *,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: float | None = None,
        venue: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Route and (optionally) submit an order. Demo-first by construction."""
        if self.kill_switch.engaged:
            raise BrokerAdapterError(
                f"registry: kill switch engaged — {self.kill_switch.as_dict()['reason']}"
            )
        record = self.route(symbol, venue=venue)
        ticket: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "type": order_type,
            "client_order_id": f"orion-{uuid.uuid4().hex[:24]}",
        }
        if price is not None:
            ticket["price"] = price
        if dry_run:
            return {"status": "DRY_RUN", "venue": record.venue, "mode": record.mode, "order": ticket}
        response = record.adapter.submit(ticket)
        return {
            "status": "SUBMITTED",
            "venue": record.venue,
            "mode": record.mode,
            "order": ticket,
            "response": response,
        }

    def status(self) -> dict[str, Any]:
        return {
            "kill_switch": self.kill_switch.as_dict(),
            "venues": [record.as_dict() for record in sorted(self._venues.values(), key=lambda r: r.venue)],
        }


class _BlockedAdapter(BaseBrokerAdapter):
    """Placeholder for a venue whose live construction was refused."""

    name = "blocked"

    def __init__(self, venue: str) -> None:
        self.name = f"{venue}:blocked"
        self.endpoint = "n/a"
        self.config = None  # deliberately unconfigured; submit() must refuse

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        raise LiveTradingDisabledError(f"{self.name}: live trading is disabled by configuration")

    def health(self) -> BrokerHealth:
        return BrokerHealth(
            name=self.name,
            available=False,
            mode="blocked",
            endpoint=self.endpoint,
            detail="live construction refused (enable live trading explicitly)",
        )