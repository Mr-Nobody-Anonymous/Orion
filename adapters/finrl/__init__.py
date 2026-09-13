"""FinRL Reinforcement Learning Adapter for ORION.

Translates FinRL and FinRL-Meta environments and trained DRL agents (PPO, DDPG, SAC)
into canonical Orion signals and target portfolio weights.
"""

from __future__ import annotations

from typing import Any, Mapping
from orion.data.contracts import Asset, Signal


class FinRLAdapter:
    """Canonical adapter facade for FinRL and FinRL-Meta."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "FinRL"
        self.version = "0.3.6"

    def evaluate_policy(
        self,
        asset: Asset,
        state_features: Mapping[str, float],
    ) -> Signal:
        """Evaluate DRL policy on current state features to emit an actionable signal."""
        from orion.integrations.trading.finrl import FinRLTradingAdapter

        adapter = FinRLTradingAdapter()
        return adapter.evaluate_step(asset, state_features)
