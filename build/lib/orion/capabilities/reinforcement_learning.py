"""Reinforcement learning policy and market environment simulation capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class RLPolicyRequest:
    """Request to train or evaluate a reinforcement learning policy."""

    algorithm: str  # PPO, A2C, DDPG, SAC, DQN
    state_dimension: int
    action_dimension: int
    episodes: int = 100
    learning_rate: float = 0.0003
    gamma: float = 0.99
    reward_metric: str = "sharpe_ratio"


@dataclass(frozen=True, slots=True)
class RLExperimentResult:
    """Output of an RL training or evaluation run."""

    provider_name: str
    algorithm: str
    cumulative_reward: float
    mean_episode_length: float
    final_sharpe: float
    policy_weights_ref: str
    convergence_status: str
    metrics_history: dict[str, Sequence[float]] = field(default_factory=dict)


class ReinforcementLearningProvider(BaseCapabilityProvider):
    """Abstract interface for RL algorithmic exploration (FinRL / FinRL-Meta / native)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.REINFORCEMENT_LEARNING

    @abstractmethod
    def train_policy(
        self,
        request: RLPolicyRequest,
        price_history: Sequence[float],
    ) -> RLExperimentResult:
        """Train or benchmark an RL agent on market simulation data."""
