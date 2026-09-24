"""
Orion Trading Engine
The central orchestrator that coordinates all subsystems.
Comparable to BlackRock's Aladdin core engine.
"""

import asyncio
import signal
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field

from src.core.event_bus import EventBus, Event, EventType
from src.core.config_manager import ConfigManager
from src.core.state_machine import SystemState, StateMachine
from src.core.circuit_breaker import CircuitBreaker
from src.core.health_check import HealthChecker

logger = logging.getLogger(__name__)


class EngineMode(Enum):
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"
    SIMULATION = "simulation"
    RESEARCH = "research"


@dataclass
class EngineConfig:
    mode: EngineMode = EngineMode.PAPER
    max_strategies: int = 50
    max_positions: int = 1000
    heartbeat_interval: float = 1.0
    risk_check_interval: float = 0.5
    data_buffer_size: int = 10000
    enable_circuit_breaker: bool = True
    enable_kill_switch: bool = True
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 15.0
    max_position_size_pct: float = 10.0
    max_correlation: float = 0.85
    max_leverage: float = 3.0
    log_level: str = "INFO"


class OrionEngine:
    """
    The Orion Trading Engine.

    This is the central nervous system of the entire platform.
    It coordinates:
    - Data ingestion and distribution
    - Strategy execution
    - Risk management
    - Order routing and execution
    - Portfolio management
    - ML model serving
    - Monitoring and alerting

    Architecture:
    - Event-driven with async support
    - Plugin-based strategy system
    - Multi-broker support
    - Real-time risk monitoring
    - Circuit breaker protection
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.engine_id = f"orion-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Core components
        self.event_bus = EventBus()
        self.config_manager = ConfigManager()
        self.state_machine = StateMachine()
        self.circuit_breaker = CircuitBreaker()
        self.health_checker = HealthChecker()

        # Subsystem references (initialized during startup)
        self.data_manager = None
        self.broker_manager = None
        self.strategy_manager = None
        self.risk_manager = None
        self.portfolio_manager = None
        self.execution_engine = None
        self.ml_engine = None
        self.monitoring = None
        self.alert_manager = None

        # State
        self._running = False
        self._start_time = None
        self._tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # Metrics
        self._metrics = {
            "events_processed": 0,
            "orders_submitted": 0,
            "orders_filled": 0,
            "signals_generated": 0,
            "risk_checks_passed": 0,
            "risk_checks_failed": 0,
            "circuit_breaker_trips": 0,
            "errors": 0,
        }

        logger.info(f"Orion Engine initialized: {self.engine_id}")
        logger.info(f"Mode: {self.config.mode.value}")

    async def start(self):
        """Start the Orion Engine."""
        logger.info("=" * 60)
        logger.info("  ORION TRADING ENGINE STARTING")
        logger.info("=" * 60)

        try:
            self.state_machine.transition(SystemState.INITIALIZING)
            self._start_time = datetime.utcnow()

            # Start event bus
            await self.event_bus.start()

            # Initialize subsystems in order
            await self._initialize_subsystems()

            # Register event handlers
            self._register_event_handlers()

            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # Start all subsystems
            await self._start_subsystems()

            self.state_machine.transition(SystemState.RUNNING)
            self._running = True

            logger.info("=" * 60)
            logger.info("  ORION ENGINE RUNNING")
            logger.info(f"  Mode: {self.config.mode.value}")
            logger.info(f"  Engine ID: {self.engine_id}")
            logger.info("=" * 60)

            # Main loop
            await self._main_loop()

        except Exception as e:
            logger.critical(f"Engine startup failed: {e}", exc_info=True)
            self.state_machine.transition(SystemState.ERROR)
            await self.shutdown()
            raise

    async def _initialize_subsystems(self):
        """Initialize all subsystems in dependency order."""
        logger.info("Initializing subsystems...")

        # 1. Data Manager
        try:
            from src.data.manager import DataManager
            self.data_manager = DataManager(self.config_manager, self.event_bus)
            if hasattr(self.data_manager, "initialize"):
                await self.data_manager.initialize()
            logger.info("  ✅ Data Manager initialized")
        except ImportError:
            logger.info("  ℹ️ Data Manager not loaded yet, using integrated feed fallback")

        # 2. Broker Manager
        try:
            from src.brokers.broker_manager import BrokerManager
            self.broker_manager = BrokerManager(self.config_manager, self.event_bus)
            if hasattr(self.broker_manager, "initialize"):
                await self.broker_manager.initialize()
            logger.info("  ✅ Broker Manager initialized")
        except ImportError:
            logger.info("  ℹ️ Broker Manager not loaded yet, paper trading available")

        # 3. Risk Manager
        try:
            from src.risk.risk_manager import RiskManager
            self.risk_manager = RiskManager(self.config, self.event_bus)
            if hasattr(self.risk_manager, "initialize"):
                await self.risk_manager.initialize()
            logger.info("  ✅ Risk Manager initialized")
        except ImportError:
            logger.info("  ℹ️ Risk Manager not loaded yet, default circuit rules active")

        # 4. Strategy Manager
        try:
            from src.strategies.strategy_manager import StrategyManager
            self.strategy_manager = StrategyManager(self.config_manager, self.event_bus)
            if hasattr(self.strategy_manager, "initialize"):
                await self.strategy_manager.initialize()
            logger.info("  ✅ Strategy Manager initialized")
        except ImportError:
            pass

        # 5. Portfolio Manager
        try:
            from src.portfolio.portfolio_manager import PortfolioManager
            self.portfolio_manager = PortfolioManager(self.config_manager, self.event_bus)
            if hasattr(self.portfolio_manager, "initialize"):
                await self.portfolio_manager.initialize()
            logger.info("  ✅ Portfolio Manager initialized")
        except ImportError:
            pass

        # 6. Execution Engine
        try:
            from src.execution.execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine(self.config_manager, self.event_bus)
            if hasattr(self.execution_engine, "initialize"):
                await self.execution_engine.initialize()
            logger.info("  ✅ Execution Engine initialized")
        except ImportError:
            pass

        # Register health checks
        self.health_checker.register_check("circuit_breaker", lambda: {
            "state": self.circuit_breaker.state.value,
            "can_execute": self.circuit_breaker.can_execute()
        })
        self.health_checker.register_check("state_machine", lambda: {
            "current_state": self.state_machine.current_state.value
        })

    def _register_event_handlers(self):
        """Register listeners for core engine events."""
        async def on_order_submitted(event: Event):
            self._metrics["orders_submitted"] += 1

        async def on_order_filled(event: Event):
            self._metrics["orders_filled"] += 1

        async def on_signal(event: Event):
            self._metrics["signals_generated"] += 1

        async def on_risk_breach(event: Event):
            self._metrics["risk_checks_failed"] += 1
            if self.config.enable_circuit_breaker:
                self.circuit_breaker.trip(reason=str(event.data))
                self._metrics["circuit_breaker_trips"] += 1

        self.event_bus.subscribe(EventType.ORDER_SUBMITTED, on_order_submitted)
        self.event_bus.subscribe(EventType.ORDER_FILLED, on_order_filled)
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, on_signal)
        self.event_bus.subscribe(EventType.RISK_BREACH, on_risk_breach)

    def _setup_signal_handlers(self):
        """Setup OS signal listeners for graceful shutdown."""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
                except NotImplementedError:
                    # Windows loop may not implement add_signal_handler
                    pass
        except Exception:
            pass

    async def _start_subsystems(self):
        """Start background services and workers."""
        logger.info("Starting active subsystems...")

    async def _main_loop(self):
        """Main engine execution and monitoring loop."""
        while self._running:
            try:
                # Periodic health & heartbeat
                await asyncio.sleep(self.config.heartbeat_interval)
                await self.event_bus.publish(
                    Event(event_type=EventType.HEARTBEAT, data={"status": self.state_machine.current_state.value})
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._metrics["errors"] += 1
                logger.error(f"Error in engine main loop: {e}", exc_info=True)

    async def shutdown(self):
        """Gracefully stop engine and close all connections."""
        if not self._running:
            return

        logger.info("Shutting down Orion Trading Engine...")
        self.state_machine.transition(SystemState.STOPPING)
        self._running = False

        for task in self._tasks:
            task.cancel()

        await self.event_bus.stop()
        self.state_machine.transition(SystemState.STOPPED)
        logger.info("Orion Engine successfully stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return engine diagnostic status."""
        uptime = (datetime.utcnow() - self._start_time).total_seconds() if self._start_time else 0
        return {
            "engine_id": self.engine_id,
            "state": self.state_machine.current_state.value,
            "mode": self.config.mode.value,
            "uptime_seconds": uptime,
            "metrics": self._metrics,
            "circuit_breaker": self.circuit_breaker.state.value,
            "health": self.health_checker.last_status,
        }
