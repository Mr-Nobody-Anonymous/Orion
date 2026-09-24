"""Timestamp normalization, bad-tick filtering, and missing-data policy.

This is the layer between a raw vendor feed and the canonical ORION
contracts. Every function is pure and stdlib-only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Sequence


class MissingDataPolicy(str, Enum):
    DROP = "drop"
    FORWARD_FILL = "ffill"
    BACKWARD_FILL = "bfill"


def to_utc(ts: datetime) -> datetime:
    """Coerce any datetime to a tz-aware UTC value."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def sort_by_time(rows: Sequence[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    return sorted(rows, key=lambda r: to_utc(r[0]))


def fill_gaps(
    rows: Sequence[tuple[datetime, float]],
    policy: MissingDataPolicy = MissingDataPolicy.FORWARD_FILL,
) -> list[tuple[datetime, float]]:
    """Apply a missing-data policy to a sorted (time, value) sequence.

    The function does *not* synthesise new timestamps; it only handles
    ``None`` or ``NaN`` values.
    """
    if not rows:
        return []
    out: list[tuple[datetime, float]] = []
    last: float | None = None
    for ts, v in rows:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            if policy is MissingDataPolicy.DROP:
                continue
            if policy is MissingDataPolicy.FORWARD_FILL:
                if last is None:
                    continue
                out.append((to_utc(ts), last))
            elif policy is MissingDataPolicy.BACKWARD_FILL:
                out.append((to_utc(ts), float("nan")))
        else:
            out.append((to_utc(ts), float(v)))
            last = float(v)
    # second pass for bfill on NaN placeholders
    if policy is MissingDataPolicy.BACKWARD_FILL:
        next_v: float | None = None
        for i in range(len(out) - 1, -1, -1):
            v = out[i][1]
            if math.isnan(v):
                if next_v is not None:
                    out[i] = (out[i][0], next_v)
            else:
                next_v = v
        out = [(t, v) for t, v in out if not math.isnan(v)]
    return out


@dataclass(frozen=True, slots=True)
class BadTickConfig:
    max_return_sigma: float = 6.0
    min_price: float = 1e-6
    min_volume: float = 0.0
    max_price_jump_ratio: float = 4.0  # absolute price > 4x previous = bad tick


@dataclass(frozen=True, slots=True)
class BadTickResult:
    cleaned: list[tuple[datetime, float]]
    rejected: list[tuple[datetime, float, str]]


def _rolling_stdev(values: Sequence[float], lookback: int) -> list[float]:
    out: list[float] = [0.0] * len(values)
    for i in range(1, len(values)):
        window = values[max(0, i - lookback) : i]
        if len(window) < 2:
            out[i] = 0.0
        else:
            out[i] = statistics.stdev(window) if len(window) >= 2 else 0.0
    return out


def filter_bad_ticks(
    rows: Sequence[tuple[datetime, float]],
    volumes: Sequence[float] | None = None,
    config: BadTickConfig | None = None,
) -> BadTickResult:
    """Reject impossible or wildly out-of-line observations.

    Rules:
      1. price <= 0                              -> reject
      2. price > 4x previous AND > 4x following -> reject
      3. |return| > max_return_sigma * stdev    -> reject
      4. volume < 0                             -> reject (if provided)
    """
    cfg = config or BadTickConfig()
    rows = sort_by_time(rows)
    cleaned: list[tuple[datetime, float]] = []
    rejected: list[tuple[datetime, float, str]] = []

    if not rows:
        return BadTickResult(cleaned=[], rejected=[])

    prices = [r[1] for r in rows]
    sd = _rolling_stdev(prices, lookback=20)
    # returns in price space
    returns: list[float] = [0.0]
    for i in range(1, len(prices)):
        if prices[i - 1] != 0:
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
        else:
            returns.append(0.0)

    for i, (ts, px) in enumerate(rows):
        reason: str | None = None
        if not math.isfinite(px) or px < cfg.min_price:
            reason = f"non_positive_price<{cfg.min_price}"
        elif (
            i > 0
            and i < len(rows) - 1
            and px > cfg.max_price_jump_ratio * max(prices[i - 1], 1e-9)
            and px > cfg.max_price_jump_ratio * max(prices[i + 1], 1e-9)
        ):
            reason = "isolated_price_spike"
        elif (
            sd[i] > 0
            and abs(returns[i]) > cfg.max_return_sigma * sd[i] / max(prices[i - 1] if i > 0 else px, 1e-9)
        ):
            reason = f"return_>{cfg.max_return_sigma}sigma"
        elif volumes is not None and volumes[i] < cfg.min_volume:
            reason = "negative_volume"
        if reason is not None:
            rejected.append((ts, px, reason))
        else:
            cleaned.append((ts, px))
    return BadTickResult(cleaned=cleaned, rejected=rejected)
