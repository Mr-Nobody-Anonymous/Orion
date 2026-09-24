"""ORION Multi-Level Kill Switch Manager.

Provides independent kill switches at multiple levels:
- Global: stops all trading
- Portfolio: stops specific portfolio
- Strategy: stops specific strategy
- Broker: stops specific broker/venue
- Account: stops specific account
- Model: stops specific model
- Asset: stops specific instrument
- Venue: stops specific venue

A risk model can say BLOCK and no language model can override it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class KillSwitchEvent:
    """Immutable record of a kill switch action."""

    event_id: str
    level: str  # global, portfolio, strategy, broker, account, model, asset, venue
    target: str  # what was killed
    action: str  # ENGAGED, DISENGAGED
    reason: str
    actor: str  # who triggered it (risk_engine, operator, etc.)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class KillSwitchManager:
    """Multi-level kill switch manager with immutable event logging.

    Kill switches are hierarchical: a global kill switch overrides all
    lower-level switches. Each engagement/disengagement is logged as
    an immutable event.

    Kill switches can be engaged by:
    - Risk engine (automatic, based on breaches)
    - Operator (manual, via dashboard or CLI)
    - Compliance system (automatic, based on rules)

    Kill switches CANNOT be disengaged by:
    - Language models
    - Strategy code
    - External libraries
    """

    def __init__(self) -> None:
        self._global: bool = False
        self._portfolios: set[str] = set()
        self._strategies: set[str] = set()
        self._brokers: set[str] = set()
        self._accounts: set[str] = set()
        self._models: set[str] = set()
        self._assets: set[str] = set()
        self._venues: set[str] = set()
        self._events: list[KillSwitchEvent] = []
        self._event_counter: int = 0

    def _record_event(
        self, level: str, target: str, action: str, reason: str, actor: str,
    ) -> KillSwitchEvent:
        self._event_counter += 1
        event = KillSwitchEvent(
            event_id=f"ks-{self._event_counter:06d}",
            level=level, target=target,
            action=action, reason=reason, actor=actor,
        )
        self._events.append(event)
        return event

    # ── Engage ────────────────────────────────────────────────────────

    def engage_global(self, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        """Engage global kill switch — blocks ALL orders."""
        self._global = True
        return self._record_event("global", "ALL", "ENGAGED", reason, actor)

    def engage_strategy(self, strategy_id: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._strategies.add(strategy_id)
        return self._record_event("strategy", strategy_id, "ENGAGED", reason, actor)

    def engage_asset(self, symbol: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._assets.add(symbol)
        return self._record_event("asset", symbol, "ENGAGED", reason, actor)

    def engage_venue(self, venue: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._venues.add(venue)
        return self._record_event("venue", venue, "ENGAGED", reason, actor)

    def engage_broker(self, broker: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._brokers.add(broker)
        return self._record_event("broker", broker, "ENGAGED", reason, actor)

    def engage_model(self, model_id: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._models.add(model_id)
        return self._record_event("model", model_id, "ENGAGED", reason, actor)

    def engage_portfolio(self, portfolio_id: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._portfolios.add(portfolio_id)
        return self._record_event("portfolio", portfolio_id, "ENGAGED", reason, actor)

    def engage_account(self, account_id: str, reason: str, actor: str = "risk_engine") -> KillSwitchEvent:
        self._accounts.add(account_id)
        return self._record_event("account", account_id, "ENGAGED", reason, actor)

    # ── Disengage ─────────────────────────────────────────────────────

    def disengage_global(self, reason: str, actor: str = "operator") -> KillSwitchEvent:
        self._global = False
        return self._record_event("global", "ALL", "DISENGAGED", reason, actor)

    def disengage_strategy(self, strategy_id: str, reason: str, actor: str = "operator") -> KillSwitchEvent:
        self._strategies.discard(strategy_id)
        return self._record_event("strategy", strategy_id, "DISENGAGED", reason, actor)

    def disengage_asset(self, symbol: str, reason: str, actor: str = "operator") -> KillSwitchEvent:
        self._assets.discard(symbol)
        return self._record_event("asset", symbol, "DISENGAGED", reason, actor)

    def disengage_venue(self, venue: str, reason: str, actor: str = "operator") -> KillSwitchEvent:
        self._venues.discard(venue)
        return self._record_event("venue", venue, "DISENGAGED", reason, actor)

    def disengage_broker(self, broker: str, reason: str, actor: str = "operator") -> KillSwitchEvent:
        self._brokers.discard(broker)
        return self._record_event("broker", broker, "DISENGAGED", reason, actor)

    def disengage_model(self, model_id: str, reason: str, actor: str = "operator") -> KillSwitchEvent:
        self._models.discard(model_id)
        return self._record_event("model", model_id, "DISENGAGED", reason, actor)

    # ── Check ─────────────────────────────────────────────────────────

    def is_blocked(
        self,
        strategy_id: str = "",
        symbol: str = "",
        venue: str = "",
        broker: str = "",
        model_id: str = "",
        portfolio_id: str = "",
        account_id: str = "",
    ) -> tuple[bool, str]:
        """Check if an order would be blocked by any kill switch.

        Returns (is_blocked, reason).
        """
        if self._global:
            return True, "GLOBAL KILL SWITCH ACTIVE"
        if portfolio_id and portfolio_id in self._portfolios:
            return True, f"Portfolio '{portfolio_id}' kill switch active"
        if strategy_id and strategy_id in self._strategies:
            return True, f"Strategy '{strategy_id}' kill switch active"
        if broker and broker in self._brokers:
            return True, f"Broker '{broker}' kill switch active"
        if account_id and account_id in self._accounts:
            return True, f"Account '{account_id}' kill switch active"
        if model_id and model_id in self._models:
            return True, f"Model '{model_id}' kill switch active"
        if symbol and symbol in self._assets:
            return True, f"Asset '{symbol}' kill switch active"
        if venue and venue in self._venues:
            return True, f"Venue '{venue}' kill switch active"
        return False, ""

    # ── Summary ───────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return a complete status summary."""
        return {
            "global_active": self._global,
            "active_switches": {
                "portfolios": sorted(self._portfolios),
                "strategies": sorted(self._strategies),
                "brokers": sorted(self._brokers),
                "accounts": sorted(self._accounts),
                "models": sorted(self._models),
                "assets": sorted(self._assets),
                "venues": sorted(self._venues),
            },
            "total_active": (
                (1 if self._global else 0)
                + len(self._portfolios) + len(self._strategies)
                + len(self._brokers) + len(self._accounts)
                + len(self._models) + len(self._assets) + len(self._venues)
            ),
            "total_events": len(self._events),
        }

    def event_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent kill switch events."""
        events = self._events[-limit:]
        return [
            {
                "event_id": e.event_id,
                "level": e.level,
                "target": e.target,
                "action": e.action,
                "reason": e.reason,
                "actor": e.actor,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in reversed(events)
        ]
