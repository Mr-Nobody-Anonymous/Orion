from decimal import Decimal

from orion.backtesting import performance_metrics, vectorized_momentum_backtest, walk_forward_momentum


def test_performance_metrics_and_walk_forward_are_computed() -> None:
    prices = [100, 101, 102, 101, 103, 104, 106, 105, 107, 109, 108, 110, 112, 111, 113, 114]
    result = vectorized_momentum_backtest(prices)
    metrics = performance_metrics(prices, result)
    walk_forward = walk_forward_momentum(prices, train_window=8, test_window=4)
    assert metrics.observations == len(prices) - 1
    assert isinstance(metrics.max_drawdown, Decimal)
    assert walk_forward.windows
