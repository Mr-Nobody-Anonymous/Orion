"""
Orion Circuit Breaker
Protects the trading engine from catastrophic cascade failures and unexpected drawdowns.
"""

import time
import logging
from enum import Enum
from typing import Callable, Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operations
    OPEN = "open"          # Trips: all operations halted
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreaker:
    """
    Standard and financial circuit breaker.
    Monitors error rates and drawdown thresholds.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        max_drawdown_pct: float = 5.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_drawdown_pct = max_drawdown_pct

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()

    def record_success(self):
        """Record successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker reset to CLOSED state.")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self, reason: str = ""):
        """Record an operation or risk failure."""
        self.failure_count += 1
        logger.warning(f"Circuit breaker recorded failure ({self.failure_count}/{self.failure_threshold}): {reason}")

        if self.failure_count >= self.failure_threshold and self.state != CircuitState.OPEN:
            self.trip(reason=f"Exceeded max failure count: {reason}")

    def trip(self, reason: str = ""):
        """Manually or automatically trip the circuit breaker."""
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        logger.critical(f"🚨 CIRCUIT BREAKER TRIPPED! State=OPEN. Reason: {reason}")

    def reset(self):
        """Manually reset the breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()
        logger.info("Circuit breaker manually reset to CLOSED.")

    def can_execute(self) -> bool:
        """Check if actions are permitted."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_state_change > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = time.time()
                logger.info("Circuit breaker entering HALF_OPEN trial state.")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False
