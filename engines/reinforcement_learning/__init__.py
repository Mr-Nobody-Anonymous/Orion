"""ORION Canonical Reinforcement Learning Engine."""

from __future__ import annotations

from typing import Any, Mapping
from orion.data.contracts import Asset, Signal


class ReinforcementLearningEngine:
    """Unified RL engine backed by FinRL and FinRL-Meta environments."""

    def evaluate_policy_step(
        self,
        asset: Asset,
        features: Mapping[str, float],
    ) -> Signal:
        from adapters.finrl import FinRLAdapter

        adapter = FinRLAdapter()
        return adapter.evaluate_policy(asset, features)
