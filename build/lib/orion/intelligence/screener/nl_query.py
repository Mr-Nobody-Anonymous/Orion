"""Natural-Language Financial Screener Query Parser.

Converts free-form financial criteria into structured ScreenFilters.
Lives in the Intelligence plane.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from .engine import ScreenFilter, ScreenerEngine, ScreenResult


class NaturalLanguageScreener:
    """Parses natural language financial screening queries into executable ScreenFilters."""

    # Pattern: [field_name] [operator] [number][%]
    FILTER_REGEX = re.compile(
        r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|==|!=|=)\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*(%?)",
        re.IGNORECASE,
    )

    FIELD_SYNONYMS = {
        "pe": "pe_ratio",
        "p/e": "pe_ratio",
        "pb": "pb_ratio",
        "p/b": "pb_ratio",
        "ev/ebitda": "ev_to_ebitda",
        "evebitda": "ev_to_ebitda",
        "roic": "roic",
        "roe": "roe",
        "debt/equity": "debt_to_equity",
        "debt_equity": "debt_to_equity",
        "growth": "revenue_growth",
        "revenue_growth": "revenue_growth",
        "f_score": "piotroski_f",
        "z_score": "altman_z",
        "volume": "volume",
        "market_cap": "market_cap",
    }

    @classmethod
    def parse_query(cls, query_text: str) -> list[ScreenFilter]:
        filters: list[ScreenFilter] = []
        clean_text = query_text.replace(",", " and ").replace(";", " and ")

        for match in cls.FILTER_REGEX.finditer(clean_text):
            raw_field, op, val_str, is_pct = match.groups()
            normalized_field = cls.FIELD_SYNONYMS.get(raw_field.lower(), raw_field.lower())
            val = float(val_str)
            if is_pct:
                val /= 100.0  # e.g., 15% -> 0.15

            if op == "=":
                op = "=="

            filters.append(ScreenFilter(field=normalized_field, operator=op, value=val))

        return filters

    @classmethod
    def execute_query(
        cls,
        query_text: str,
        universe: Sequence[dict[str, Any]],
        sort_by: str | None = None,
        limit: int | None = None,
    ) -> list[ScreenResult]:
        parsed_filters = cls.parse_query(query_text)
        return ScreenerEngine.screen(universe, parsed_filters, sort_by=sort_by, limit=limit)
