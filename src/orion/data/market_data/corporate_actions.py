"""Corporate actions engine and historical price adjustment.

Handles dividends, stock splits, mergers, symbol changes, and trading halts.
Computes split-adjusted and total-return-adjusted historical price series.
Strictly in the Truth plane (pure, zero-dependency).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Sequence

from ..contracts import Asset, OHLCV


class CorporateActionType(str, Enum):
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    SPLIT = "split"
    REVERSE_SPLIT = "reverse_split"
    MERGER = "merger"
    SPINOFF = "spinoff"
    SYMBOL_CHANGE = "symbol_change"
    DELISTING = "delisting"
    TRADING_HALT = "trading_halt"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass(frozen=True, slots=True)
class CorporateAction:
    asset: Asset
    action_type: CorporateActionType
    effective_date: datetime
    rate_or_ratio: Decimal  # e.g., Decimal("2.0") for 2-for-1 split; Decimal("0.50") for $0.50 dividend
    old_symbol: str = ""
    new_symbol: str = ""
    notes: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class AdjustedOHLCV:
    raw: OHLCV
    adjusted_open: Decimal
    adjusted_high: Decimal
    adjusted_low: Decimal
    adjusted_close: Decimal
    adjusted_volume: Decimal
    split_factor: Decimal
    dividend_factor: Decimal


class CorporateActionAdjustmentEngine:
    """Calculates split-adjusted and dividend-adjusted price series backward from current date."""

    @staticmethod
    def adjust_series(
        bars: Sequence[OHLCV],
        actions: Sequence[CorporateAction],
    ) -> list[AdjustedOHLCV]:
        if not bars:
            return []

        # Sort bars ascending by timestamp
        sorted_bars = sorted(bars, key=lambda b: b.timestamp)
        sorted_actions = sorted(actions, key=lambda a: a.effective_date)

        adjusted: list[AdjustedOHLCV] = []
        for bar in sorted_bars:
            cumulative_split_factor = Decimal("1.0")
            cumulative_div_factor = Decimal("1.0")

            # Actions taking effect strictly AFTER this bar's date adjust this bar backward
            for action in sorted_actions:
                if action.effective_date > bar.timestamp:
                    if action.action_type in (CorporateActionType.SPLIT, CorporateActionType.STOCK_DIVIDEND):
                        if action.rate_or_ratio > 0:
                            cumulative_split_factor /= action.rate_or_ratio
                    elif action.action_type == CorporateActionType.REVERSE_SPLIT:
                        if action.rate_or_ratio > 0:
                            cumulative_split_factor *= action.rate_or_ratio
                    elif action.action_type == CorporateActionType.CASH_DIVIDEND:
                        # Standard CRSP/Yahoo dividend adjustment: (P - Div) / P
                        if bar.close > 0:
                            div_ratio = (bar.close - action.rate_or_ratio) / bar.close
                            if div_ratio > 0:
                                cumulative_div_factor *= div_ratio

            total_factor = cumulative_split_factor * cumulative_div_factor
            vol_factor = Decimal("1.0") / cumulative_split_factor if cumulative_split_factor > 0 else Decimal("1.0")

            adj_bar = AdjustedOHLCV(
                raw=bar,
                adjusted_open=bar.open * total_factor,
                adjusted_high=bar.high * total_factor,
                adjusted_low=bar.low * total_factor,
                adjusted_close=bar.close * total_factor,
                adjusted_volume=bar.volume * vol_factor,
                split_factor=cumulative_split_factor,
                dividend_factor=cumulative_div_factor,
            )
            adjusted.append(adj_bar)

        return adjusted
