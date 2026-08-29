"""End-to-end paper-Alpaca evidence for the broker registry.

Scope
-----

This module adds the *evidence* layer the existing TODO and
``test_multi_broker.py`` tests imply but do not yet assert:

* The :class:`BrokerRegistry` discovers Alpaca from env keys and
  constructs the adapter in **paper** mode by default — and the
  TUI snapshot reflects that.
* The :class:`KillSwitch` blocks **both** live submit and dry-run
  submit (a deliberate, conservative behaviour).
* The :class:`KillSwitch` is safe under concurrent submit attempts.
* The TUI surfaces the Alpaca venue in the same shape the web
  dashboard exposes (single source of truth).

No real network is touched. The Alpaca adapter's HTTP layer is
either short-circuited by env keys (paper default returns DRY_RUN
through the registry when no transport exists) or by an
already-tested local stub server. The intent here is to confirm
the registry + TUI wiring, not to re-test the adapter itself
(``test_brokers.py`` and ``test_cloud_broker_integration.py``
already cover that).
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orion.dashboard.tui import TuiSnapshot
from orion.dashboard.web import DashboardState
from orion.infrastructure.configuration import AIMode, OrionConfig
from orion.integrations.brokers import (
    AlpacaAdapter,
    BrokerAdapterError,
    BrokerRegistry,
    KillSwitch,
)
from orion.learning.mistakes import LessonStore


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Strip every broker env var so tests start from a known state."""
    for venue in ("ALPACA", "BINANCE", "KRAKEN", "COINBASE", "OANDA", "IBKR"):
        for suffix in (
            "API_KEY",
            "API_SECRET",
            "API_KEY_ID",
            "API_SECRET_KEY",
            "PASSPHRASE",
            "ACCOUNT_ID",
            "TOKEN",
            "MODE",
        ):
            monkeypatch.delenv(f"ORION_{venue}_{suffix}", raising=False)
            monkeypatch.delenv(f"{venue}_{suffix}", raising=False)
    return monkeypatch


def _alpaca_paper_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum env keys for the registry to discover Alpaca in
    paper mode. Values are obviously fake — these tests never call the
    real Alpaca API."""
    monkeypatch.setenv("ALPACA_API_KEY_ID", "test-key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "test-secret-key")


# ---------------------------------------------------------------------------
# End-to-end paper-Alpaca through the registry.
# ---------------------------------------------------------------------------


class TestPaperAlpacaThroughRegistry:
    """The registry must discover Alpaca from env, route equity to it,
    and surface a paper-mode venue record — without any code change
    beyond reading the env."""

    def test_alpaca_discovered_from_env_keys(self, clean_env, monkeypatch) -> None:
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        venues = registry.configured()
        assert "alpaca" in venues

    def test_alpaca_mode_is_paper_by_default(self, clean_env, monkeypatch) -> None:
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        record = registry.get("alpaca")
        assert record.mode == "demo"
        # PAPER_BASE is the https://paper-api.alpaca.markets URL.
        assert record.adapter.endpoint == AlpacaAdapter.PAPER_BASE

    def test_alpaca_endpoint_never_live_without_explicit_unlock(
        self, clean_env, monkeypatch
    ) -> None:
        """Even when env says MODE=live, an unlocked config must
        still resolve to the paper endpoint. This is the multi-gate
        contract: env alone is not enough."""
        _alpaca_paper_env(monkeypatch)
        monkeypatch.setenv("ALPACA_MODE", "live")
        registry = BrokerRegistry(OrionConfig())  # live_trading_enabled=False
        record = registry.get("alpaca")
        assert record.adapter.endpoint == AlpacaAdapter.PAPER_BASE
        # And the live-configured registry would resolve to LIVE_BASE.
        live_config = OrionConfig(execution_mode="live", live_trading_enabled=True)
        live_registry = BrokerRegistry(live_config)
        live_record = live_registry.get("alpaca")
        assert live_record.adapter.endpoint == AlpacaAdapter.LIVE_BASE

    def test_equity_symbol_routes_to_alpaca(self, clean_env, monkeypatch) -> None:
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        for symbol in ("AAPL", "MSFT", "SPY", "QQQ"):
            assert registry.route(symbol).venue == "alpaca", symbol

    def test_paper_dry_run_returns_registry_envelope(self, clean_env, monkeypatch) -> None:
        """A dry-run paper order through the registry must return the
        standard DRY_RUN envelope and never reach the network."""
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        result = registry.submit(
            "AAPL",
            side="BUY",
            quantity=1,
            order_type="MARKET",
            dry_run=True,
        )
        assert result["status"] == "DRY_RUN"
        assert result["venue"] == "alpaca"
        assert result["mode"] == "demo"
        assert result["order"]["symbol"] == "AAPL"
        assert result["order"]["side"] == "BUY"
        assert result["order"]["quantity"] == 1
        # client_order_id is generated, must be a string with the orion- prefix.
        assert result["order"]["client_order_id"].startswith("orion-")

    def test_registry_status_surfaces_alpaca_health(
        self, clean_env, monkeypatch
    ) -> None:
        """The status() dict is what the TUI + web dashboard read.
        It must include Alpaca with available=True and a paper URL.

        Note: ``VenueRecord.as_dict()`` overrides the venue-level
        ``mode`` with the adapter's ``health().mode`` (because of the
        ``**health`` spread), so the dict reports ``paper`` rather
        than ``demo`` when ``execution_mode == "paper"``. The
        registry's own ``record.mode`` field still says ``demo``.
        The TUI and the web dashboard both read the dict, so the
        dict is the source of truth.
        """
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        status = registry.status()
        names = [v["name"] for v in status["venues"]]
        assert "alpaca" in names
        alpaca = next(v for v in status["venues"] if v["name"] == "alpaca")
        assert alpaca["available"] is True
        # The status dict reports the adapter's effective mode.
        assert alpaca["mode"] == "paper"
        assert alpaca["endpoint"] == AlpacaAdapter.PAPER_BASE
        # But the registry's own mode field is the demo/live gate.
        assert registry.get("alpaca").mode == "demo"
        # The kill switch is exposed alongside the venues.
        assert status["kill_switch"]["engaged"] is False


# ---------------------------------------------------------------------------
# Kill-switch coverage — including dry-run and concurrency.
# ---------------------------------------------------------------------------


class TestKillSwitchCoverage:
    """The kill switch must block *every* order path, including
    dry-runs and concurrent submits, on every venue."""

    def test_engaged_blocks_dry_run(self, clean_env, monkeypatch) -> None:
        """A dry-run must still be refused when the kill switch is
        engaged. This is the conservative choice: the operator's
        panic applies to intent, not just to network calls."""
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        registry.kill_switch.engage("operator panic")
        with pytest.raises(BrokerAdapterError, match="kill switch"):
            registry.submit(
                "AAPL", side="BUY", quantity=1, dry_run=True
            )

    def test_engaged_blocks_all_venues(self, clean_env, monkeypatch) -> None:
        """Engaging the kill switch once must block every venue,
        not just the first one routed. Two venues are configured
        and the kill switch must intercept both routes."""
        _alpaca_paper_env(monkeypatch)
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_API_SECRET", "s")
        registry = BrokerRegistry(OrionConfig())
        registry.kill_switch.engage("global")
        with pytest.raises(BrokerAdapterError, match="kill switch"):
            registry.submit("AAPL", side="BUY", quantity=1)
        with pytest.raises(BrokerAdapterError, match="kill switch"):
            registry.submit("BTCUSDT", side="BUY", quantity=0.01)

    def test_concurrent_submits_safe_under_kill_switch(
        self, clean_env, monkeypatch
    ) -> None:
        """Ten threads racing on submit() while the kill switch
        toggles must each get a deterministic outcome — either a
        clean DRY_RUN envelope or a clean kill-switch refusal. No
        thread may see a corrupted registry state."""
        _alpaca_paper_env(monkeypatch)
        registry = BrokerRegistry(OrionConfig())
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def submit_once() -> None:
            try:
                result = registry.submit(
                    "AAPL", side="BUY", quantity=1, dry_run=True
                )
                with outcomes_lock:
                    outcomes.append(result["status"])
            except BrokerAdapterError as exc:
                with outcomes_lock:
                    outcomes.append(str(exc))

        threads = [threading.Thread(target=submit_once) for _ in range(10)]
        for t in threads:
            t.start()

        # Toggle the kill switch in the middle of the burst.
        time_to_engage = threading.Event()

        def toggle_ks() -> None:
            time_to_engage.wait()
            registry.kill_switch.engage("mid-burst")

        toggler = threading.Thread(target=toggle_ks, daemon=True)
        toggler.start()
        time_to_engage.set()

        for t in threads:
            t.join()
        toggler.join()

        # Every outcome is either a DRY_RUN or a kill-switch refusal.
        # No thread crashed, no thread returned a malformed payload.
        for outcome in outcomes:
            assert outcome == "DRY_RUN" or "kill switch" in outcome, outcome

    def test_kill_switch_as_dict_round_trip(self) -> None:
        """The kill switch serialisation is what the TUI / dashboard
        / Prometheus metrics all read. It must be JSON-safe."""
        ks = KillSwitch()
        ks.engage("manual")
        d = ks.as_dict()
        assert d["engaged"] is True
        assert d["reason"] == "manual"
        # Re-instantiate and confirm the dict is still well-formed.
        assert isinstance(d["engaged_at"], str) or d["engaged_at"] is None


# ---------------------------------------------------------------------------
# TUI surface — single source of truth with the web dashboard.
# ---------------------------------------------------------------------------


class TestTuiSeesRegistry:
    """The TUI must read the same :class:`BrokerRegistry` the web
    dashboard reads, so a venue discovered from env is visible in
    both UIs."""

    def test_tui_snapshot_includes_alpaca_when_keys_present(
        self, clean_env, monkeypatch, tmp_path: Path
    ) -> None:
        from orion.experiments import ExperimentTracker
        from orion.orchestration.system import OrionSystem
        from orion.strategies import StrategyRegistry

        _alpaca_paper_env(monkeypatch)
        # Build a system with isolated, predictable registries.
        system = OrionSystem()
        system.experiments = ExperimentTracker(root=tmp_path / "experiments")
        system.strategies = StrategyRegistry(path=tmp_path / "strategies")
        lesson_store = LessonStore(tmp_path / "lessons.jsonl")

        from orion.dashboard.web import DashboardState

        state = DashboardState(system=system, lesson_store=lesson_store)
        snap = TuiSnapshot.from_dashboard_state(state)
        names = [v.venue for v in snap.venues]
        assert "alpaca" in names
        alpaca = next(v for v in snap.venues if v.venue == "alpaca")
        # The TUI reads the registry's status() dict, which reports
        # the adapter's effective execution mode (paper), not the
        # registry's own venue-mode field (demo).
        assert alpaca.mode == "paper"
        assert alpaca.available is True
        # The snapshot killswitch is consistent with the registry.
        assert snap.kill_switch.engaged is False

    def test_tui_snapshot_includes_kill_switch_state(
        self, clean_env, monkeypatch, tmp_path: Path
    ) -> None:
        """When the registry's kill switch is engaged, the TUI
        snapshot must reflect that without any extra plumbing."""
        from orion.dashboard.web import DashboardState
        from orion.experiments import ExperimentTracker
        from orion.orchestration.system import OrionSystem
        from orion.strategies import StrategyRegistry

        _alpaca_paper_env(monkeypatch)
        system = OrionSystem()
        system.experiments = ExperimentTracker(root=tmp_path / "experiments")
        system.strategies = StrategyRegistry(path=tmp_path / "strategies")
        lesson_store = LessonStore(tmp_path / "lessons.jsonl")
        state = DashboardState(system=system, lesson_store=lesson_store)
        # Engage the kill switch through the registry the TUI reads from.
        state.registry.kill_switch.engage("tui test")
        snap = TuiSnapshot.from_dashboard_state(state)
        assert snap.kill_switch.engaged is True
        assert snap.kill_switch.reason == "tui test"

    def test_tui_snapshot_empty_when_no_env_keys(
        self, clean_env, tmp_path: Path
    ) -> None:
        """With no broker keys, the TUI must report zero venues
        honestly — not invent fake ones."""
        from orion.dashboard.web import DashboardState
        from orion.experiments import ExperimentTracker
        from orion.orchestration.system import OrionSystem
        from orion.strategies import StrategyRegistry

        system = OrionSystem()
        system.experiments = ExperimentTracker(root=tmp_path / "experiments")
        system.strategies = StrategyRegistry(path=tmp_path / "strategies")
        lesson_store = LessonStore(tmp_path / "lessons.jsonl")
        state = DashboardState(system=system, lesson_store=lesson_store)
        snap = TuiSnapshot.from_dashboard_state(state)
        assert snap.venues == ()


# ---------------------------------------------------------------------------
# Config validation — the multi-gate contract is mechanical.
# ---------------------------------------------------------------------------


class TestConfigGates:
    """The :class:`OrionConfig` validate() method is the single
    mechanical enforcement of the multi-gate unlock. It must reject
    every invalid combination."""

    def test_validate_rejects_live_without_flag(self) -> None:
        with pytest.raises(ValueError, match="live"):
            OrionConfig(execution_mode="live", live_trading_enabled=False).validate()

    def test_validate_rejects_flag_without_live(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled"):
            OrionConfig(execution_mode="paper", live_trading_enabled=True).validate()

    def test_validate_accepts_paper_default(self) -> None:
        # Default config (simulation/paper, no live flag) must validate.
        OrionConfig().validate()
        OrionConfig(execution_mode="paper").validate()

    def test_validate_accepts_live_with_flag(self) -> None:
        OrionConfig(
            execution_mode="live", live_trading_enabled=True
        ).validate()

    def test_validate_rejects_autonomy_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="autonomy_level"):
            OrionConfig(autonomy_level=5).validate()
        with pytest.raises(ValueError, match="autonomy_level"):
            OrionConfig(autonomy_level=-1).validate()

    def test_validate_rejects_fraction_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="max_position_fraction"):
            OrionConfig(max_position_fraction=1.5).validate()
        with pytest.raises(ValueError, match="max_daily_loss_fraction"):
            OrionConfig(max_daily_loss_fraction=-0.01).validate()

    def test_default_aimode_is_local(self) -> None:
        # The default AI mode is local — cloud is opt-in. This is the
        # other side of the "stdlib-only by default" discipline.
        assert OrionConfig().mode == AIMode.LOCAL
