"""Tests for the P4-5 unified CLI surface (orion brokers / cycle / lessons-analysis / pipeline)."""

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
    if command == "pipeline":
        from orion.cli.main import _run_pipeline_cli
        return _run_pipeline_cli(system, parsed)
    if command == "frozen-backtest":
        from orion.cli.main import _run_frozen_backtest_cli
        return _run_frozen_backtest_cli(system, parsed)
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


# --------------------------------------------------------------------------- P4-5 pipeline
# ``orion pipeline`` is the audit's "single do-the-work" surface. It must run
# status + filings + factors + cycle in one shot, and each step must be skippable
# so CI can verify the chain cheaply.


class TestPipelineCLI:
    def test_pipeline_runs_all_steps(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["pipeline", "AAPL"])
        assert payload["command"] == "pipeline"
        assert payload["symbol"] == "AAPL"
        assert payload["status"] == "IMPLEMENTED"
        # All four steps present and successful.
        assert "system_status" in payload
        assert payload["filings"]["status"] == "IMPLEMENTED"
        assert payload["factors"]["status"] == "IMPLEMENTED"
        assert "cycle" in payload
        assert payload["cycle"]["status"] == "IMPLEMENTED"

    def test_pipeline_skip_cycle_runs_status_filings_factors_only(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["pipeline", "AAPL", "--skip-cycle"])
        assert "cycle" not in payload
        assert payload["filings"]["status"] == "IMPLEMENTED"
        assert payload["factors"]["status"] == "IMPLEMENTED"

    def test_pipeline_skip_filings(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["pipeline", "AAPL", "--skip-filings"])
        assert payload["filings"]["status"] == "SKIPPED"
        # Other steps still ran.
        assert payload["factors"]["status"] == "IMPLEMENTED"
        assert "cycle" in payload

    def test_pipeline_skip_factors(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process(["pipeline", "AAPL", "--skip-factors"])
        assert payload["factors"]["status"] == "SKIPPED"
        assert payload["filings"]["status"] == "IMPLEMENTED"
        assert "cycle" in payload

    def test_pipeline_survives_filings_failure(self, tmp_path: Path, monkeypatch) -> None:
        """A broken filings provider must not crash the pipeline."""
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        parsed = parser.parse_args(["pipeline", "AAPL"])
        from orion.infrastructure.env import load_env
        load_env()
        from orion.cli.main import _run_pipeline_cli
        from orion.orchestration.system import OrionSystem
        system = OrionSystem()
        def _boom(*a, **kw):
            raise RuntimeError("edgar offline")
        monkeypatch.setattr(system, "fetch_filings", _boom)
        payload = _run_pipeline_cli(system, parsed)
        assert payload["filings"]["status"] == "UNAVAILABLE"
        assert "edgar offline" in payload["filings"]["reason"]
        # Cycle still ran.
        assert "cycle" in payload

    def test_pipeline_survives_factors_failure(self, tmp_path: Path, monkeypatch) -> None:
        """A broken factor engine must not crash the pipeline."""
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        parsed = parser.parse_args(["pipeline", "AAPL"])
        from orion.infrastructure.env import load_env
        load_env()
        from orion.cli.main import _run_pipeline_cli
        from orion.orchestration.system import OrionSystem
        system = OrionSystem()
        def _boom(*a, **kw):
            raise RuntimeError("factor svc down")
        monkeypatch.setattr(system, "compute_factors", _boom)
        payload = _run_pipeline_cli(system, parsed)
        assert payload["factors"]["status"] == "UNAVAILABLE"
        assert "factor svc down" in payload["factors"]["reason"]
        # Filings still ran.
        assert payload["filings"]["status"] == "IMPLEMENTED"

    def test_pipeline_uses_explicit_prices(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        prices = [str(100 + i * 0.1) for i in range(30)]
        payload = _run_in_process(["pipeline", "AAPL", "--prices", *prices])
        assert payload["status"] == "IMPLEMENTED"
        assert payload["factors"]["status"] == "IMPLEMENTED"

    def test_pipeline_with_close_records_reflection(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = _run_in_process([
            "pipeline", "AAPL",
            "--close", "101",
            "--strategy", "PIPELINE-TEST",
        ])
        cycle = payload["cycle"]
        assert cycle["status"] == "IMPLEMENTED"
        assert cycle["strategy"] is not None
        assert cycle["strategy"]["name"] == "PIPELINE-TEST"


class TestPipelineSubprocess:
    def test_orion_pipeline_subprocess(self, tmp_path: Path) -> None:
        """``orion pipeline`` exits 0 and prints parseable JSON."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path("src").resolve()) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; sys.argv=['orion','pipeline','DEMO','--skip-cycle']; from orion.cli import main; main()"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["command"] == "pipeline"
        assert "system_status" in payload
        assert "filings" in payload
        assert "factors" in payload


# --------------------------------------------------------------------------- P3-2 frozen-backtest CLI


class TestFrozenBacktestCLI:
    def test_frozen_backtest_persists_artifact(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        out_dir = tmp_path / "frozen-art"
        payload = _run_in_process([
            "frozen-backtest",
            "--symbol", "DEMO",
            "--artifact-dir", str(out_dir),
        ])
        assert payload["command"] == "frozen-backtest"
        assert payload["status"] == "IMPLEMENTED"
        assert payload["artifact_dir"] == str(out_dir)
        assert "beats_factor_neutral" in payload
        # Files written.
        for name in ("result.json", "holdout.json", "config.json"):
            assert (out_dir / name).is_file()
        # The verdict in config.json matches the in-memory verdict.
        config = json.loads((out_dir / "config.json").read_text())
        assert config["beats_factor_neutral"] == payload["beats_factor_neutral"]

    def test_frozen_backtest_subprocess(self, tmp_path: Path) -> None:
        """``orion frozen-backtest`` exits 0 and prints parseable JSON."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path("src").resolve()) + os.pathsep + env.get("PYTHONPATH", "")
        out_dir = tmp_path / "frozen-cli"
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; sys.argv=['orion','frozen-backtest','--symbol','DEMO','--artifact-dir',r'" + str(out_dir) + r"']; from orion.cli import main; main()"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["command"] == "frozen-backtest"
        assert payload["status"] == "IMPLEMENTED"
        assert (out_dir / "result.json").is_file()
