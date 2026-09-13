"""ORION Financial ML Features Engine.

Provides institutional-grade feature engineering for financial machine learning.
Implements triple-barrier labeling, fractional differentiation,
structural break detection, and microstructure features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TripleBarrierLabel:
    """Label from the triple-barrier method."""

    index: int
    label: int  # 1 = upper hit, -1 = lower hit, 0 = vertical hit
    return_pct: float
    time_to_hit: int


class FeatureEngineeringEngine:
    """Financial ML feature engineering toolkit."""

    @staticmethod
    def get_triple_barriers(
        prices: Sequence[float],
        volatility: Sequence[float],
        pt_sl: tuple[float, float] = (1.0, 1.0),
        t_events: Sequence[int] | None = None,
        max_holding_period: int = 10,
        min_return: float = 0.001,
    ) -> list[TripleBarrierLabel]:
        """Apply the Triple-Barrier Method for ML labeling.

        Args:
            prices: Price series.
            volatility: Daily volatility series (used to scale barriers).
            pt_sl: Profit taking and stop loss multipliers.
            t_events: Indices of events to label (e.g., CUSUM filter events).
            max_holding_period: Vertical barrier (time limit).
            min_return: Minimum return threshold to trigger.

        Returns:
            List of TripleBarrierLabel objects.
        """
        if t_events is None:
            t_events = list(range(len(prices)))

        labels = []
        n = len(prices)

        for i in t_events:
            if i >= n - 1:
                continue

            pt_mult, sl_mult = pt_sl
            vol = volatility[i] if i < len(volatility) else 0.01

            upper_barrier = prices[i] * (1 + pt_mult * vol)
            lower_barrier = prices[i] * (1 - sl_mult * vol)

            vertical_barrier = min(i + max_holding_period, n - 1)

            hit_label = 0
            hit_index = vertical_barrier

            # Scan forward to find the first barrier hit
            for j in range(i + 1, vertical_barrier + 1):
                if prices[j] >= upper_barrier:
                    hit_label = 1
                    hit_index = j
                    break
                elif prices[j] <= lower_barrier:
                    hit_label = -1
                    hit_index = j
                    break

            # Filter by min return if vertical barrier hit
            if hit_label == 0:
                ret = (prices[hit_index] - prices[i]) / prices[i]
                if ret > min_return:
                    hit_label = 1
                elif ret < -min_return:
                    hit_label = -1

            ret = (prices[hit_index] - prices[i]) / prices[i]
            labels.append(TripleBarrierLabel(
                index=i,
                label=hit_label,
                return_pct=ret,
                time_to_hit=hit_index - i,
            ))

        return labels

    @staticmethod
    def frac_diff_ffd(
        series: Sequence[float],
        d: float = 0.4,
        tau: float = 1e-4,
    ) -> list[float]:
        """Fractional differentiation using Fixed-Width Window (FFD).

        Args:
            series: Input time series (prices, log prices).
            d: Fractional differencing degree (0 to 1).
            tau: Weight threshold to determine window size.
        """
        if not series:
            return []

        # Calculate weights
        weights = [1.0]
        k = 1
        while True:
            w = -weights[-1] * (d - k + 1) / k
            if abs(w) < tau:
                break
            weights.append(w)
            k += 1

        window = len(weights)
        weights.reverse()  # Oldest weight first

        diff_series = []
        # Need at least 'window' elements to start
        for i in range(len(series)):
            if i < window - 1:
                diff_series.append(float("nan"))
                continue

            val = 0.0
            for j in range(window):
                val += weights[j] * series[i - window + 1 + j]
            diff_series.append(val)

        return diff_series

    @staticmethod
    def roll_measure(
        high: Sequence[float],
        low: Sequence[float],
        close: Sequence[float],
    ) -> float:
        """Calculate Roll's measure for effective bid-ask spread."""
        if len(close) < 3:
            return 0.0

        returns = [(close[i] - close[i - 1]) for i in range(1, len(close))]
        autocov = 0.0
        mean_r = sum(returns) / len(returns)

        for i in range(1, len(returns)):
            autocov += (returns[i] - mean_r) * (returns[i - 1] - mean_r)

        autocov = autocov / (len(returns) - 1)

        if autocov < 0:
            return 2 * math.sqrt(-autocov)
        return 0.0
