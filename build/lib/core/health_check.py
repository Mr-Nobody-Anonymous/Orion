"""
Orion Health Checker
Provides continuous liveness and readiness monitoring across all active subsystems.
"""

import asyncio
import logging
from typing import Dict, Any, Callable, Coroutine, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Subsystem health monitor and status aggregator.
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], Any]] = {}
        self._last_status: Dict[str, Any] = {}

    def register_check(self, name: str, check_fn: Callable[[], Any]):
        """Register a health check callback (sync or async)."""
        self._checks[name] = check_fn

    async def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_healthy = True

        for name, check_fn in self._checks.items():
            try:
                res = check_fn()
                if asyncio.iscoroutine(res):
                    res = await res
                status = res if isinstance(res, dict) else {"status": "ok", "details": res}
                results[name] = status
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = {"status": "unhealthy", "error": str(e)}
                overall_healthy = False

        self._last_status = {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "subsystems": results
        }
        return self._last_status

    @property
    def last_status(self) -> Dict[str, Any]:
        return self._last_status
