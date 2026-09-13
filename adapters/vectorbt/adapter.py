"""ORION VectorBT Adapter — Full BacktestEngine Implementation.

Provides vectorized backtesting, parameter sweeps, walk-forward analysis,
and portfolio analytics through the canonical Orion adapter interface.

When vectorbt is installed, uses the library directly.
When absent, falls back to a built-in vectorized engine using numpy or stdlib.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from orion.data.contracts import BacktestResult, Instrument


class VectorBTAdapter:
    """Canonical adapter for VectorBT backtesting engine.

    Translates VectorBT results into canonical Orion BacktestResult schema.
    Provides parameter sweep and walk-forward capabilities.
    """

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "VectorBT"
        self.version = "0.26.1"
        self._vbt = None
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if vectorbt is installed."""
        try:
            import vectorbt as vbt
            self._vbt = vbt
            return True
        except ImportError:
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    def run_backtest(
        self,
        strategy_id: str,
        prices: Sequence[float],
        signals: Sequence[int] | None = None,
        fee_rate_bps: float = 10.0,
        slippage_bps: float = 5.0,
        initial_cash: float = 100000.0,
    ) -> BacktestResult:
        """Run a vectorized backtest.

        Args:
            strategy_id: Strategy identifier.
            prices: Price series.
            signals: Entry signals (1=buy, -1=sell, 0=hold).
            fee_rate_bps: Trading fee in basis points.
            slippage_bps: Slippage in basis points.
            initial_cash: Starting capital.

        Returns:
            Canonical BacktestResult.
        """
        if self._available and self._vbt is not None:
            return self._run_with_vectorbt(
                strategy_id, prices, signals, fee_rate_bps, slippage_bps, initial_cash,
            )
        return self._run_builtin(
            strategy_id, prices, signals, fee_rate_bps, slippage_bps, initial_cash,
        )

    def parameter_sweep(
        self,
        prices: Sequence[float],
        lookback_range: range = range(5, 50, 5),
        fee_rate_bps: float = 10.0,
    ) -> list[dict[str, Any]]:
        """Run parameter sweep over lookback periods.

        Returns a list of results sorted by Sharpe ratio.
        """
        results = []
        for lookback in lookback_range:
            signals = self._momentum_signals(prices, lookback)
            bt = self._run_builtin(
                f"momentum_{lookback}", prices, signals, fee_rate_bps, 5.0, 100000.0,
            )
            results.append({
                "lookback": lookback,
                "sharpe": float(bt.sharpe_ratio),
                "sortino": float(bt.sortino_ratio),
                "max_drawdown": float(bt.max_drawdown_pct),
                "win_rate": float(bt.win_rate_pct),
                "cagr": float(bt.cagr_pct),
                "total_trades": bt.total_trades,
            })
        return sorted(results, key=lambda r: r["sharpe"], reverse=True)

    def walk_forward(
        self,
        prices: Sequence[float],
        train_pct: float = 0.7,
        n_splits: int = 5,
        strategy_id: str = "walk_forward",
    ) -> dict[str, Any]:
        """Walk-forward analysis with train/test splits.

        Returns in-sample and out-of-sample performance comparison.
        """
        n = len(prices)
        split_size = n // n_splits
        results = []

        for i in range(n_splits):
            start = i * split_size
            end = min(start + split_size, n)
            if end - start < 10:
                continue

            train_end = start + int((end - start) * train_pct)
            train_prices = prices[start:train_end]
            test_prices = prices[train_end:end]

            if len(train_prices) < 5 or len(test_prices) < 5:
                continue

            # Train: find best lookback
            best_lookback = 10
            best_sharpe = -999.0
            for lb in range(5, min(30, len(train_prices) // 2)):
                signals = self._momentum_signals(train_prices, lb)
                bt = self._run_builtin(f"train_{lb}", train_prices, signals, 10.0, 5.0, 100000.0)
                if float(bt.sharpe_ratio) > best_sharpe:
                    best_sharpe = float(bt.sharpe_ratio)
                    best_lookback = lb

            # Test: apply best params
            test_signals = self._momentum_signals(test_prices, best_lookback)
            test_bt = self._run_builtin(
                strategy_id, test_prices, test_signals, 10.0, 5.0, 100000.0,
            )

            results.append({
                "split": i,
                "train_sharpe": best_sharpe,
                "test_sharpe": float(test_bt.sharpe_ratio),
                "best_lookback": best_lookback,
                "test_max_dd": float(test_bt.max_drawdown_pct),
            })

        avg_test_sharpe = (
            sum(r["test_sharpe"] for r in results) / len(results)
            if results else 0.0
        )
        avg_train_sharpe = (
            sum(r["train_sharpe"] for r in results) / len(results)
            if results else 0.0
        )

        return {
            "strategy_id": strategy_id,
            "n_splits": len(results),
            "avg_train_sharpe": round(avg_train_sharpe, 4),
            "avg_test_sharpe": round(avg_test_sharpe, 4),
            "overfit_ratio": round(
                avg_test_sharpe / max(avg_train_sharpe, 0.001), 4
            ),
            "splits": results,
        }

    # ── Internal implementations ──────────────────────────────────────

    def _run_with_vectorbt(
        self,
        strategy_id: str,
        prices: Sequence[float],
        signals: Sequence[int] | None,
        fee_bps: float,
        slippage_bps: float,
        initial_cash: float,
    ) -> BacktestResult:
        """Run backtest using the vectorbt library."""
        import numpy as np
        vbt = self._vbt

        close = np.array(prices, dtype=np.float64)

        if signals is None:
            signals_arr = np.ones(len(prices), dtype=int)
        else:
            signals_arr = np.array(signals, dtype=int)

        entries = signals_arr == 1
        exits = signals_arr == -1

        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=initial_cash,
            fees=fee_bps / 10000,
            slippage=slippage_bps / 10000,
            freq="1D",
        )

        stats = pf.stats()
        equity = pf.value().values.tolist()

        return BacktestResult(
            strategy_id=strategy_id,
            start_date=str(datetime.now(timezone.utc).date()),
            end_date=str(datetime.now(timezone.utc).date()),
            cagr_pct=Decimal(str(round(stats.get("Total Return [%]", 0) / max(1, len(prices) / 252), 4))),
            sharpe_ratio=Decimal(str(round(stats.get("Sharpe Ratio", 0), 4))),
            sortino_ratio=Decimal(str(round(stats.get("Sortino Ratio", 0), 4))),
            max_drawdown_pct=Decimal(str(round(abs(stats.get("Max Drawdown [%]", 0)), 4))),
            win_rate_pct=Decimal(str(round(stats.get("Win Rate [%]", 0), 4))),
            profit_factor=Decimal(str(round(stats.get("Profit Factor", 0), 4))),
            total_trades=int(stats.get("Total Trades", 0)),
            turnover=Decimal("0"),
            equity_curve=tuple(equity),
            walk_forward_verified=False,
        )

    def _run_builtin(
        self,
        strategy_id: str,
        prices: Sequence[float],
        signals: Sequence[int] | None,
        fee_bps: float,
        slippage_bps: float,
        initial_cash: float,
    ) -> BacktestResult:
        """Built-in vectorized backtest engine (no external dependencies)."""
        import math

        n = len(prices)
        if n < 2:
            zero = Decimal("0")
            return BacktestResult(
                strategy_id=strategy_id,
                start_date="", end_date="",
                cagr_pct=zero, sharpe_ratio=zero, sortino_ratio=zero,
                max_drawdown_pct=zero, win_rate_pct=zero, profit_factor=zero,
                total_trades=0, turnover=zero,
            )

        # Default signals: buy and hold
        if signals is None:
            signals = [1] + [0] * (n - 1)

        fee = fee_bps / 10000
        slip = slippage_bps / 10000

        cash = initial_cash
        position = 0.0
        equity_curve = [initial_cash]
        trades = 0
        wins = 0
        gross_profit = 0.0
        gross_loss = 0.0
        entry_price = 0.0
        peak = initial_cash

        for i in range(1, n):
            sig = signals[i] if i < len(signals) else 0
            price = prices[i]

            if sig == 1 and position == 0:  # Buy
                adj_price = price * (1 + slip)
                shares = cash / adj_price
                cost = shares * adj_price * fee
                cash -= (shares * adj_price + cost)
                position = shares
                entry_price = adj_price
                trades += 1

            elif sig == -1 and position > 0:  # Sell
                adj_price = price * (1 - slip)
                proceeds = position * adj_price
                cost = proceeds * fee
                pnl = (adj_price - entry_price) * position
                cash += (proceeds - cost)
                if pnl > 0:
                    wins += 1
                    gross_profit += pnl
                else:
                    gross_loss += abs(pnl)
                position = 0
                trades += 1

            equity = cash + position * price
            equity_curve.append(equity)
            peak = max(peak, equity)

        # Final equity
        final_equity = equity_curve[-1]

        # Returns
        daily_returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] > 0
        ]

        # Metrics
        total_return = (final_equity / initial_cash - 1) if initial_cash > 0 else 0
        years = max(n / 252, 0.01)
        cagr = ((final_equity / initial_cash) ** (1 / years) - 1) if initial_cash > 0 and final_equity > 0 else 0

        mean_ret = sum(daily_returns) / max(len(daily_returns), 1)
        std_ret = math.sqrt(
            sum((r - mean_ret) ** 2 for r in daily_returns) / max(len(daily_returns) - 1, 1)
        ) if len(daily_returns) > 1 else 0.001

        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0

        down_returns = [r for r in daily_returns if r < 0]
        down_std = math.sqrt(
            sum(r * r for r in down_returns) / max(len(down_returns), 1)
        ) if down_returns else 0.001
        sortino = (mean_ret / down_std * math.sqrt(252)) if down_std > 0 else 0

        # Max drawdown
        max_dd = 0.0
        peak_eq = equity_curve[0]
        for eq in equity_curve:
            peak_eq = max(peak_eq, eq)
            dd = (peak_eq - eq) / peak_eq if peak_eq > 0 else 0
            max_dd = max(max_dd, dd)

        win_rate = (wins / (trades // 2) * 100) if trades > 1 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        q = Decimal("0.0001")
        return BacktestResult(
            strategy_id=strategy_id,
            start_date="simulated",
            end_date="simulated",
            cagr_pct=Decimal(str(round(cagr * 100, 4))),
            sharpe_ratio=Decimal(str(round(sharpe, 4))),
            sortino_ratio=Decimal(str(round(sortino, 4))),
            max_drawdown_pct=Decimal(str(round(max_dd * 100, 4))),
            win_rate_pct=Decimal(str(round(win_rate, 4))),
            profit_factor=Decimal(str(round(profit_factor, 4))),
            total_trades=trades,
            turnover=Decimal(str(round(trades / max(years, 0.01), 2))),
            equity_curve=tuple(round(e, 2) for e in equity_curve),
            walk_forward_verified=False,
        )

    @staticmethod
    def _momentum_signals(prices: Sequence[float], lookback: int) -> list[int]:
        """Generate momentum signals: buy when price > lookback avg, sell when below."""
        signals = [0] * len(prices)
        for i in range(lookback, len(prices)):
            avg = sum(prices[i - lookback:i]) / lookback
            if prices[i] > avg:
                signals[i] = 1
            elif prices[i] < avg:
                signals[i] = -1
        return signals
