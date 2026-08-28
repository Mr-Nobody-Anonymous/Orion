"""Live broker alert surface.

A small data structure that lets the rest of ORION subscribe to
broker events (connectivity loss, rate limit, order rejection)
without coupling to any specific broker SDK.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Deque


class LiveBrokerAlertKind(str, Enum):
    CONNECTIVITY = "connectivity"
    RATE_LIMIT = "rate_limit"
    ORDER_REJECTED = "order_rejected"
    ORDER_FILLED = "order_filled"
    AUTH = "auth"
    KILL_SWITCH = "kill_switch"


@dataclass(frozen=True, slots=True)
class LiveBrokerAlert:
    kind: LiveBrokerAlertKind
    broker: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "broker": self.broker,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class LiveBrokerAlerts:
    """Thread-safe bounded ring buffer of broker alerts.

    Operators and dashboards can drain the buffer without taking
    a lock by iterating :attr:`recent`.
    """

    def __init__(self, capacity: int = 256) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._lock = threading.Lock()
        self._buffer: Deque[LiveBrokerAlert] = deque(maxlen=capacity)

    def push(self, alert: LiveBrokerAlert) -> None:
        with self._lock:
            self._buffer.append(alert)

    def recent(self, limit: int | None = None) -> tuple[LiveBrokerAlert, ...]:
        with self._lock:
            items = tuple(self._buffer)
        if limit is None or limit >= len(items):
            return items
        return items[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
