"""Causal Price Movement Attribution Engine ("Why did X move today?").

Decomposes asset returns into probability-weighted causal drivers:
Sector/market beta, earnings releases, options flow, macro shocks, and sentiment.
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class AttributionDriver:
    rank: int
    category: str  # "earnings", "macro", "sector_momentum", "options_flow", "sentiment"
    title: str
    contribution_pct: Decimal  # e.g., +3.2%
    weight_confidence: Decimal  # e.g., 0.85
    supporting_evidence: str
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PriceMovementAttributionReport:
    symbol: str
    asset_move_pct: Decimal
    unexplained_residual_pct: Decimal
    primary_drivers: tuple[AttributionDriver, ...]
    overall_confidence: Decimal
    summary: str


class PriceAttributionEngine:
    """Multi-factor attribution analyzing why an asset moved on a given day."""

    @staticmethod
    def attribute_movement(
        symbol: str,
        asset_return: Decimal,
        market_return: Decimal,
        sector_return: Decimal,
        beta: Decimal = Decimal("1.2"),
        earnings_surprise_pct: Decimal | None = None,
        macro_surprise_impact: Decimal | None = None,
        sentiment_score: Decimal | None = None,  # -1.0 to +1.0
        options_implied_squeeze: bool = False,
    ) -> PriceMovementAttributionReport:
        drivers: list[AttributionDriver] = []
        explained_total = Decimal("0")

        # 1. Sector and Market Beta effect
        market_comp = (market_return * beta).quantize(Decimal("0.0001"))
        sector_comp = (sector_return - market_return) * Decimal("0.5")  # idiosyncratic sector excess
        beta_tot = market_comp + sector_comp
        if abs(beta_tot) > Decimal("0.002"):
            drivers.append(AttributionDriver(
                rank=1,
                category="sector_momentum",
                title="Market and Sector Beta Co-movement",
                contribution_pct=(beta_tot * Decimal("100")).quantize(Decimal("0.01")),
                weight_confidence=Decimal("0.90"),
                supporting_evidence=f"Market moved {market_return*100:.2f}%, sector moved {sector_return*100:.2f}% with asset beta {beta}.",
                sources=("market_data",),
            ))
            explained_total += beta_tot

        # 2. Earnings effect
        if earnings_surprise_pct is not None and abs(earnings_surprise_pct) > Decimal("0.01"):
            # Sensitivity: ~0.4x surprise passed to price
            earn_impact = earnings_surprise_pct * Decimal("0.4")
            drivers.append(AttributionDriver(
                rank=2,
                category="earnings",
                title="Quarterly Earnings Release Surprise",
                contribution_pct=(earn_impact * Decimal("100")).quantize(Decimal("0.01")),
                weight_confidence=Decimal("0.95"),
                supporting_evidence=f"Reported earnings surprise of {earnings_surprise_pct*100:.1f}%.",
                sources=("sec_filing", "earnings_wire"),
            ))
            explained_total += earn_impact

        # 3. Macro effect
        if macro_surprise_impact is not None and abs(macro_surprise_impact) > Decimal("0.001"):
            drivers.append(AttributionDriver(
                rank=3,
                category="macro",
                title="Macroeconomic Release Shock",
                contribution_pct=(macro_surprise_impact * Decimal("100")).quantize(Decimal("0.01")),
                weight_confidence=Decimal("0.80"),
                supporting_evidence=f"Macro economic event contributed {macro_surprise_impact*100:.2f}%.",
                sources=("economic_calendar",),
            ))
            explained_total += macro_surprise_impact

        # 4. Options gamma squeeze
        if options_implied_squeeze:
            squeeze_impact = Decimal("0.015") if asset_return > 0 else Decimal("-0.015")
            drivers.append(AttributionDriver(
                rank=4,
                category="options_flow",
                title="Options Dealer Gamma Hedging / Squeeze",
                contribution_pct=(squeeze_impact * Decimal("100")).quantize(Decimal("0.01")),
                weight_confidence=Decimal("0.75"),
                supporting_evidence="Heavy short-dated call volume triggered dealer delta hedging acceleration.",
                sources=("options_flow",),
            ))
            explained_total += squeeze_impact

        # 5. Sentiment effect
        if sentiment_score is not None and abs(sentiment_score) > Decimal("0.2"):
            sent_impact = sentiment_score * Decimal("0.008")
            drivers.append(AttributionDriver(
                rank=5,
                category="sentiment",
                title="News and Social Sentiment Inflow",
                contribution_pct=(sent_impact * Decimal("100")).quantize(Decimal("0.01")),
                weight_confidence=Decimal("0.70"),
                supporting_evidence=f"Net sentiment polarity scored {sentiment_score:.2f}.",
                sources=("news_terminal", "social_intelligence"),
            ))
            explained_total += sent_impact

        # Re-rank drivers by absolute contribution
        drivers.sort(key=lambda d: abs(d.contribution_pct), reverse=True)
        ranked_drivers = tuple(
            AttributionDriver(
                rank=i + 1,
                category=d.category,
                title=d.title,
                contribution_pct=d.contribution_pct,
                weight_confidence=d.weight_confidence,
                supporting_evidence=d.supporting_evidence,
                sources=d.sources,
            )
            for i, d in enumerate(drivers)
        )

        residual = asset_return - explained_total
        res_pct = (residual * Decimal("100")).quantize(Decimal("0.01"))
        move_pct = (asset_return * Decimal("100")).quantize(Decimal("0.01"))

        summary = f"{symbol} moved {move_pct:+.2f}%. Primary driver: {ranked_drivers[0].title} ({ranked_drivers[0].contribution_pct:+.2f}%)" if ranked_drivers else f"{symbol} moved {move_pct:+.2f}% with no distinct headline catalyst."

        return PriceMovementAttributionReport(
            symbol=symbol,
            asset_move_pct=move_pct,
            unexplained_residual_pct=res_pct,
            primary_drivers=ranked_drivers,
            overall_confidence=Decimal("0.84") if ranked_drivers else Decimal("0.40"),
            summary=summary,
        )
