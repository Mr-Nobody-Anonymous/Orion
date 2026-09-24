"""
Orion State Machine
Tracks system and subsystem states across lifecycle stages.
"""

import logging
from enum import Enum, auto
from typing import Set, Dict, Optional, Callable

logger = logging.getLogger(__name__)


class SystemState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class StateMachine:
    """
    Manages deterministic transitions between valid system states.
    """

    ALLOWED_TRANSITIONS: Dict[SystemState, Set[SystemState]] = {
        SystemState.UNINITIALIZED: {SystemState.INITIALIZING, SystemState.ERROR},
        SystemState.INITIALIZING: {SystemState.READY, SystemState.RUNNING, SystemState.ERROR},
        SystemState.READY: {SystemState.RUNNING, SystemState.STOPPING, SystemState.ERROR},
        SystemState.RUNNING: {SystemState.PAUSED, SystemState.DEGRADED, SystemState.STOPPING, SystemState.ERROR},
        SystemState.PAUSED: {SystemState.RUNNING, SystemState.STOPPING, SystemState.ERROR},
        SystemState.DEGRADED: {SystemState.RUNNING, SystemState.PAUSED, SystemState.STOPPING, SystemState.ERROR},
        SystemState.STOPPING: {SystemState.STOPPED, SystemState.ERROR},
        SystemState.STOPPED: {SystemState.INITIALIZING},
        SystemState.ERROR: {SystemState.INITIALIZING, SystemState.STOPPED},
    }

    def __init__(self, initial_state: SystemState = SystemState.UNINITIALIZED):
        self._current_state = initial_state
        self._on_transition_hooks: Dict[SystemState, list] = {}

    @property
    def current_state(self) -> SystemState:
        return self._current_state

    def is_state(self, state: SystemState) -> bool:
        return self._current_state == state

    def transition(self, target_state: SystemState) -> bool:
        """Attempt to transition to a new state."""
        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        if target_state not in allowed:
            logger.warning(
                f"Invalid state transition: Cannot transition from {self._current_state.value} to {target_state.value}"
            )
            return False

        prev = self._current_state
        self._current_state = target_state
        logger.info(f"System state transitioned: {prev.value} -> {target_state.value}")

        hooks = self._on_transition_hooks.get(target_state, [])
        for hook in hooks:
            try:
                hook(prev, target_state)
            except Exception as e:
                logger.error(f"Error in transition hook for {target_state.value}: {e}")

        return True

    def add_transition_hook(self, target_state: SystemState, hook: Callable[[SystemState, SystemState], None]):
        """Register callback for when target state is reached."""
        if target_state not in self._on_transition_hooks:
            self._on_transition_hooks[target_state] = []
        self._on_transition_hooks[target_state].append(hook)
