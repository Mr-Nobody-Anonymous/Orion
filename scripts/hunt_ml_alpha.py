#!/usr/bin/env python
"""Machine Learning Alpha Hunt

Uses a Random Forest Regressor to discover alpha patterns.
Tests the model through Orion's strict Out-Of-Sample Strategy Lab gates.
"""

from __future__ import annotations

import sys
import os
import random
from decimal import Decimal
import numpy as np
from sklearn.ensemble import RandomForestRegressor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orion.evaluation.walk_forward import build_folds, WalkForwardFold
from orion.research.strategy_lab import StrategyLabEngine

class MockStrategy:
    def __init__(self, name: str):
        self.name = name

def generate_market_data(n_bars: int) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic but mildly autocorrelated market data (mocking a tradable anomaly)."""
    random.seed(42)
    np.random.seed(42)
    prices = [100.0]
    drift = 0.0001
    vol = 0.01
    for i in range(n_bars - 1):
        # Create a hidden regime/anomaly: mean reversion after 3 down days
        if i >= 3 and prices[-1] < prices[-2] < prices[-3]:
            shock = abs(random.gauss(0, vol * 2))  # Bounce
        else:
            shock = random.gauss(0, vol)
        prices.append(prices[-1] * (1.0 + drift + shock))
        
    prices_arr = np.array(prices)
    returns = np.diff(prices_arr) / prices_arr[:-1]
    returns = np.insert(returns, 0, 0.0)
    return prices_arr, returns

def extract_features(returns: np.ndarray) -> np.ndarray:
    """Extract lagged return features for ML."""
    features = []
    for i in range(len(returns)):
        if i < 5:
            features.append([0.0] * 5)
        else:
            features.append([returns[i-1], returns[i-2], returns[i-3], returns[i-4], returns[i-5]])
    return np.array(features)

def main() -> None:
    print("Initializing Orion ML Alpha Hunt...")
    n_bars = 2000
    prices, returns = generate_market_data(n_bars)
    X = extract_features(returns)
    y = np.roll(returns, -1)  # Predict next day's return
    y[-1] = 0.0 # Remove last element's invalid target
    
    folds = build_folds(n_bars, train_size=500, test_size=100, step=100, embargo=5, purge=0)
    print(f"Generated {len(folds)} walk-forward folds.")
    
    in_sample_returns = []
    oos_returns = []
    
    for fold in folds:
        # Train ML Model
        X_train = X[fold.train_start : fold.train_end + 1]
        y_train = y[fold.train_start : fold.train_end + 1]
        
        model = RandomForestRegressor(n_estimators=50, max_depth=3, random_state=42)
        model.fit(X_train, y_train)
        
        # Calculate in-sample proxy performance
        is_preds = model.predict(X_train)
        # Position sizing: 1 if positive pred, -1 if negative
        is_positions = np.where(is_preds > 0, 1.0, -1.0)
        is_fold_ret = np.sum(is_positions * y_train)
        in_sample_returns.append(is_fold_ret)
        
        # Out-of-Sample evaluation
        X_test = X[fold.test_start : fold.test_end + 1]
        y_test = y[fold.test_start : fold.test_end + 1]
        
        oos_preds = model.predict(X_test)
        oos_positions = np.where(oos_preds > 0, 1.0, -1.0)
        oos_fold_ret = np.sum(oos_positions * y_test)
        oos_returns.append(oos_fold_ret)

    strategy = MockStrategy("RandomForest_Alpha_v1")
    
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
