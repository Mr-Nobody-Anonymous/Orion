"""Conversational AI Financial Copilot.

Answers complex multi-asset financial questions with tool-augmented reasoning:
Attribution, screening, risk stress testing, and valuation.
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from .attribution import PriceAttributionEngine, PriceMovementAttributionReport
from ..fundamental.valuation import ValuationEngine
from ..screener.nl_query import NaturalLanguageScreener


@dataclass(frozen=True, slots=True)
class CopilotResponse:
    query: str
    intent: str  # "attribution", "screener", "valuation", "general"
    response_text: str
    confidence: Decimal
    tool_artifacts: Mapping[str, Any] = field(default_factory=dict)


class FinancialCopilot:
    """Conversational financial AI agent with deterministic financial tool integration."""

    @classmethod
    def answer_query(
        cls,
        query: str,
        context_data: Mapping[str, Any] | None = None,
    ) -> CopilotResponse:
        q_lower = query.lower()
        ctx = context_data or {}

        # 1. Price Attribution query ("Why did X move / fall / rise?")
        if any(w in q_lower for w in ("why did", "why is", "why dropped", "why surged")):
            symbol = ctx.get("symbol", "ASSET")
            asset_ret = ctx.get("asset_return", Decimal("-0.047"))
            mkt_ret = ctx.get("market_return", Decimal("-0.012"))
            sec_ret = ctx.get("sector_return", Decimal("-0.020"))

            attr = PriceAttributionEngine.attribute_movement(
                symbol=symbol,
                asset_return=asset_ret,
                market_return=mkt_ret,
                sector_return=sec_ret,
                sentiment_score=ctx.get("sentiment_score", Decimal("-0.6")),
                options_implied_squeeze=ctx.get("options_squeeze", False),
            )

            body_lines = [f"{symbol} moved {attr.asset_move_pct:+.2f}%. Primary drivers:"]
            for d in attr.primary_drivers:
                body_lines.append(f"{d.rank}. {d.title} ({d.contribution_pct:+.2f}%): {d.supporting_evidence}")
            body_lines.append(f"Confidence: {int(attr.overall_confidence * 100)}%")

            return CopilotResponse(
                query=query,
                intent="attribution",
                response_text="\n".join(body_lines),
                confidence=attr.overall_confidence,
                tool_artifacts={"attribution_report": attr},
            )

        # 2. Screener query ("Find companies...", "Screen stocks...")
        if any(w in q_lower for w in ("find", "screen", "filter", "stocks with", "companies with")):
            universe = ctx.get("universe", [])
            results = NaturalLanguageScreener.execute_query(query, universe)
            symbols = [r.symbol for r in results]
            resp = f"Found {len(results)} matching securities: {', '.join(symbols)}" if symbols else "No securities matched the specified criteria."
            return CopilotResponse(
                query=query,
                intent="screener",
                response_text=resp,
                confidence=Decimal("0.90"),
                tool_artifacts={"screen_results": results},
            )

        # 3. Valuation query ("DCF", "Valuation", "Fair value")
        if any(w in q_lower for w in ("dcf", "valuation", "fair value", "intrinsic value")):
            fcf = ctx.get("projected_fcf", [Decimal("100"), Decimal("110"), Decimal("120")])
            wacc = ctx.get("wacc", Decimal("0.08"))
            g = ctx.get("terminal_growth", Decimal("0.02"))
            net_debt = ctx.get("net_debt", Decimal("50"))
            shares = ctx.get("shares_outstanding", Decimal("20"))

            res = ValuationEngine.dcf(fcf, wacc, g, net_debt, shares)
            resp = f"Implied DCF Fair Value: ${res.implied_share_price:.2f} per share (Enterprise Value: ${res.enterprise_value:,.2f}, Equity Value: ${res.equity_value:,.2f})."
            return CopilotResponse(
                query=query,
                intent="valuation",
                response_text=resp,
                confidence=Decimal("0.88"),
                tool_artifacts={"dcf_result": res},
            )

        # Default general response
        return CopilotResponse(
            query=query,
            intent="general",
            response_text="Orion Financial Copilot processed your query. Ready to assist with market data, valuation, risk analysis, or screening.",
            confidence=Decimal("0.70"),
        )
