"""Kalshi-Class Prediction Market Engine.

Models YES/NO double order book mechanics, implied vs. Bayesian calibrated probability,
Kelly criterion bet sizing, and lifecycle settlement.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

from ...data.contracts import PredictionMarket, PredictionMarketContract


@dataclass(frozen=True, slots=True)
class CalibratedProbability:
    contract_ticker: str
    market_implied_probability: Decimal
    ai_model_probability: Decimal
    calibrated_probability: Decimal
    model_edge: Decimal  # AI prob - Implied prob
    kelly_fraction: Decimal


@dataclass(frozen=True, slots=True)
class PredictionMarketSettlement:
    contract_ticker: str
    outcome: str  # "YES" or "NO"
    settlement_price: Decimal  # 1.00 for win, 0.00 for loss
    positions_held: Decimal
    entry_cost: Decimal
    payout: Decimal
    realized_pnl: Decimal


class KalshiMarketEngine:
    """Prediction market probability modeling, Kelly bet sizing, and settlement mechanics."""

    @staticmethod
    def calculate_implied_probability(yes_bid: Decimal, yes_ask: Decimal) -> Decimal:
        """Calculates implied probability from top of YES book."""
        if yes_bid < 0 or yes_ask > 1 or yes_bid > yes_ask:
            raise ValueError(f"Invalid YES book prices: bid={yes_bid}, ask={yes_ask}")
        return (yes_bid + yes_ask) / Decimal("2")

    @staticmethod
    def calibrate_probability(
        market_implied: Decimal,
        ai_model_prob: Decimal,
        ai_confidence: Decimal = Decimal("0.8"),
    ) -> CalibratedProbability:
        """Bayesian blend of market wisdom with AI model prediction weighted by confidence."""
        if not (Decimal("0") <= market_implied <= Decimal("1")):
            raise ValueError(f"Market implied prob must be in [0, 1]: {market_implied}")
        if not (Decimal("0") <= ai_model_prob <= Decimal("1")):
            raise ValueError(f"AI model prob must be in [0, 1]: {ai_model_prob}")

        # Linear bayesian shrinkage: Calibrated = (1 - w) * Market + w * Model
        w = max(Decimal("0.0"), min(Decimal("1.0"), ai_confidence))
        calibrated = (Decimal("1") - w) * market_implied + (w * ai_model_prob)
        edge = calibrated - market_implied

        # Kelly Criterion: f* = (p * b - q) / b
        # In prediction markets, payout is 1.00 per share. Net odds b = (1.00 - price) / price
        price = market_implied
        if Decimal("0.01") <= price <= Decimal("0.99") and edge > 0:
            b = (Decimal("1.00") - price) / price
            p = calibrated
            q = Decimal("1.00") - p
            raw_kelly = (p * b - q) / b
            # Institutional half-Kelly for capital preservation
            kelly = max(Decimal("0"), raw_kelly * Decimal("0.5")).quantize(Decimal("0.0001"))
        else:
            kelly = Decimal("0")

        return CalibratedProbability(
            contract_ticker="KALSHI_CONTRACT",
            market_implied_probability=market_implied,
            ai_model_probability=ai_model_prob,
            calibrated_probability=calibrated,
            model_edge=edge,
            kelly_fraction=kelly,
        )

    @staticmethod
    def settle_contract(
        contract_ticker: str,
        winning_outcome: str,
        side_held: str,
        quantity: Decimal,
        avg_entry_price: Decimal,
    ) -> PredictionMarketSettlement:
        """Settles an expired contract for an account holding positions."""
        won = (winning_outcome.upper() == side_held.upper())
        settlement_price = Decimal("1.00") if won else Decimal("0.00")
        entry_cost = quantity * avg_entry_price
        payout = quantity * settlement_price
        realized_pnl = payout - entry_cost

        return PredictionMarketSettlement(
            contract_ticker=contract_ticker,
            outcome=winning_outcome.upper(),
            settlement_price=settlement_price,
            positions_held=quantity,
            entry_cost=entry_cost,
            payout=payout,
            realized_pnl=realized_pnl,
        )
