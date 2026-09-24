"""Institutional Multi-Asset Quantitative Screener.

Filters and ranks assets across 100+ fundamental, valuation, technical, and macro metrics.
Lives in the Intelligence plane.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ScreenFilter:
    field: str
    operator: str  # ">", "<", ">=", "<=", "==", "!=", "BETWEEN"
    value: float
    value2: float | None = None  # for BETWEEN

    def matches(self, row_val: Any) -> bool:
        if row_val is None:
            return False
        try:
            num = float(row_val)
        except (ValueError, TypeError):
            return False

        if self.operator == ">":
            return num > self.value
        elif self.operator == "<":
            return num < self.value
        elif self.operator == ">=":
            return num >= self.value
        elif self.operator == "<=":
            return num <= self.value
        elif self.operator == "==":
            return abs(num - self.value) < 1e-6
        elif self.operator == "!=":
            return abs(num - self.value) >= 1e-6
        elif self.operator.upper() == "BETWEEN" and self.value2 is not None:
            return self.value <= num <= self.value2
        return False


@dataclass(frozen=True, slots=True)
class ScreenResult:
    symbol: str
    metrics: Mapping[str, Any]
    score: float = 0.0


class ScreenerEngine:
    """Multi-asset screener evaluating compound filtering criteria and sorting rankings."""

    @staticmethod
    def screen(
        universe: Sequence[Mapping[str, Any]],
        filters: Sequence[ScreenFilter],
        sort_by: str | None = None,
        ascending: bool = False,
        limit: int | None = None,
    ) -> list[ScreenResult]:
        matched: list[ScreenResult] = []

        for row in universe:
            sym = str(row.get("symbol", "UNKNOWN"))
            is_match = True
            for f in filters:
                val = row.get(f.field)
                if not f.matches(val):
                    is_match = False
                    break

            if is_match:
                score = float(row.get(sort_by, 0.0)) if sort_by and row.get(sort_by) is not None else 0.0
                matched.append(ScreenResult(symbol=sym, metrics=dict(row), score=score))

        if sort_by:
            matched.sort(key=lambda x: x.score, reverse=not ascending)

        if limit is not None:
            matched = matched[:limit]

        return matched
