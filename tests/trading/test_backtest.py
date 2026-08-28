from decimal import Decimal

from orion.backtest import vectorized_momentum_backtest


def test_vectorized_momentum_backtest_accounts_for_fees() -> None:
    result = vectorized_momentum_backtest([100, 101, 102, 103, 104, 105, 106])
    assert result.trades >= 1
    assert result.final_cash > result.initial_cash
    assert result.transaction_costs > Decimal("0")
