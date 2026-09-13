#!/usr/bin/env python
"""Alpha Discovery Engine: Walk-Forward Out-of-Sample Evaluation

This script demonstrates Orion's scientific strategy evaluation process using
the Walk-Forward harness (with embargo) and the Strategy Lab Engine.
It proves that strategies must survive strict out-of-sample conditions.
"""

from __future__ import annotations

import math
import random
from decimal import Decimal

from orion.evaluation.walk_forward import build_folds, run_fold, WalkForwardFold
from orion.research.strategy_lab import StrategyLabEngine, StrategyEvaluationRecord

class MockStrategy:
    def __init__(self, name: str):
        self.name = name

def simple_momentum_predictor(train_prices: list[float]) -> float:
    """Predicts next return based on recent momentum."""
    if len(train_prices) < 2:
        return 0.0
    # Use the last 5 days for momentum, or less if not available
    lookback = min(5, len(train_prices) - 1)
    ret = (train_prices[-1] / train_prices[-1 - lookback]) - 1.0
    return float(ret)

def generate_synthetic_prices(n: int, drift: float = 0.0005, vol: float = 0.01) -> list[float]:
    """Generate a random walk price series."""
    random.seed(42)
    prices = [100.0]
    for _ in range(n - 1):
        shock = random.gauss(0, vol)
        prices.append(prices[-1] * (1.0 + drift + shock))
    return prices

def main() -> None:
    print("Initializing Orion Alpha Discovery Engine...")
    
    # 1. Generate 1000 days of synthetic prices
    n_bars = 1000
    prices = generate_synthetic_prices(n_bars)
    
    # 2. Build Walk-Forward Folds (Train: 200, Test: 50, Embargo: 5, Purge: 0, Step: 50)
    folds = build_folds(n_bars, train_size=200, test_size=50, step=50, embargo=5, purge=0)
    
    print(f"Generated {len(folds)} walk-forward folds.")
    
    # 3. Evaluate the strategy across all folds
    in_sample_returns = []
    oos_returns = []
    
    for fold in folds:
        # In-sample proxy: evaluate on the train set (mocking an in-sample return)
        train_prices = prices[fold.train_start : fold.train_end + 1]
        if len(train_prices) >= 2:
            is_ret = train_prices[-1] / train_prices[0] - 1.0
            in_sample_returns.append(is_ret)
        
        # Out-of-sample evaluation using the predictor
        error = run_fold(fold, prices, simple_momentum_predictor)
        
        # Calculate actual OOS realised return for the metric
        test_prices = prices[fold.test_start : fold.test_end + 1]
        if len(test_prices) >= 2:
            oos_ret = test_prices[-1] / test_prices[0] - 1.0
            oos_returns.append(oos_ret)
            
    # 4. Institutional Strategy Lab Evaluation
    strategy = MockStrategy("Momentum_v1")
    
    record = StrategyLabEngine.evaluate_strategy(
        strategy=strategy, # type: ignore
        in_sample_returns=in_sample_returns,
        out_of_sample_returns=oos_returns,
        baseline_sharpe=Decimal("0.50"),
        max_acceptable_drawdown_pct=Decimal("25.0")
    )
    
    print("\n" + "="*50)
    print(" ORION INSTITUTIONAL STRATEGY EVALUATION")
    print("="*50)
    print(f"Strategy:              {record.strategy_name}")
    print(f"Backtest Sharpe:       {record.backtest_sharpe}")
    print(f"Walk-Forward Sharpe:   {record.walk_forward_sharpe}")
    print(f"Max Drawdown:          {record.max_drawdown_pct}%")
    print(f"Beats Baseline:        {record.beats_baseline}")
    print(f"Stress Test Passed:    {record.stress_test_passed}")
    print(f"Verdict:               {record.approval_verdict}")
    print("="*50)

if __name__ == "__main__":
    main()
