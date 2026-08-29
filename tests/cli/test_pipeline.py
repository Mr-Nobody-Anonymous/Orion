"""Tests for the P4-5 unified CLI surface (orion brokers / cycle / lessons-analysis)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orion.cli.main import build_parser
from orion.infrastructure.configuration import OrionConfig
from orion.orchestration.system import OrionSystem


def _run_in_process(args):
    parser = build_parser()
    parsed = parser.parse_args(args)
    from orion.infrastructure.env import load_env
    load_env()
    config = OrionConfig()
    system = OrionSystem(config)
    command = parsed.command
    if command == "brokers":
        from orion.cli.main import _run_brokers_cli
        return _run_brokers_cli(parsed)
    if command == "lessons-analysis":
        from orion.cli.main import _run_lessons_analysis_cli
        return _run_lessons_analysis_cli(system, parsed)
    if command == "cycle":
        from orion.cli.main import _run_cycle_cli
        return _run_cycle_cli(system, parsed)
    if command == "status":
        return system.status()
    raise AssertionError(f"unhandled {command!r}")


class TestBrokersCLI:
    def test_brokers_lists_all_venues(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["brokers"])
        assert payload["catalogue"]["count"] == 6
        venues = {entry["venue"] for entry in payload["catalogue"]["venues"]}
        assert venues == {"alpaca", "binance", "kraken", "coinbase", "oanda", "ibkr"}

    def test_brokers_missing_only(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["brokers", "--missing-only"])
        assert len(payload["catalogue"]["venues"]) == 6
        venues = {entry["venue"] for entry in payload["catalogue"]["venues"]}
        assert "binance" in venues


class TestLessonsAnalysisCLI:
    def test_lessons_analysis_default(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        system = OrionSystem()
        from orion.learning.mistakes import TradeOutcome
        system.record_trade_outcome(TradeOutcome(
            symbol="AAPL", side="buy", quantity=1, entry_price=100, exit_price=95,
            predicted_return=0.05, mode="simulation", regime="trending", equity=100000.0,
        ))
        payload = _run_in_process(["lessons-analysis", "--top", "3"])
        assert payload["status"] == "IMPLEMENTED"
        assert "all_time" in payload
        assert "by_kind" in payload["all_time"]

    def test_lessons_analysis_filter(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["lessons-analysis", "--symbol", "AAPL"])
        assert payload["all_time"]["by_symbol"] == {}


class TestCycleCLI:
    def test_cycle_returns_full_payload(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["cycle", "AAPL", "--close", "97", "--strategy", "TEST"])
        assert payload["status"] == "IMPLEMENTED"
        cycle = payload["cycle"]
        assert "lessons" in cycle
        assert "order" in cycle
        assert cycle["strategy"]["name"] == "TEST"

    def test_cycle_without_close_omits_lessons(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["cycle", "AAPL"])
        assert payload["cycle"]["lessons"] == []
        assert payload["cycle"]["strategy"] is None


class TestSubprocessSmoke:
    def test_orion_brokers_subprocess(self, tmp_path: Path) -> None:
        """``orion brokers`` exits 0 and prints parseable JSON.

        Invoked through the entry-point declared in ``pyproject.toml``
        (``orion = "orion.__main__:main"``), not via the runpy module
        path which triggers a different code path.
        """
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path("src").resolve()) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; sys.argv=['orion','brokers']; from orion.cli import main; main()"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["catalogue"]["count"] == 6
