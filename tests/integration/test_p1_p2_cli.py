"""End-to-end tests for the P1-5 / P1-6 / P2 CLI subcommands."""

from __future__ import annotations

import json
import math
import subprocess
import sys


def _run(*args: str) -> dict:
    """Run ``python -m orion ...`` and return the parsed JSON payload."""
    result = subprocess.run(
        [sys.executable, "-m", "orion", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd="c:\\Users\\hp\\Desktop\\Orion",
    )
    return json.loads(result.stdout)


def test_cli_factors_runs() -> None:
    payload = _run(
        "factors",
        "--prices",
        "100", "101", "102", "103", "102", "101", "100", "99", "98",
        "99", "100", "101", "102", "103", "104", "105", "106", "107", "108",
        "109", "110", "111", "112", "113", "114", "115", "116", "117", "118",
        "119", "120",
        "--factor", "momentum",
        "--factor", "value",
    )
    assert payload["command"] == "factors"
    assert payload["prices_count"] == 31
    names = [s["name"] for s in payload["signals"]]
    assert names == ["momentum", "value"]


def test_cli_optimize_mvo() -> None:
    payload = _run(
        "optimize",
        "--method", "mvo",
        "--symbols", "AAPL", "MSFT", "GOOGL",
        "--volatilities", "0.25", "0.20", "0.30",
        "--returns", "0.10", "0.08", "0.12",
    )
    assert payload["command"] == "optimize"
    weights = payload["result"]["weights"]
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-6)


def test_cli_agents_runs() -> None:
    payload = _run(
        "agents", "AAPL",
        "--prices", "100", "101", "102", "103", "104", "105",
        "106", "107", "108", "109", "110",
    )
    assert payload["command"] == "agents"
    assert payload["symbol"] == "AAPL"
    assert payload["report"]["final_verdict"] in {"ALLOW", "BLOCK", "NEEDS_REVIEW"}


def test_cli_dashboard_json() -> None:
    payload = _run(
        "dashboard",
        "--candidate-id", "cand-x",
        "--decision", "APPROVE",
        "--summary", "Smoke test",
        "--json",
    )
    assert payload["command"] == "dashboard"
    assert payload["card"]["candidate_id"] == "cand-x"


def test_cli_compliance_audit_chain() -> None:
    payload = _run(
        "compliance",
        "--restricted", "AAPL", "MSFT",
        "--check-symbol", "AAPL",
        "--audit-action", "test-action",
    )
    assert payload["command"] == "compliance"
    assert "AAPL" in payload["restricted_symbols"]
    assert payload["check"]["restricted"] is True
    assert payload["audit"]["verify_ok"] is True


def test_cli_distributed_drain() -> None:
    payload = _run("distributed", "--pool", "research", "--drain")
    assert payload["command"] == "distributed"
    assert payload["pool"] == "research"
    assert payload["drained"] == 0
