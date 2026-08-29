"""End-to-end tests for the mission-control web server (localhost only)."""

from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import pytest

from orion.dashboard.web import DashboardState, create_server
from orion.learning.mistakes import LessonStore, TradeOutcome


@pytest.fixture()
def server(tmp_path: Path):
    from orion.experiments import ExperimentTracker
    from orion.orchestration.system import OrionSystem
    from orion.strategies import StrategyRegistry

    system = OrionSystem()
    # Isolate per-test registries so the web endpoints are deterministic.
    system.experiments = ExperimentTracker(root=tmp_path / "experiments")
    system.strategies = StrategyRegistry(path=tmp_path / "strategies")
    state = DashboardState(system=system, lesson_store=LessonStore(tmp_path / "lessons.jsonl"))
    httpd = create_server(state, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    base = f"http://{host}:{port}"
    yield base, state
    httpd.shutdown()
    httpd.server_close()


def get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(base: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class TestWebServer:
    def test_index_serves_html(self, server) -> None:
        base, _ = server
        with urllib.request.urlopen(base + "/", timeout=10) as resp:
            html = resp.read().decode("utf-8")
        assert "ORION" in html
        assert "<canvas" in html
        assert "Peer-AI council" in html

    def test_status_endpoint(self, server) -> None:
        base, _ = server
        payload = get(base, "/api/status")
        assert payload["banner"] == "ORION MISSION CONTROL"
        assert "equity_history" in payload
        assert payload["live_trading_enabled"] is False

    def test_brokers_endpoint(self, server) -> None:
        base, _ = server
        payload = get(base, "/api/brokers")
        assert "kill_switch" in payload
        assert isinstance(payload["venues"], list)

    def test_lessons_endpoint(self, server) -> None:
        base, _ = server
        payload = get(base, "/api/lessons")
        assert payload["recent"] == []
        assert isinstance(payload["counts"], dict)

    def test_market_endpoint(self, server) -> None:
        base, _ = server
        payload = get(base, "/api/market")
        assert len(payload["prices"]) >= 3
        assert "prediction" in payload

    def test_unknown_path_404(self, server) -> None:
        base, _ = server
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            get(base, "/api/nope")
        assert excinfo.value.code == 404

    def test_reflect_endpoint_records_lesson(self, server) -> None:
        base, state = server
        result = post(base, "/api/reflect", {
            "symbol": "AAPL", "side": "buy", "quantity": 10,
            "entry_price": 100, "exit_price": 96,
            "predicted_return": 0.02, "mode": "simulation",
            "equity": 100000,
        })
        assert result["lessons"]
        assert result["summary"]["replay"]["size"] == 1
        assert len(state.lesson_store.recent(5)) == 1

    def test_killswitch_roundtrip(self, server) -> None:
        base, state = server
        engaged = post(base, "/api/killswitch", {"engaged": True, "reason": "test"})
        assert engaged["kill_switch"]["engaged"] is True
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            post(base, "/api/trade", {"symbol": "AAPL", "side": "BUY", "quantity": 1})
        assert excinfo.value.code == 409
        disengaged = post(base, "/api/killswitch", {"engaged": False})
        assert disengaged["kill_switch"]["engaged"] is False

    def test_trade_dry_run(self, server) -> None:
        base, state = server
        with pytest.raises(urllib.error.HTTPError):
            # No venues configured in the test env: dry-run still needs a route.
            post(base, "/api/trade", {"symbol": "AAPL", "side": "BUY", "quantity": 1, "dry_run": True})

    def test_deliberate_without_peers(self, server) -> None:
        base, state = server
        state.cloud_providers = []
        result = post(base, "/api/deliberate", {"question": "regime?"})
        assert result["insights"] == []
        assert result["consensus"] is None

    def test_strategies_endpoint_empty(self, server) -> None:
        base, _ = server
        payload = get(base, "/api/strategies")
        assert payload["summary"]["strategies"] == 0

    def test_register_and_promote_strategy(self, server) -> None:
        base, state = server
        registered = post(base, "/api/register-strategy", {
            "name": "WEB-STRAT",
            "rules": {"entry": "momentum", "lookback": 20},
            "universe": ["SPY"],
            "lineage": ["ds-a", "feat-b", "model-c"],
            "backtest_ref": "bt-9",
        })
        assert registered["strategy"]["version"] == "v1"
        owner = post(base, "/api/promote-strategy", {"name": "WEB-STRAT", "target": "validating"})
        assert owner["strategy"]["status"] == "validating"
        payload = get(base, "/api/strategies")
        assert payload["summary"]["strategies"] == 1
        assert payload["strategies"][0]["lineage"]["backtest"] == "bt-9"

    def test_experiments_endpoint(self, server) -> None:
        base, state = server
        started = post(base, "/api/start-experiment", {"name": "dash-run", "tags": {"ui": "web"}})
        assert started["experiment"]["name"] == "dash-run"
        payload = get(base, "/api/experiments")
        assert payload["summary"]["experiments"] == 1
        assert payload["recent"][0]["tags"]["ui"] == "web"