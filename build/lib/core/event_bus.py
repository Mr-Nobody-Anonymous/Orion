"""
Orion Event Bus
Asynchronous pub/sub event bus for decoupled component communication.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class EventType(Enum):
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    HEARTBEAT = "heartbeat"

    # Market Data events
    TICK = "tick"
    BAR = "bar"
    ORDERBOOK_UPDATE = "orderbook_update"

    # Signal & Strategy events
    SIGNAL_GENERATED = "signal_generated"
    STRATEGY_ALERT = "strategy_alert"

    # Order & Execution events
    ORDER_SUBMITTED = "order_submitted"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_REJECTED = "order_rejected"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

    # Risk & Portfolio events
    RISK_BREACH = "risk_breach"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    POSITION_UPDATE = "position_update"
    PORTFOLIO_REBALANCE = "portfolio_rebalance"


@dataclass
class Event:
    event_type: Union[EventType, str]
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: Optional[str] = None
    event_id: Optional[str] = None


HandlerType = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    High-throughput asynchronous Event Bus.
    Supports topic subscriptions, regex matching, and async callbacks.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[HandlerType]] = {}
        self._global_subscribers: List[HandlerType] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: Union[EventType, str], handler: HandlerType):
        """Subscribe an async handler to a specific event type."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        if key not in self._subscribers:
            self._subscribers[key] = []
        if handler not in self._subscribers[key]:
            self._subscribers[key].append(handler)

    def subscribe_all(self, handler: HandlerType):
        """Subscribe to all events (useful for logging/monitoring)."""
        if handler not in self._global_subscribers:
            self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: Union[EventType, str], handler: HandlerType):
        """Unsubscribe handler from an event type."""
        key = event_type.value if isinstance(event_type, EventType) else str(event_type)
        if key in self._subscribers and handler in self._subscribers[key]:
            self._subscribers[key].remove(handler)

    async def publish(self, event: Event):
        """Publish an event to the queue."""
        await self._queue.put(event)

    def publish_nowait(self, event: Event):
        """Non-blocking publish to event queue."""
        self._queue.put_nowait(event)

    async def start(self):
        """Start the background event dispatcher loop."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._process_events())
            logger.info("EventBus dispatcher started.")

    async def stop(self):
        """Gracefully stop event bus processing."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus dispatcher stopped.")

    async def _process_events(self):
        """Main dispatcher loop."""
        while self._running:
            try:
                event = await self._queue.get()
                key = event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type)
                
                handlers = list(self._subscribers.get(key, [])) + list(self._global_subscribers)
                if handlers:
                    await asyncio.gather(
                        *[self._safe_dispatch(h, event) for h in handlers],
                        return_exceptions=True
                    )
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event in EventBus: {e}", exc_info=True)

    async def _safe_dispatch(self, handler: HandlerType, event: Event):
        try:
            res = handler(event)
            if asyncio.iscoroutine(res):
                await res
        except Exception as e:
            logger.error(f"Event handler {getattr(handler, '__name__', 'unknown')} failed: {e}", exc_info=True)
