"""Backtesting and quantitative simulation capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class BacktestRequest:
    """Request to backtest a strategy rule set or signal series."""

    strategy_name: str
    symbol: str
    prices: Sequence[float]
    signals: Sequence[float] | None = None
    initial_capital: float = 100_000.0
    cost_per_trade_bps: float = 5.0  # 5 bps
    slippage_bps: float = 3.0
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParameterSweepRequest:
    """Request to execute a high-speed parameter grid search."""

    strategy_name: str
    symbol: str
    prices: Sequence[float]
    param_grid: dict[str, Sequence[Any]]
    target_metric: str = "sharpe_ratio"


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Standardized performance output of a backtesting engine."""

    provider_name: str
    strategy_name: str
    symbol: str
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    profit_factor: float
    equity_curve: tuple[float, ...]
    engine_metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "total_return_pct": self.total_return_pct,
            "cagr_pct": self.cagr_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate_pct": self.win_rate_pct,
            "total_trades": self.total_trades,
            "profit_factor": self.profit_factor,
            "equity_curve": list(self.equity_curve),
            "engine_metadata": self.engine_metadata,
        }


@dataclass(frozen=True, slots=True)
class SweepResult:
    """Output of a multi-parameter sweep."""

    provider_name: str
    total_combinations: int
    best_parameters: dict[str, Any]
    best_metric_value: float
    top_results: tuple[dict[str, Any], ...]


class BacktestProvider(BaseCapabilityProvider):
    """Abstract interface for vectorized, event-driven, and institutional backtesting engines."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.BACKTESTING

    @abstractmethod
    def run_backtest(self, request: BacktestRequest) -> BacktestResult:
        """Execute a backtest on the given price and signal series."""

    def run_parameter_sweep(self, request: ParameterSweepRequest) -> SweepResult:
        """Optionally execute a parameter sweep."""
        # Default naive sweep using single runs
        return SweepResult(
            provider_name=self.name,
            total_combinations=1,
            best_parameters={},
            best_metric_value=0.0,
            top_results=(),
        )
