from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class QuantSignal:
    name: str
    score: Decimal
    evidence: tuple[str, ...]


def momentum_signal(prices: Sequence[float], lookback: int = 5) -> QuantSignal:
    if len(prices) <= lookback or prices[0] <= 0:
        raise ValueError("prices must contain more than lookback positive observations")
    return_pct = Decimal(str(prices[-1] / prices[-1 - lookback] - 1))
    direction = "positive" if return_pct >= 0 else "negative"
    return QuantSignal("momentum", return_pct, (f"{lookback}-period return is {direction}",))
