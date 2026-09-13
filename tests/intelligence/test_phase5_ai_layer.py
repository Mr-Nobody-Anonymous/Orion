"""Tests for Phase 5: AI Layer.

Covers:
- Causal price movement attribution ("Why did X move today?")
- AI Financial Copilot conversational query dispatch and tool execution
- Strategy Research Lab automated hypothesis testing and approval gate
- Institutional Model Zoo ensemble, Information Coefficient (IC), and hit-rate
- Online continual learning and concept drift detector
- Causal AI Granger causality and Difference-in-Differences (DiD)
"""

from __future__ import annotations

import math
from decimal import Decimal
import pytest

from orion.data.contracts import Strategy
from orion.intelligence.causal import CausalAIEngine
from orion.intelligence.copilot import (
    FinancialCopilot,
    PriceAttributionEngine,
)
from orion.learning.online import OnlineContinualLearner
from orion.models.zoo import ModelPrediction, ModelZooEngine
from orion.research.strategy_lab import StrategyLabEngine


# ---------------------------------------------------------------------------
# 1. Price Attribution Engine
# ---------------------------------------------------------------------------

def test_price_attribution_engine() -> None:
    report = PriceAttributionEngine.attribute_movement(
        symbol="NVDA",
        asset_return=Decimal("0.068"),  # +6.8%
        market_return=Decimal("0.012"),  # +1.2%
        sector_return=Decimal("0.035"),  # +3.5% (Semis)
        beta=Decimal("1.4"),
        earnings_surprise_pct=Decimal("0.12"),  # +12% EPS beat
        options_implied_squeeze=True,
    )

    assert report.symbol == "NVDA"
    assert report.asset_move_pct == Decimal("6.80")
    assert len(report.primary_drivers) >= 3
    # Top driver should be earnings or options squeeze
    top_categories = [d.category for d in report.primary_drivers[:2]]
    assert "earnings" in top_categories or "options_flow" in top_categories
    assert report.overall_confidence > Decimal("0.80")


# ---------------------------------------------------------------------------
# 2. AI Financial Copilot
# ---------------------------------------------------------------------------

def test_financial_copilot_queries() -> None:
    # 1. Attribution
    ctx_attr = {
        "symbol": "BTC",
        "asset_return": Decimal("-0.047"),
        "market_return": Decimal("-0.010"),
        "sector_return": Decimal("-0.030"),
        "sentiment_score": Decimal("-0.7"),
    }
    resp1 = FinancialCopilot.answer_query("Why is BTC falling today?", context_data=ctx_attr)
    assert resp1.intent == "attribution"
    assert "BTC moved -4.70%" in resp1.response_text
    assert "Confidence:" in resp1.response_text

    # 2. Screener
    universe = [
        {"symbol": "AAPL", "roic": 0.28, "debt_to_equity": 0.4},
        {"symbol": "MSFT", "roic": 0.24, "debt_to_equity": 0.3},
        {"symbol": "RISKY", "roic": 0.05, "debt_to_equity": 2.0},
    ]
    resp2 = FinancialCopilot.answer_query("Find stocks with roic > 20% and debt_to_equity < 0.5", context_data={"universe": universe})
    assert resp2.intent == "screener"
    assert "AAPL" in resp2.response_text
    assert "MSFT" in resp2.response_text
    assert "RISKY" not in resp2.response_text

    # 3. Valuation
    resp3 = FinancialCopilot.answer_query("Calculate DCF valuation for company")
    assert resp3.intent == "valuation"
    assert "Implied DCF Fair Value" in resp3.response_text


# ---------------------------------------------------------------------------
# 3. Strategy Research Lab
# ---------------------------------------------------------------------------

def test_strategy_lab_engine() -> None:
    strat = Strategy(name="MOMENTUM_ALPHA_01")
    # Positive in-sample returns with steady Sharpe
    is_returns = [0.005 + 0.008 * ((-1) ** i) for i in range(100)]
    # Healthy out-of-sample returns
    oos_returns = [0.004 + 0.007 * ((-1) ** i) for i in range(50)]

    rec = StrategyLabEngine.evaluate_strategy(strat, is_returns, oos_returns, baseline_sharpe=Decimal("1.0"))
    assert rec.strategy_name == "MOMENTUM_ALPHA_01"
    assert rec.walk_forward_sharpe > 0
    assert rec.beats_baseline is True
    assert rec.approval_verdict == "APPROVED"


# ---------------------------------------------------------------------------
# 4. Model Zoo & Ensembles
# ---------------------------------------------------------------------------

def test_model_zoo_engine() -> None:
    preds = [0.02, 0.01, -0.01, 0.03, -0.02, 0.01, 0.02, -0.01, 0.04, -0.03]
    actual = [0.018, 0.012, -0.008, 0.025, -0.015, 0.008, 0.015, -0.012, 0.035, -0.028]

    ic = ModelZooEngine.calculate_information_coefficient(preds, actual)
    acc = ModelZooEngine.calculate_directional_accuracy(preds, actual)

    assert ic > 0.90  # Very high correlation
    assert acc == 1.0  # 100% directional accuracy

    m1 = ModelPrediction(model_name="LGBM", expected_return=0.03, directional_probability_up=0.70, confidence=0.8)
    m2 = ModelPrediction(model_name="TRANSFORMER", expected_return=0.02, directional_probability_up=0.60, confidence=0.6)

    ens = ModelZooEngine.ensemble_predictions([m1, m2])
    assert ens.model_name == "ENSEMBLE"
    assert 0.02 < ens.expected_return < 0.03
    assert 0.60 < ens.directional_probability_up < 0.70


# ---------------------------------------------------------------------------
# 5. Online Continual Learning
# ---------------------------------------------------------------------------

def test_online_continual_learner() -> None:
    learner = OnlineContinualLearner(model_name="LIVE_PREDICTOR", window_size=30, max_acceptable_mse=0.02)

    # Ingest 25 degraded outcomes where prediction has large error
    for i in range(25):
        learner.record_outcome(predicted_return=0.05, actual_return=-0.08)

    snapshot = learner.evaluate_live_drift()
    assert snapshot.is_degraded is True
    assert snapshot.retraining_recommended is True
    assert snapshot.rolling_directional_accuracy == 0.0


# ---------------------------------------------------------------------------
# 6. Causal AI Engine
# ---------------------------------------------------------------------------

def test_causal_ai_engine() -> None:
    # Granger Causality: X leads Y by 1 lag
    x = [0.01 * math.sin(i * 0.2) for i in range(50)]
    y = [0.0] + [0.8 * x[i - 1] for i in range(1, 50)]

    res_gc = CausalAIEngine.test_granger_causality(x, y, lags=2)
    assert res_gc.f_statistic > 0
    assert res_gc.variance_reduction_pct > 0

    # Difference in Differences
    treatment_pre = [10.0, 10.2, 9.8]  # Avg 10.0
    treatment_post = [15.0, 15.2, 14.8]  # Avg 15.0 (Diff = +5.0)
    control_pre = [10.0, 10.0, 10.0]  # Avg 10.0
    control_post = [11.0, 11.0, 11.0]  # Avg 11.0 (Diff = +1.0)

    did = CausalAIEngine.difference_in_differences(treatment_pre, treatment_post, control_pre, control_post)
    # Expected: (15 - 10) - (11 - 10) = 5.0 - 1.0 = +4.0
    assert abs(did.did_estimate - 4.0) < 0.01
    assert did.is_positive_effect is True
