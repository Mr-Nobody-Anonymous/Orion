"""Agent framework adapters and patterns."""

from __future__ import annotations

from .a_evolve import AEvolveAdapter
from .agentic_trading import AgenticTradingAdapter
from .evolver import EvolverAdapter
from .hermes import HermesMemoryAdapter
from .quantmuse import QuantMuseAdapter
from .vibe_trading import VibeTradingAdapter

__all__ = [
    "AEvolveAdapter",
    "AgenticTradingAdapter",
    "EvolverAdapter",
    "HermesMemoryAdapter",
    "QuantMuseAdapter",
    "VibeTradingAdapter",
]
