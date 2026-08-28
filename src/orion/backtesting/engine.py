from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class BacktestResult:
    initial_cash: Decimal
    final_cash: Decimal
    total_return: Decimal
    trades: int
    transaction_costs: Decimal


def vectorized_momentum_backtest(prices: Sequence[float], lookback: int = 5,
                                 initial_cash: Decimal = Decimal("100000"),
                                 fee_rate: Decimal = Decimal("0.001")) -> BacktestResult:
    if len(prices) <= lookback or any(price <= 0 for price in prices):
        raise ValueError("prices must contain positive values beyond lookback")
    cash = initial_cash
    shares = Decimal("0")
    costs = Decimal("0")
    trades = 0
    for index in range(lookback, len(prices)):
        price = Decimal(str(prices[index]))
        previous = Decimal(str(prices[index - lookback]))
        portfolio_value = cash + shares * price
        target_shares = portfolio_value / price if price > previous else Decimal("0")
        delta = target_shares - shares
        if delta:
            notional = abs(delta * price)
            cost = notional * fee_rate
            cash -= delta * price + cost
            costs += cost
            shares = target_shares
            trades += 1
    final_cash = cash + shares * Decimal(str(prices[-1]))
    return BacktestResult(initial_cash, final_cash, final_cash / initial_cash - 1, trades, costs)
