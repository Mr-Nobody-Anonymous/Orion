"""Pure-stdlib statistical signals.

These are short, dependency-free factor implementations. They are
deterministic, easy to test, and always available. Heavier implementations
(e.g. Kronos, Time-Series-Library) live in the optional worker layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, pstdev
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Signal:
    name: str
    value: float
    direction: str  # "bullish" | "bearish" | "neutral"
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "direction": self.direction,
            "evidence": list(self.evidence),
        }


def _returns(prices: Sequence[float]) -> list[float]:
    if len(prices) < 2:
        return []
    return [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]


def momentum(prices: Sequence[float], *, lookback: int = 5) -> Signal:
    if len(prices) <= lookback or prices[-1] <= 0 or prices[-1 - lookback] <= 0:
        raise ValueError("prices must be longer than lookback and positive")
    change = prices[-1] / prices[-1 - lookback] - 1
    direction = "bullish" if change > 0 else "bearish" if change < 0 else "neutral"
    return Signal("momentum", change, direction, (f"{lookback}-period return = {change:.4f}",))


def mean_reversion(prices: Sequence[float], *, window: int = 20) -> Signal:
    if len(prices) < 3 or prices[-1] <= 0:
        raise ValueError("prices must contain at least 3 positive observations")
    window = min(window, len(prices))
    rolling = mean(prices[-window:])
    deviation = (rolling - prices[-1]) / prices[-1]
    direction = "bullish" if deviation > 0 else "bearish" if deviation < 0 else "neutral"
    return Signal("mean_reversion", deviation, direction, (f"rolling mean deviation = {deviation:.4f}",))


def realized_volatility(prices: Sequence[float], *, window: int = 20) -> Signal:
    if len(prices) < 2:
        raise ValueError("prices must contain at least 2 observations")
    returns = _returns(prices)
    window_returns = returns[-window:] if len(returns) > window else returns
    if len(window_returns) < 2:
        vol = 0.0
    else:
        vol = pstdev(window_returns)
    return Signal("realized_volatility", vol, "neutral", (f"window={window}",))


def zscore(prices: Sequence[float], *, window: int = 20) -> Signal:
    if len(prices) < 2 or prices[-1] <= 0:
        raise ValueError("prices must contain at least 2 positive observations")
    window = min(window, len(prices))
    values = prices[-window:]
    m = mean(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    z = (prices[-1] - m) / sd if sd > 0 else 0.0
    direction = "bearish" if z > 1.5 else "bullish" if z < -1.5 else "neutral"
    return Signal("zscore", z, direction, (f"window={window}",))


def moving_average_crossover(prices: Sequence[float], *, fast: int = 5, slow: int = 20) -> Signal:
    if len(prices) < slow or prices[-1] <= 0:
        raise ValueError("not enough prices for the requested slow window")
    fast_ma = mean(prices[-fast:])
    slow_ma = mean(prices[-slow:])
    diff = (fast_ma - slow_ma) / slow_ma
    direction = "bullish" if diff > 0 else "bearish" if diff < 0 else "neutral"
    return Signal("ma_crossover", diff, direction, (f"fast={fast}; slow={slow}",))


def bollinger_position(prices: Sequence[float], *, window: int = 20, num_std: float = 2.0) -> Signal:
    if len(prices) < 2 or prices[-1] <= 0:
        raise ValueError("prices must contain at least 2 positive observations")
    window = min(window, len(prices))
    values = prices[-window:]
    m = mean(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    upper = m + num_std * sd
    lower = m - num_std * sd
    if upper == lower:
        position = 0.5
    else:
        position = (prices[-1] - lower) / (upper - lower)
    direction = "bearish" if position > 0.8 else "bullish" if position < 0.2 else "neutral"
    return Signal("bollinger", position, direction, (f"position={position:.2f}",))


def rsi(prices: Sequence[float], *, period: int = 14) -> Signal:
    if len(prices) <= period or prices[-1] <= 0:
        raise ValueError("not enough prices for the requested RSI period")
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    window = changes[-period:]
    gains = [max(0.0, c) for c in window]
    losses = [max(0.0, -c) for c in window]
    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0
    if avg_loss == 0:
        rsi_value = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_value = 100.0 - (100.0 / (1.0 + rs))
    direction = "bearish" if rsi_value > 70 else "bullish" if rsi_value < 30 else "neutral"
    return Signal("rsi", rsi_value, direction, (f"period={period}",))


def sharpe(returns: Sequence[float], *, risk_free: float = 0.0, periods_per_year: int = 252) -> Signal:
    if len(returns) < 2:
        raise ValueError("at least two returns are required")
    avg = mean(returns) - risk_free / periods_per_year
    sd = pstdev(returns)
    ratio = (avg / sd) * sqrt(periods_per_year) if sd > 0 else 0.0
    direction = "bullish" if ratio > 1 else "bearish" if ratio < 0 else "neutral"
    return Signal("sharpe", ratio, direction, (f"periods_per_year={periods_per_year}",))


def signal_to_decimal(signal: Signal) -> Decimal:
    return Decimal(str(signal.value))


def aggregate_score(signals: Sequence[Signal]) -> float:
    if not signals:
        raise ValueError("signals must be non-empty")
    weights = {
        "momentum": 0.3,
        "mean_reversion": 0.15,
        "ma_crossover": 0.2,
        "zscore": 0.1,
        "bollinger": 0.05,
        "rsi": 0.1,
        "realized_volatility": -0.1,
        "sharpe": 0.1,
    }
    total = 0.0
    for s in signals:
        sign = 1.0 if s.direction == "bullish" else -1.0 if s.direction == "bearish" else 0.0
        total += sign * weights.get(s.name, 0.0) * (abs(s.value) if s.name != "realized_volatility" else s.value)
    return total
