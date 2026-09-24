"""Factor catalogue (P1-6).

Each factor is a self-contained, dependency-free computation that turns
a price/return series into a **z-scored long-short signal** in
``[-1, 1]``. The catalogue deliberately uses only public, well-known
factor definitions so a reader can verify every signal by hand.

The factors are:

- **value** — relative cheapness via the inverse of the trailing return
  (mean-reversion-tilted cheapness proxy).
- **momentum** — 12-month return excluding the most recent month, the
  classic Jegadeesh-Titman signal, with a short-window safety floor.
- **quality** — stability of returns: ``1 / (1 + stddev(returns))``.
- **size** — proxy via the average volume rank: low-volume = small.
- **low-volatility** — ``-stddev(returns)``, z-scored.
- **carry** — positive drift proxy: ``mean(returns) / stddev(returns)``.
- **growth** — second-difference of price (acceleration of trend).
- **profitability** — proxy: signed mean of return × stability.
- **term-structure** — return spread between short and long windows.
- **liquidity** — inverse of realised absolute return (a very simple
  Amihud-style proxy).
- **sentiment** — placeholder that maps a user-supplied sentiment score
  series into the same ``[-1, 1]`` range. If no series is provided, the
  factor returns ``0.0`` (so the catalogue works without external data).

All factors clamp to ``[-1, 1]`` and return ``NaN-equivalent`` (here
``float("nan")``) when the input is too short. Callers must check for
``math.isnan`` before using the signal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

__all__ = [
    "FactorDefinition",
    "FactorLibrary",
    "FactorSignal",
    "FACTOR_NAMES",
    "FACTOR_REGISTRY",
    "compute_factor_signal",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _returns(prices: Sequence[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        if prev == 0:
            out.append(0.0)
            continue
        out.append(cur / prev - 1.0)
    return out


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _zscore_clip(values: Sequence[float]) -> list[float]:
    """Centre & rescale to ``[-1, 1]``; robust to zero dispersion."""
    finite = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    if not finite:
        return [float("nan")] * len(values)
    mean = sum(finite) / len(finite)
    sd = _stdev(finite) or 1.0
    return [max(-1.0, min(1.0, (v - mean) / (3.0 * sd))) for v in values]


# ---------------------------------------------------------------------------
# Factor implementations
# ---------------------------------------------------------------------------


def _factor_value(prices: Sequence[float]) -> float:
    if len(prices) < 4:
        return float("nan")
    rets = _returns(prices[-63:]) if len(prices) > 63 else _returns(prices)
    if not rets:
        return float("nan")
    # Cheapness ≈ low cumulative return; high = expensive.
    cum = sum(rets)
    return max(-1.0, min(1.0, -cum / max(1e-9, abs(cum) + _stdev(rets))))


def _factor_momentum(prices: Sequence[float]) -> float:
    if len(prices) < 21:
        return float("nan")
    # Jegadeesh-Titman 12-1: skip the most recent month.
    lookback_end = len(prices) - 21
    if lookback_end <= 0:
        return float("nan")
    start = prices[0]
    end = prices[lookback_end]
    if start <= 0:
        return float("nan")
    twelve_minus_one = end / start - 1.0
    return max(-1.0, min(1.0, twelve_minus_one / 0.5))


def _factor_quality(prices: Sequence[float]) -> float:
    rets = _returns(prices)
    if len(rets) < 4:
        return float("nan")
    sd = _stdev(rets)
    if sd == 0:
        return 0.0
    return max(-1.0, min(1.0, 1.0 / (1.0 + sd * 50.0)))


def _factor_size(prices: Sequence[float]) -> float:
    """Size proxy: low absolute return magnitude = small / illiquid."""
    rets = _returns(prices)
    if len(rets) < 4:
        return float("nan")
    avg_abs = sum(abs(r) for r in rets) / len(rets)
    if avg_abs == 0:
        return 0.0
    return max(-1.0, min(1.0, -math.log(avg_abs * 1000.0 + 1.0) / 4.0))


def _factor_low_vol(prices: Sequence[float]) -> float:
    rets = _returns(prices)
    if len(rets) < 4:
        return float("nan")
    sd = _stdev(rets)
    return max(-1.0, min(1.0, -sd * 50.0))


def _factor_carry(prices: Sequence[float]) -> float:
    rets = _returns(prices)
    if len(rets) < 4:
        return float("nan")
    mean = _mean(rets)
    sd = _stdev(rets)
    if sd == 0:
        return 0.0
    sharpe_like = mean / sd
    return max(-1.0, min(1.0, sharpe_like / 2.0))


def _factor_growth(prices: Sequence[float]) -> float:
    if len(prices) < 6:
        return float("nan")
    # Acceleration: average of second differences, normalised.
    diffs = [prices[i] / prices[i - 1] - 1.0 for i in range(2, len(prices))]
    if not diffs:
        return float("nan")
    accel = (diffs[-1] - diffs[0]) / max(1, len(diffs) - 1)
    return max(-1.0, min(1.0, accel * 100.0))


def _factor_profitability(prices: Sequence[float]) -> float:
    rets = _returns(prices)
    if len(rets) < 4:
        return float("nan")
    mean = _mean(rets)
    sd = _stdev(rets)
    if sd == 0:
        return 0.0
    return max(-1.0, min(1.0, mean / (sd + 1e-9) / 3.0))


def _factor_term_structure(prices: Sequence[float]) -> float:
    if len(prices) < 30:
        return float("nan")
    short = sum(_returns(prices[-10:])) if len(prices) >= 11 else 0.0
    long = sum(_returns(prices[-30:])) if len(prices) >= 31 else 0.0
    spread = short - long / 3.0  # long-window averaged to per-bar scale
    return max(-1.0, min(1.0, spread * 50.0))


def _factor_liquidity(prices: Sequence[float]) -> float:
    rets = _returns(prices)
    if len(rets) < 4:
        return float("nan")
    # Amihud-style proxy: high |return| per unit price = illiquid.
    illiquidity = sum(abs(r) for r in rets) / max(1e-9, _mean(prices))
    return max(-1.0, min(1.0, -illiquidity * 100.0))


def _factor_sentiment(prices: Sequence[float], *, sentiment_scores: Sequence[float] = ()) -> float:
    if not sentiment_scores:
        return 0.0
    clipped = _zscore_clip(sentiment_scores)
    if not clipped:
        return 0.0
    return float(clipped[-1])


# ---------------------------------------------------------------------------
# Catalogue wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FactorSignal:
    """A single factor's value plus provenance."""

    name: str
    value: float
    lookback: int
    description: str
    extra: Mapping[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "name": self.name,
            "value": (
                float("nan")
                if isinstance(self.value, float) and math.isnan(self.value)
                else self.value
            ),
            "lookback": self.lookback,
            "description": self.description,
        }
        if self.extra:
            out["extra"] = dict(self.extra)
        return out


@dataclass(frozen=True, slots=True)
class FactorDefinition:
    """Definition of a single factor: name, function, description, lookback."""

    name: str
    description: str
    lookback: int
    compute: Callable[..., float]

    def evaluate(self, prices: Sequence[float], **kwargs) -> FactorSignal:
        value = self.compute(prices, **kwargs)
        return FactorSignal(
            name=self.name,
            value=value,
            lookback=self.lookback,
            description=self.description,
        )


class FactorLibrary:
    """Container of factor definitions; lookup by name and iteration."""

    def __init__(self, factors: Sequence[FactorDefinition]):
        if not factors:
            raise ValueError("FactorLibrary requires at least one factor")
        names = [f.name for f in factors]
        if len(set(names)) != len(names):
            raise ValueError("duplicate factor names in library")
        self._factors: dict[str, FactorDefinition] = {f.name: f for f in factors}

    def __iter__(self):
        return iter(self._factors.values())

    def __len__(self) -> int:
        return len(self._factors)

    def names(self) -> tuple[str, ...]:
        return tuple(self._factors)

    def get(self, name: str) -> FactorDefinition:
        try:
            return self._factors[name]
        except KeyError as error:
            raise KeyError(f"unknown factor: {name!r}") from error


FACTOR_REGISTRY: FactorLibrary = FactorLibrary(
    [
        FactorDefinition(
            "value",
            "Long cheap assets (low cumulative return), short expensive ones.",
            lookback=63,
            compute=_factor_value,
        ),
        FactorDefinition(
            "momentum",
            "12-month return excluding the most recent month (Jegadeesh-Titman).",
            lookback=252,
            compute=_factor_momentum,
        ),
        FactorDefinition(
            "quality",
            "Stability of returns: 1 / (1 + stddev(returns)).",
            lookback=60,
            compute=_factor_quality,
        ),
        FactorDefinition(
            "size",
            "Size proxy via average absolute return magnitude (smaller = lower).",
            lookback=60,
            compute=_factor_size,
        ),
        FactorDefinition(
            "low-volatility",
            "Low realised volatility: -zscore(stddev(returns)).",
            lookback=60,
            compute=_factor_low_vol,
        ),
        FactorDefinition(
            "carry",
            "Sharpe-like drift: mean(returns) / stddev(returns).",
            lookback=60,
            compute=_factor_carry,
        ),
        FactorDefinition(
            "growth",
            "Acceleration of the price series (second-difference).",
            lookback=20,
            compute=_factor_growth,
        ),
        FactorDefinition(
            "profitability",
            "Risk-adjusted drift proxy (mean / stddev).",
            lookback=60,
            compute=_factor_profitability,
        ),
        FactorDefinition(
            "term-structure",
            "Short-window minus long-window return (per-bar normalised).",
            lookback=30,
            compute=_factor_term_structure,
        ),
        FactorDefinition(
            "liquidity",
            "Amihud-style illiquidity, inverted to a signal.",
            lookback=60,
            compute=_factor_liquidity,
        ),
        FactorDefinition(
            "sentiment",
            "External sentiment score clipped to [-1, 1].",
            lookback=0,
            compute=_factor_sentiment,
        ),
    ]
)

FACTOR_NAMES: tuple[str, ...] = FACTOR_REGISTRY.names()


def compute_factor_signal(
    name: str,
    prices: Sequence[float],
    **kwargs,
) -> FactorSignal:
    """Compute a single factor by name; raises ``KeyError`` if unknown."""
    return FACTOR_REGISTRY.get(name).evaluate(prices, **kwargs)
