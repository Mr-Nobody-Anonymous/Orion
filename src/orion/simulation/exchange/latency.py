"""Latency and market-impact models.

Both models are pure functions of their inputs and easy to swap.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class LatencyConfig:
    """Deterministic base latency + Gaussian jitter (microseconds)."""

    base_us: int = 250
    jitter_us: int = 100
    seed: int | None = None

    def sample_us(self) -> int:
        if self.seed is None:
            jitter = int(random.gauss(0.0, self.jitter_us))
        else:
            rng = random.Random(self.seed)
            jitter = int(rng.gauss(0.0, self.jitter_us))
        return max(0, self.base_us + jitter)


@dataclass(frozen=True, slots=True)
class MarketImpactConfig:
    """Square-root market impact: ``eta * sigma * sqrt(qty / ADV)``.

    ``sigma`` is the daily return volatility of the asset; ``ADV`` is
    the average daily volume.  ``eta`` is a calibration constant.  This
    is a deliberately simple model: realistic enough to penalise large
    orders without pretending to be a microstructure simulator.
    """

    eta: float = 0.1
    sigma: float = 0.02
    adv: float = 1_000_000.0
    min_impact_bps: float = 0.0  # floor for tiny orders

    def impact(self, quantity: float, side: str) -> float:
        if quantity <= 0 or self.adv <= 0:
            return 0.0
        ratio = quantity / self.adv
        bps = self.eta * self.sigma * math.sqrt(max(ratio, 1e-9)) * 10_000.0
        bps = max(bps, self.min_impact_bps)
        # Buyers pay the impact (positive); sellers receive it (negative)
        return bps if side.lower() == "buy" else -bps

    def impact_decimal(self, quantity: Decimal, side: str) -> Decimal:
        return Decimal(str(self.impact(float(quantity), side))) / Decimal("10000")
