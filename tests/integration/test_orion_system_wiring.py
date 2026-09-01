"""End-to-end tests for the wired-in P1-5 / P1-6 / P2 modules on OrionSystem."""

from __future__ import annotations

import math

from orion.data.contracts import Asset, AssetClass
from orion.orchestration.system import OrionSystem


def test_system_exposes_filings_manager() -> None:
    system = OrionSystem()
    assert system.filings is not None
    status = system.filings.status()
    assert status.sec["configured"] is True
    assert status.news["configured"] is True
    assert status.earnings["configured"] is True


def test_system_exposes_agents_with_full_hierarchy() -> None:
    system = OrionSystem()
    assert system.agents is not None
    # 7 default agents
    assert len(system.agents._agents) == 7


def test_system_exposes_compliance_scaffolding() -> None:
    system = OrionSystem()
    assert system.audit_log is not None
    assert system.rbac is not None
    assert system.restricted_list is not None
    system.audit_log.append("test", "action", {"x": 1})
    assert len(system.audit_log.records()) == 1


def test_system_exposes_distributed_controller() -> None:
    system = OrionSystem()
    assert system.distributed is not None
    assert system.distributed.pools is not None
    pools = system.distributed.pools
    assert pools.research is not None
    assert pools.backtest is not None
    assert pools.training is not None


def test_system_compute_factors_default_set() -> None:
    system = OrionSystem()
    prices = [100 + i * 0.1 for i in range(60)]
    payload = system.compute_factors(prices)
    assert payload["status"] == "IMPLEMENTED"
    assert len(payload["signals"]) == len(system.factor_names)


def test_system_compute_factors_subset() -> None:
    system = OrionSystem()
    prices = [100 + i * 0.1 for i in range(60)]
    payload = system.compute_factors(prices, factors=("momentum", "value"))
    names = {s["name"] for s in payload["signals"]}
    assert names == {"momentum", "value"}


def test_system_factor_exposures_runs() -> None:
    system = OrionSystem()
    strategy_returns = [0.01, -0.02, 0.03, -0.01, 0.02, 0.04, -0.03, 0.01, 0.0, 0.05]
    factor_returns = {name: [0.0] * 10 for name in system.factor_names}
    factor_returns["momentum"] = [0.005, -0.015, 0.020, -0.005, 0.010, 0.030, -0.020, 0.005, 0.0, 0.040]
    payload = system.factor_exposures(strategy_returns, factor_returns, factor_names=("momentum", "value"))
    assert payload["status"] == "IMPLEMENTED"
    assert "alpha" in payload["report"]
    assert "r_squared" in payload["report"]


def test_system_fetch_filings_uses_reference() -> None:
    system = OrionSystem()
    asset = Asset("AAPL", AssetClass.EQUITY)
    payload = system.fetch_filings(asset)
    assert payload["status"] == "IMPLEMENTED"
    assert "bundle" in payload


def test_system_run_agents_routes_through_hierarchy() -> None:
    system = OrionSystem()
    payload = system.run_agents("AAPL", [100, 101, 102, 103, 104, 105])
    assert payload["status"] == "IMPLEMENTED"
    assert payload["report"]["final_verdict"] in {"ALLOW", "NEEDS_REVIEW", "BLOCK"}


def test_system_optimize_portfolio_mvp() -> None:
    system = OrionSystem()
    payload = system.optimize_portfolio(
        {"A": 0.05, "B": 0.05},
        volatilities={"A": 0.2, "B": 0.3},
        method="mvp",
    )
    assert payload["status"] == "IMPLEMENTED"
    weights = payload["result"]["weights"]
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)


def test_system_doctor_reports_all_systems() -> None:
    system = OrionSystem()
    payload = system.doctor()
    assert payload["status"] == "HEALTHY"
    checks = payload["checks"]
    assert checks["filings"] == "PASS"
    assert checks["agents"] == "PASS"
    assert checks["compliance"] == "PASS"
    assert checks["distributed"] == "PASS"


# --------------------------------------------------------------------------- P3-3
# ``OrionSystem.run`` must wire filings + factor exposures into its payload so
# the per-cycle decision context carries the audit-traceable external signals
# (news, earnings, factor betas).  Failures in either source are demoted to
# ``UNAVAILABLE`` so a broken provider cannot break the cycle.


def test_run_includes_filings_and_factors_in_payload() -> None:
    system = OrionSystem()
    asset = Asset("AAPL", AssetClass.EQUITY)
    prices = [100 + i * 0.1 for i in range(60)]
    payload = system.run(asset, prices)
    assert "decision" in payload
    assert "filings" in payload
    assert "factors" in payload
    # Default providers are configured so the success path is the expected one.
    assert payload["filings"]["status"] == "IMPLEMENTED"
    assert payload["factors"]["status"] == "IMPLEMENTED"
    assert "bundle" in payload["filings"]
    assert "signals" in payload["factors"]


def test_run_survives_filings_failure(monkeypatch) -> None:
    """A broken filings source must not break the cycle."""
    system = OrionSystem()

    def _boom(asset, **kwargs):
        raise RuntimeError("filings down")

    monkeypatch.setattr(system, "fetch_filings", _boom)
    asset = Asset("AAPL", AssetClass.EQUITY)
    prices = [100 + i * 0.1 for i in range(60)]
    payload = system.run(asset, prices)
    assert payload["filings"]["status"] == "UNAVAILABLE"
    assert "filings down" in payload["filings"]["reason"]
    # The cycle itself still completed.
    assert "decision" in payload


def test_run_survives_factor_failure(monkeypatch) -> None:
    """A broken factor source must not break the cycle."""
    system = OrionSystem()

    def _boom(prices, factors=()):
        raise RuntimeError("factor engine exploded")

    monkeypatch.setattr(system, "compute_factors", _boom)
    asset = Asset("AAPL", AssetClass.EQUITY)
    prices = [100 + i * 0.1 for i in range(60)]
    payload = system.run(asset, prices)
    assert payload["factors"]["status"] == "UNAVAILABLE"
    assert "factor engine exploded" in payload["factors"]["reason"]
    assert "decision" in payload


def test_run_factor_signals_match_default_set() -> None:
    """The wire-up must expose the same factor set ``compute_factors`` does."""
    system = OrionSystem()
    asset = Asset("AAPL", AssetClass.EQUITY)
    prices = [100 + i * 0.1 for i in range(60)]
    payload = system.run(asset, prices)
    signal_names = {s["name"] for s in payload["factors"]["signals"]}
    assert signal_names == set(system.factor_names)
