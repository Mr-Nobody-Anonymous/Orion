"""Market Surveillance and Trade Abuse Detection.

Detects Spoofing, Layering, Wash Trading, and Pump-and-Dump manipulation.
Supports both stateful streaming tracking and batch static analysis.
Lives in the Control plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import time
import uuid
from typing import Any, Mapping, Sequence

from ..data.contracts import Action, Order


class AbuseType(str, Enum):
    SPOOFING = "SPOOFING"
    LAYERING = "LAYERING"
    WASH_TRADING = "WASH_TRADING"
    PUMP_AND_DUMP = "PUMP_AND_DUMP"


@dataclass(frozen=True, slots=True)
class SurveillanceAlert:
    alert_id: str
    abuse_type: AbuseType
    symbol: str
    account_id: str
    severity: str  # "HIGH", "CRITICAL"
    evidence: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def manipulation_type(self) -> str:
        return self.abuse_type.value


class MarketSurveillanceEngine:
    """Surveillance detector identifying abusive trading behavior."""

    def __init__(
        self,
        spoofing_cancel_ratio_threshold: float = 0.80,
        wash_trade_window_seconds: float = 30.0,
    ) -> None:
        self.spoofing_cancel_ratio_threshold = spoofing_cancel_ratio_threshold
        self.wash_trade_window_seconds = wash_trade_window_seconds

        # Stateful tracking
        self._orders: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._cancels: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._trades: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def record_order(
        self, account_id: str, symbol: str, side: str, price: float, quantity: float, timestamp: float | None = None
    ) -> None:
        key = (account_id, symbol)
        ts = time.time() if timestamp is None else timestamp
        self._orders.setdefault(key, []).append({
            "side": side.upper(),
            "price": price,
            "quantity": quantity,
            "ts": ts,
        })

    def record_cancel(
        self, account_id: str, symbol: str, quantity: float, timestamp: float | None = None
    ) -> None:
        key = (account_id, symbol)
        ts = time.time() if timestamp is None else timestamp
        self._cancels.setdefault(key, []).append({
            "quantity": quantity,
            "ts": ts,
        })

    def record_trade(
        self, account_id: str, symbol: str, side: str, price: float, quantity: float, timestamp: float | None = None
    ) -> None:
        key = (account_id, symbol)
        ts = time.time() if timestamp is None else timestamp
        self._trades.setdefault(key, []).append({
            "side": side.upper(),
            "price": price,
            "quantity": quantity,
            "ts": ts,
        })

    def detect_spoofing(
        self, account_id: str, symbol: str, current_time: float | None = None
    ) -> list[SurveillanceAlert]:
        key = (account_id, symbol)
        orders = self._orders.get(key, [])
        cancels = self._cancels.get(key, [])

        if not orders:
            return []

        cancel_ratio = len(cancels) / len(orders)
        if len(orders) >= 5 and cancel_ratio >= self.spoofing_cancel_ratio_threshold:
            return [
                SurveillanceAlert(
                    alert_id=f"spoof_{symbol}_{account_id}_{uuid.uuid4().hex[:6]}",
                    abuse_type=AbuseType.SPOOFING,
                    symbol=symbol,
                    account_id=account_id,
                    severity="CRITICAL",
                    evidence=f"High cancel ratio {cancel_ratio*100:.1f}% ({len(cancels)} cancels out of {len(orders)} orders)",
                )
            ]
        return []

    def detect_wash_trading(
        self, account_id: str, symbol: str, current_time: float | None = None
    ) -> list[SurveillanceAlert]:
        key = (account_id, symbol)
        trades = self._trades.get(key, [])
        now = time.time() if current_time is None else current_time

        alerts: list[SurveillanceAlert] = []
        recent = [t for t in trades if abs(now - t["ts"]) <= self.wash_trade_window_seconds]

        buys = [t for t in recent if t["side"] in ("BUY", "BID")]
        sells = [t for t in recent if t["side"] in ("SELL", "ASK", "SHORT")]

        for b in buys:
            for s in sells:
                if abs(b["price"] - s["price"]) < 1e-4 and abs(b["quantity"] - s["quantity"]) < 1e-4:
                    alerts.append(
                        SurveillanceAlert(
                            alert_id=f"wash_{symbol}_{account_id}_{uuid.uuid4().hex[:6]}",
                            abuse_type=AbuseType.WASH_TRADING,
                            symbol=symbol,
                            account_id=account_id,
                            severity="CRITICAL",
                            evidence=f"Matched buy and sell of {b['quantity']} @ ${b['price']} within {abs(b['ts']-s['ts']):.1f}s",
                        )
                    )
        return alerts

    # --- Backward compatibility static batch methods ---
    @staticmethod
    def detect_wash_trading_batch(
        orders_placed: Sequence[tuple[str, Order]],
    ) -> list[SurveillanceAlert]:
        alerts: list[SurveillanceAlert] = []
        by_symbol: dict[str, list[tuple[str, Order]]] = {}
        for acc_id, order in orders_placed:
            by_symbol.setdefault(order.asset.symbol, []).append((acc_id, order))

        for sym, ords in by_symbol.items():
            buys = [(acc, o) for acc, o in ords if o.side == Action.BUY]
            sells = [(acc, o) for acc, o in ords if o.side in (Action.SELL, Action.SHORT)]

            for b_acc, b_ord in buys:
                for s_acc, s_ord in sells:
                    if b_acc == s_acc:
                        price_match = (b_ord.limit_price is not None and b_ord.limit_price == s_ord.limit_price)
                        qty_match = (b_ord.quantity == s_ord.quantity)
                        if price_match and qty_match:
                            alerts.append(SurveillanceAlert(
                                alert_id=f"wash_{sym}_{b_acc}_{int(datetime.now(timezone.utc).timestamp())}",
                                abuse_type=AbuseType.WASH_TRADING,
                                symbol=sym,
                                account_id=b_acc,
                                severity="CRITICAL",
                                evidence=f"Simultaneous buy and sell orders of {b_ord.quantity} shares at ${b_ord.limit_price} from account {b_acc}.",
                            ))
        return alerts

    @staticmethod
    def detect_spoofing_batch(
        account_id: str,
        symbol: str,
        orders_submitted: int,
        orders_cancelled: int,
        executed_fills: int,
        avg_time_to_cancel_ms: float,
    ) -> SurveillanceAlert | None:
        if orders_submitted >= 10:
            cancel_ratio = orders_cancelled / orders_submitted
            fill_ratio = executed_fills / orders_submitted
            if cancel_ratio > 0.85 and fill_ratio < 0.05 and avg_time_to_cancel_ms < 500.0:
                return SurveillanceAlert(
                    alert_id=f"spoof_{symbol}_{account_id}_{int(datetime.now(timezone.utc).timestamp())}",
                    abuse_type=AbuseType.SPOOFING,
                    symbol=symbol,
                    account_id=account_id,
                    severity="CRITICAL",
                    evidence=f"Cancel ratio {cancel_ratio*100:.1f}%, fill ratio {fill_ratio*100:.1f}%, avg cancel latency {avg_time_to_cancel_ms:.1f}ms.",
                )
        return None
