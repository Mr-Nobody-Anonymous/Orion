from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AIMode(str, Enum):
    LOCAL = "local"
    HYBRID = "hybrid"
    CLOUD = "cloud"


@dataclass(frozen=True, slots=True)
class OrionConfig:
    mode: AIMode = AIMode.LOCAL
    execution_mode: str = "simulation"
    autonomy_level: int = 0
    live_trading_enabled: bool = False
    max_position_fraction: float = 0.10
    max_portfolio_exposure: float = 1.0
    max_daily_loss_fraction: float = 0.02

    def validate(self) -> None:
        if not 0 <= self.autonomy_level <= 4:
            raise ValueError("autonomy_level must be between 0 and 4")
        if self.live_trading_enabled and self.execution_mode != "live":
            raise ValueError("live_trading_enabled requires live execution_mode")
        if self.execution_mode == "live" and not self.live_trading_enabled:
            raise ValueError("live execution is disabled by default")
        for name, value in (
            ("max_position_fraction", self.max_position_fraction),
            ("max_portfolio_exposure", self.max_portfolio_exposure),
            ("max_daily_loss_fraction", self.max_daily_loss_fraction),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
