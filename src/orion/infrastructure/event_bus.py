from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import DefaultDict

from ..data.contracts import Event


Handler = Callable[[Event], None]


class EventBus:
    """Small in-process bus; transport can be replaced without changing events."""

    def __init__(self) -> None:
        self._handlers: DefaultDict[str, list[Handler]] = defaultdict(list)
        self.history: list[Event] = []

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event: Event) -> None:
        self.history.append(event)
        for handler in tuple(self._handlers.get(event.name, ())):
            handler(event)
