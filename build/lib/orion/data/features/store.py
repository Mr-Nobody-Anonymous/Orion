"""Institutional Point-in-Time Feature Store and Drift Monitor.

Provides feature registry, point-in-time feature extraction without lookahead bias,
and real-time feature drift (Population Stability Index) detection.
Strictly in the Truth plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    feature_group: str  # e.g., "technical", "fundamental", "macro", "microstructure", "sentiment"
    description: str = ""
    version: int = 1
    source: str = "orion"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FeatureValue:
    feature_name: str
    entity_id: str  # e.g. "AAPL", "BTC-USDT"
    timestamp: datetime
    value: float
    vendor_release_time: datetime | None = None

    @property
    def effective_time(self) -> datetime:
        return self.vendor_release_time or self.timestamp


class FeatureDriftMonitor:
    """Monitors feature distribution drift using Population Stability Index (PSI)."""

    @staticmethod
    def calculate_psi(
        baseline: Sequence[float],
        target: Sequence[float],
        bins: int = 10,
    ) -> float:
        if not baseline or not target:
            return 0.0

        clean_base = [v for v in baseline if not math.isnan(v)]
        clean_target = [v for v in target if not math.isnan(v)]
        if len(clean_base) < 10 or len(clean_target) < 10:
            return 0.0

        sorted_base = sorted(clean_base)
        n_base = len(sorted_base)
        n_target = len(clean_target)

        # Quantile bin edges from baseline
        cutoffs = [sorted_base[int(i * (n_base - 1) / bins)] for i in range(1, bins)]

        def get_bin(val: float) -> int:
            for i, cut in enumerate(cutoffs):
                if val <= cut:
                    return i
            return len(cutoffs)

        base_counts = [0] * bins
        target_counts = [0] * bins

        for v in clean_base:
            base_counts[get_bin(v)] += 1

        for v in clean_target:
            target_counts[get_bin(v)] += 1

        psi = 0.0
        for b_cnt, t_cnt in zip(base_counts, target_counts):
            # Laplace smoothing
            p_base = (b_cnt + 1.0) / (n_base + bins)
            p_target = (t_cnt + 1.0) / (n_target + bins)
            psi += (p_target - p_base) * math.log(p_target / p_base)

        return float(psi)


class PointInTimeFeatureStore:
    """Manages feature definitions and point-in-time correct historical feature retrieval."""

    def __init__(self) -> None:
        self._definitions: dict[str, FeatureDefinition] = {}
        # Storage keyed by entity_id -> feature_name -> list of FeatureValue sorted by effective_time
        self._store: dict[str, dict[str, list[FeatureValue]]] = {}

    def register_feature(self, definition: FeatureDefinition) -> None:
        self._definitions[definition.name] = definition

    def record_feature(
        self,
        feature_name: str,
        entity_id: str,
        timestamp: datetime,
        value: float,
        vendor_release_time: datetime | None = None,
    ) -> None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if vendor_release_time and vendor_release_time.tzinfo is None:
            vendor_release_time = vendor_release_time.replace(tzinfo=timezone.utc)

        fv = FeatureValue(
            feature_name=feature_name,
            entity_id=entity_id,
            timestamp=timestamp,
            value=value,
            vendor_release_time=vendor_release_time,
        )
        self._store.setdefault(entity_id, {}).setdefault(feature_name, []).append(fv)

    def get_features_as_of(
        self,
        entity_id: str,
        feature_names: Sequence[str],
        as_of: datetime,
    ) -> dict[str, float | None]:
        """Returns feature values known strictly at or before `as_of`."""
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        entity_features = self._store.get(entity_id, {})
        result: dict[str, float | None] = {}

        for name in feature_names:
            series = entity_features.get(name, [])
            # Find the latest value whose effective_time <= as_of
            valid_values = [v.value for v in series if v.effective_time <= as_of]
            result[name] = valid_values[-1] if valid_values else None

        return result

    def get_feature_history(
        self,
        entity_id: str,
        feature_name: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[tuple[datetime, float]]:
        series = self._store.get(entity_id, {}).get(feature_name, [])
        out: list[tuple[datetime, float]] = []
        for v in series:
            t = v.effective_time
            if start and t < start:
                continue
            if end and t > end:
                continue
            out.append((t, v.value))
        out.sort(key=lambda x: x[0])
        return out
