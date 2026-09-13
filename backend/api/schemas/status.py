from pydantic import BaseModel
from typing import Any

class SystemLimits(BaseModel):
    max_position_fraction: float
    max_portfolio_exposure: float
    max_daily_loss_fraction: float

class SystemStatus(BaseModel):
    banner: str
    mode: str
    execution_mode: str
    live_trading_enabled: bool
    autonomy_level: str
    limits: SystemLimits
    equity_history: list[float]
    trades: list[dict[str, Any]]
