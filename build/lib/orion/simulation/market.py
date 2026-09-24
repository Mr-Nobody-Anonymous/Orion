from __future__ import annotations

from dataclasses import dataclass
from random import Random
from statistics import mean, pstdev
from typing import Sequence


@dataclass(frozen=True, slots=True)
class SimulationResult:
    paths: tuple[tuple[float, ...], ...]
    terminal_mean: float
    terminal_p05: float
    terminal_p95: float
    seed: int


def bootstrap_market_paths(prices: Sequence[float], *, paths: int = 100, horizon: int = 20, seed: int = 7) -> SimulationResult:
    if len(prices) < 3 or any(price <= 0 for price in prices):
        raise ValueError("at least three positive prices are required")
    if paths < 1 or horizon < 1:
        raise ValueError("paths and horizon must be positive")
    returns = [prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))]
    random = Random(seed)
    generated: list[tuple[float, ...]] = []
    for _ in range(paths):
        path = [float(prices[-1])]
        for _ in range(horizon):
            path.append(path[-1] * (1 + random.choice(returns)))
        generated.append(tuple(path))
    terminals = sorted(path[-1] for path in generated)
    lower_index = max(0, round((len(terminals) - 1) * 0.05))
    upper_index = min(len(terminals) - 1, round((len(terminals) - 1) * 0.95))
    return SimulationResult(tuple(generated), mean(terminals), terminals[lower_index], terminals[upper_index], seed)
