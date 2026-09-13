"""ORION Lean Adapter — Event-Driven BacktestEngine.

Provides an adapter to QuantConnect's LEAN engine. Runs LEAN as a
subprocess and streams results back into canonical Orion contracts.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from orion.data.contracts import BacktestResult


class LeanAdapter:
    """Canonical adapter for QuantConnect LEAN event-driven engine.

    Executes C# or Python algorithms inside LEAN's local environment
    and maps the results to Orion's BacktestResult.
    """

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "QuantConnect_LEAN"
        # Path to lean-cli executable
        self.lean_cli_path = self.config.get("lean_cli_path", "lean")
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if lean-cli is installed and accessible."""
        try:
            result = subprocess.run(
                [self.lean_cli_path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    def run_algorithm(
        self,
        strategy_id: str,
        algorithm_file_path: Path,
        data_directory: Path | None = None,
        start_date: str = "20200101",
        end_date: str = "20230101",
        cash: float = 100000.0,
    ) -> BacktestResult:
        """Execute a LEAN algorithm.

        Args:
            strategy_id: Unique strategy identifier.
            algorithm_file_path: Path to the .py or .cs algorithm file.
            data_directory: Path to LEAN data directory.
            start_date: YYYYMMDD format.
            end_date: YYYYMMDD format.
            cash: Initial starting capital.

        Returns:
            Canonical BacktestResult.
        """
        if not self._available:
            return self._fallback_result(strategy_id, "LEAN CLI not available")

        if not algorithm_file_path.exists():
            return self._fallback_result(strategy_id, f"Algorithm {algorithm_file_path} not found")

        # In a real institutional deployment, this would use Docker or a remote LEAN cluster.
        # For the local adapter, we simulate the lean backtest call.
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "results"

            cmd = [
                self.lean_cli_path, "backtest",
                str(algorithm_file_path.parent),
                "--output", str(output_dir),
            ]
            if data_directory:
                cmd.extend(["--data-provider-local", str(data_directory)])

            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=600)

                # LEAN outputs a comprehensive JSON stats file
                stats_file = output_dir / "backtest-result.json"
                if stats_file.exists():
                    return self._parse_lean_results(strategy_id, stats_file)
                else:
                    return self._fallback_result(strategy_id, "LEAN execution failed to produce results")

            except subprocess.TimeoutExpired:
                return self._fallback_result(strategy_id, "LEAN execution timed out")

    def _parse_lean_results(self, strategy_id: str, results_file: Path) -> BacktestResult:
        """Parse LEAN JSON output to Orion canonical schema."""
        with open(results_file, "r") as f:
            data = json.load(f)

        stats = data.get("TotalPerformance", {}).get("PortfolioStatistics", {})
        equity = data.get("Charts", {}).get("Strategy Equity", {}).get("Series", {}).get("Equity", {}).get("Values", [])

        # Map LEAN to Orion
        cagr = Decimal(str(stats.get("CompoundingAnnualReturn", 0))) * 100
        sharpe = Decimal(str(stats.get("SharpeRatio", 0)))
        sortino = Decimal(str(stats.get("SortinoRatio", 0)))
        max_dd = Decimal(str(stats.get("Drawdown", 0))) * 100
        win_rate = Decimal(str(stats.get("WinRate", 0))) * 100
        profit_factor = Decimal(str(stats.get("ProfitFactor", 0)))
        trades = int(data.get("TotalOrders", 0))

        equity_curve = [float(point.get("y", 0)) for point in equity]

        q = Decimal("0.0001")
        return BacktestResult(
            strategy_id=strategy_id,
            start_date=data.get("RuntimeStatistics", {}).get("Start Date", ""),
            end_date=data.get("RuntimeStatistics", {}).get("End Date", ""),
            cagr_pct=cagr.quantize(q),
            sharpe_ratio=sharpe.quantize(q),
            sortino_ratio=sortino.quantize(q),
            max_drawdown_pct=max_dd.quantize(q),
            win_rate_pct=win_rate.quantize(q),
            profit_factor=profit_factor.quantize(q),
            total_trades=trades,
            turnover=Decimal("0"),
            equity_curve=tuple(equity_curve),
            walk_forward_verified=False,
        )

    def _fallback_result(self, strategy_id: str, reason: str) -> BacktestResult:
        """Return an empty/failed result when execution cannot proceed."""
        zero = Decimal("0")
        return BacktestResult(
            strategy_id=f"{strategy_id}_FAILED",
            start_date="ERROR", end_date=reason,
            cagr_pct=zero, sharpe_ratio=zero, sortino_ratio=zero,
            max_drawdown_pct=zero, win_rate_pct=zero, profit_factor=zero,
            total_trades=0, turnover=zero,
        )
