"""End-to-end workflow test for ORION.

Exercises the complete documented workflow:

    1. Initialize the system
    2. Load data (use synthetic prices)
    3. Research
    4. Compute factors and portfolio weights
    5. Run the agent hierarchy for a decision
    6. Run the 16-phase executive loop
    7. Simulate
    8. Backtest
    9. Evaluate (P0-3 ablation lab)
    10. Train
    11. Doctor (HEALTHY)
    12. CLI smoke (status, doctor, factors, optimize, agents, filings, compliance, distributed)

This is the canonical "fresh operator" test. If this passes, ORION
works as documented.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.orchestration.system import OrionSystem


PRICES = [
    100, 101, 102, 103, 104, 103, 102, 101, 100, 99,
    100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
    110, 111, 112, 113, 114, 115, 116, 117, 118, 119,
    120, 121, 122, 123, 124, 125, 126, 127, 128, 129,
    130, 131, 132, 133, 134, 135, 136, 137, 138, 139,
    140, 141, 142, 143, 144, 145, 146, 147, 148, 149,
    150, 151, 152, 153, 154, 155, 156, 157, 158, 159,
    160, 161, 162, 163, 164, 165, 166, 167, 168, 169,
    170, 171, 172, 173, 174, 175, 176, 177, 178, 179,
    180, 181, 182, 183, 184, 185, 186, 187, 188, 189,
]


def test_full_workflow_end_to_end() -> None:
    """Run the complete documented workflow in-process."""
    system = OrionSystem()

    # 1. status
    status = system.status()
    assert status["mode"] == "local"
    assert status["capabilities"]["live_execution"] == "BLOCKED"

    # 2. doctor (HEALTHY)
    doctor = system.doctor()
    assert doctor["status"] == "HEALTHY"

    # 3. Run cycle
    asset = Asset("AAPL", AssetClass.EQUITY)
    cycle = system.run(asset, PRICES)
    assert cycle["decision"] in {"BUY", "SELL", "HOLD", "WAIT", "SHORT"}
    assert "fills" in cycle
    assert "market_regime" in cycle

    # 4. Council
    council = system.council("AAPL", PRICES)
    assert "members" in council
    assert "prediction" in council

    # 5. Backtest
    backtest = system.backtest(PRICES)
    assert "metrics" in backtest

    # 6. Simulate
    sim = system.simulate(PRICES)
    assert sim["status"] == "IMPLEMENTED"
    assert sim["terminal_p05"] <= sim["terminal_mean"] <= sim["terminal_p95"]

    # 7. Benchmark
    bench = system.benchmark(PRICES)
    assert bench["status"] == "IMPLEMENTED"

    # 8. Train
    train = system.train()
    assert "model" in train
    assert "status" in train

    # 9. Evaluate (P0-3 ablation lab)
    eval_result = system.run_evaluation("AAPL", PRICES)
    assert "run_id" in eval_result
    assert "artifact_dir" in eval_result
    assert "report" in eval_result

    # 10. Evolve
    evo = system.evolve(PRICES, population_size=4)
    assert evo["status"] == "EXPERIMENTAL"
    assert evo["generation"] >= 0

    # 11. Research (will BLOCK without network, that's expected)
    research = system.research("robust financial time series forecasting", limit=2)
    assert "status" in research
    # The research layer may return SUFFICIENT_METADATA (when OpenAlex responds),
    # INSUFFICIENT_EVIDENCE (when too few sources are found), or BLOCKED (on network failure).
    assert research["status"] in {"OK", "BLOCKED", "SUFFICIENT_METADATA", "INSUFFICIENT_EVIDENCE"}

    # 12. P1-5: filings
    filings = system.fetch_filings(asset)
    assert filings["status"] == "IMPLEMENTED"
    assert "bundle" in filings

    # 13. P1-6: factors
    factors = system.compute_factors(PRICES, factors=("momentum", "value"))
    assert factors["status"] == "IMPLEMENTED"
    assert len(factors["signals"]) == 2

    # 14. P1-6: factor exposures
    strategy_returns = [0.01, -0.02, 0.03, -0.01, 0.02, 0.04, -0.03, 0.01, 0.0, 0.05]
    factor_returns = {name: [0.0] * 10 for name in system.factor_names}
    factor_returns["momentum"] = [0.005, -0.015, 0.020, -0.005, 0.010, 0.030, -0.020, 0.005, 0.0, 0.040]
    exposures = system.factor_exposures(strategy_returns, factor_returns, factor_names=("momentum", "value"))
    assert exposures["status"] == "IMPLEMENTED"

    # 15. P2-2: agent hierarchy
    agents = system.run_agents("AAPL", PRICES)
    assert agents["status"] == "IMPLEMENTED"
    assert agents["report"]["final_verdict"] in {"ALLOW", "BLOCK", "NEEDS_REVIEW"}

    # 16. P2-5: portfolio optimizer
    opt = system.optimize_portfolio(
        {"AAPL": 0.08, "MSFT": 0.06, "GOOGL": 0.04},
        volatilities={"AAPL": 0.25, "MSFT": 0.20, "GOOGL": 0.30},
        method="mvp",
    )
    assert opt["status"] == "IMPLEMENTED"
    weights = opt["result"]["weights"]
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)

    # 17. P2-3: compliance audit chain
    system.audit_log.append("test", "promote", {"candidate": "x"})
    ok, _ = system.audit_log.verify()
    assert ok

    # 18. P2-4: distributed queue
    drained = system.distributed_drain()
    assert set(drained.keys()) == {
        "research", "backtest", "training", "evolution", "llm", "simulation", "data"
    }


def test_cli_smoke_full_workflow() -> None:
    """Run the complete documented workflow via the CLI."""
    repo = "c:\\Users\\hp\\Desktop\\Orion"
    cmds = [
        ["status"],
        ["doctor"],
        ["factors", "--prices", "100", "101", "102", "103", "104", "105",
         "106", "107", "108", "109", "110", "111", "112", "113", "114", "115",
         "116", "117", "118", "119", "120", "121", "122", "123", "124", "125",
         "126", "127", "128", "129", "130", "131", "132", "133", "134", "135"],
        ["optimize", "--method", "mvp", "--symbols", "A", "B", "C",
         "--volatilities", "0.2", "0.3", "0.25"],
        ["agents", "AAPL", "--prices", "100", "101", "102", "103", "104", "105"],
        ["filings", "AAPL", "--use-reference"],
        ["compliance", "--restricted", "MSFT", "--check-symbol", "MSFT",
         "--audit-action", "test"],
        ["distributed", "--pool", "research", "--drain"],
        ["dashboard", "--candidate-id", "cand-x", "--decision", "DEFER", "--json"],
    ]
    for cmd in cmds:
        result = subprocess.run(
            [sys.executable, "-m", "orion", *cmd],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        assert "hardware" in payload
        assert "model_tier" in payload
