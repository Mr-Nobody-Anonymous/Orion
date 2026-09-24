"""Cross-Exchange and Multi-Venue Arbitrage Engine.

Detects spatial cross-venue price discrepancies and triangular arbitrage opportunities
after deducting venue taker fees, slippage buffers, and transfer costs.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from ...data.contracts import Asset, MarketQuote


@dataclass(frozen=True, slots=True)
class SpatialArbitrageOpportunity:
    symbol: str
    buy_venue: str
    sell_venue: str
    buy_price: Decimal  # Venue A Ask
    sell_price: Decimal  # Venue B Bid
    gross_spread: Decimal
    gross_spread_bps: Decimal
    net_spread_bps: Decimal
    is_profitable: bool


@dataclass(frozen=True, slots=True)
class TriangularArbitrageOpportunity:
    pair_a: str  # e.g. "BTC/USDT"
    pair_b: str  # e.g. "ETH/BTC"
    pair_c: str  # e.g. "ETH/USDT"
    synthetic_return: Decimal
    net_profit_pct: Decimal
    is_profitable: bool


class ArbitrageEngine:
    """Multi-venue and triangular arbitrage detection."""

    @staticmethod
    def detect_spatial_arbitrage(
        symbol: str,
        quotes: Sequence[MarketQuote],
        taker_fee_bps: Decimal = Decimal("10"),  # 0.10% per leg
        buffer_bps: Decimal = Decimal("5"),
    ) -> list[SpatialArbitrageOpportunity]:
        opportunities: list[SpatialArbitrageOpportunity] = []
        if len(quotes) < 2:
            return []

        total_fee_bps = (taker_fee_bps * Decimal("2")) + buffer_bps

        for q_buy in quotes:
            for q_sell in quotes:
                if q_buy.asset.venue == q_sell.asset.venue:
                    continue

                buy_p = q_buy.ask
                sell_p = q_sell.bid
                if buy_p <= 0 or sell_p <= 0:
                    continue

                gross_spread = sell_p - buy_p
                gross_bps = (gross_spread / buy_p) * Decimal("10000")
                net_bps = gross_bps - total_fee_bps

                if net_bps > 0:
                    opportunities.append(SpatialArbitrageOpportunity(
                        symbol=symbol,
                        buy_venue=q_buy.asset.venue or "venue_1",
                        sell_venue=q_sell.asset.venue or "venue_2",
                        buy_price=buy_p,
                        sell_price=sell_p,
                        gross_spread=gross_spread,
                        gross_spread_bps=gross_bps.quantize(Decimal("0.01")),
                        net_spread_bps=net_bps.quantize(Decimal("0.01")),
                        is_profitable=True,
                    ))

        opportunities.sort(key=lambda x: x.net_spread_bps, reverse=True)
        return opportunities

    @staticmethod
    def detect_triangular_arbitrage(
        p_btc_usdt: Decimal,
        p_eth_btc: Decimal,
        p_eth_usdt: Decimal,
        fee_rate: Decimal = Decimal("0.001"),  # 0.1% per trade (3 trades = ~0.3%)
    ) -> TriangularArbitrageOpportunity:
        """Calculates triangular cycle: USDT -> BTC -> ETH -> USDT."""
        # 1 USDT buys (1 / p_btc_usdt) BTC
        # BTC buys (1 / p_eth_btc) ETH
        # ETH sells for p_eth_usdt
        synthetic_rate = (Decimal("1") / p_btc_usdt) * (Decimal("1") / p_eth_btc) * p_eth_usdt
        # 3 trading fee legs
        net_multiplier = (Decimal("1") - fee_rate) ** Decimal("3")
        final_return = synthetic_rate * net_multiplier
        net_profit_pct = (final_return - Decimal("1.0")) * Decimal("100")

        return TriangularArbitrageOpportunity(
            pair_a="BTC/USDT",
            pair_b="ETH/BTC",
            pair_c="ETH/USDT",
            synthetic_return=synthetic_rate.quantize(Decimal("0.0001")),
            net_profit_pct=net_profit_pct.quantize(Decimal("0.01")),
            is_profitable=net_profit_pct > Decimal("0"),
        )
