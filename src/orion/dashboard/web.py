"""ORION Mission Control — a stdlib-only web dashboard.

Serves a single-page, dark "mission control" UI from
:class:`DashboardState`, which wraps the live :class:`OrionSystem`,
the :class:`BrokerRegistry`, the :class:`PeerAICouncil`, and the
:class:`LessonStore`. Everything the page shows is real state from
those objects — nothing is mocked.

Endpoints (JSON)
----------------

* ``GET  /api/status``       — system + config + equity history
* ``GET  /api/brokers``      — venue discovery + kill switch state
* ``GET  /api/peers``        — cloud AI peers + latest insights
* ``GET  /api/lessons``      — recent lessons + mistake counts
* ``GET  /api/market``       — demo price series + ensemble forecast
* ``POST /api/cycle``        — run one decision cycle (safe simulated broker)
* ``POST /api/trade``        — route an order to a venue (dry-run by default)
* ``POST /api/killswitch``   — engage / disengage the kill switch
* ``POST /api/reflect``      — feed a trade outcome to the mistake analyzer
* ``POST /api/deliberate``   — ask the peer-AI council a question

Run with ``python -m orion.cli.main serve`` (binds 127.0.0.1 by default).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ..integrations.brokers import BrokerAdapterError, BrokerRegistry, KillSwitch
from ..learning.mistakes import LessonStore, MistakeAnalyzer, TradeOutcome
from ..models.cloud.factory import create_cloud_providers_from_env
from ..orchestration.system import OrionSystem

_ORION_BANNER = "ORION MISSION CONTROL"


class DashboardState:
    """Holds the live objects the dashboard reads from."""

    def __init__(
        self,
        system: OrionSystem | None = None,
        *,
        registry: BrokerRegistry | None = None,
        lesson_store: LessonStore | None = None,
        cloud_providers: list[Any] | None = None,
    ) -> None:
        self.system = system or OrionSystem()
        # Bridge: the dashboard's own registry is *the* system's broker
        # registry. This way a kill switch flipped on the system is
        # visible on the TUI and the web, with no parallel state.
        self.registry = registry if registry is not None else self.system.broker_registry
        self.lesson_store = lesson_store or LessonStore()
        self.analyzer = MistakeAnalyzer(store=self.lesson_store)
        self.cloud_providers = (
            cloud_providers if cloud_providers is not None else create_cloud_providers_from_env()
        )
        self.equity_history: list[float] = [100_000.0]
        self.trade_log: list[dict[str, Any]] = []
        self.peer_insights: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------ snapshots

    def api_status(self) -> dict[str, Any]:
        config = self.system.config
        return {
            "banner": _ORION_BANNER,
            "mode": getattr(config.mode, "value", str(config.mode)),
            "execution_mode": config.execution_mode,
            "live_trading_enabled": config.live_trading_enabled,
            "autonomy_level": config.autonomy_level,
            "limits": {
                "max_position_fraction": config.max_position_fraction,
                "max_portfolio_exposure": config.max_portfolio_exposure,
                "max_daily_loss_fraction": config.max_daily_loss_fraction,
            },
            "equity_history": self.equity_history[-120:],
            "trades": self.trade_log[-30:],
        }

    def api_brokers(self) -> dict[str, Any]:
        return self.registry.status()

    def api_peers(self) -> dict[str, Any]:
        from ..intelligence.peer_ai import PeerAICouncil
        from ..models.cloud.factory import create_cloud_providers_from_env

        council = PeerAICouncil(providers=create_cloud_providers_from_env())
        return {
            "available": council.available,
            "peers": council.peer_status(),
            "insights": [insight.as_dict() for insight in council.recent_insights(20)],
        }

    def api_lessons(self) -> dict[str, Any]:
        return {
            "recent": self.lesson_store.recent(15),
            "counts": self.lesson_store.by_kind(),
            "replay": self.analyzer.replay.summary() if len(self.analyzer.replay) else {"size": 0},
            "analysis": self.system.learner.analysis() if hasattr(self.system, "learner") else {},
        }

    def api_strategies(self) -> dict[str, Any]:
        from ..strategies import StrategyRegistry

        registry: StrategyRegistry = self.system.strategies
        return {
            "summary": registry.summary(),
            "strategies": [
                {
                    "name": name,
                    "latest": registry.get(name).describe(),  # type: ignore[union-attr] - names() derives from the registry
                    "lineage": registry.lineage(name),
                }
                for name in registry.names()
            ],
        }

    def api_brokers(self) -> dict[str, Any]:
        from ..integrations.brokers import catalogue_as_dict, missing_keys_all, ping_all

        # Live venue state (the ones the registry actually constructed).
        venues_live = [record.as_dict() for record in sorted(
            self.registry._venues.values(), key=lambda r: r.venue
        )]
        return {
            # Live venues (consumed by the TUI venue strip + kill-switch card).
            "venues": venues_live,
            "kill_switch": self.registry.kill_switch.as_dict(),
            # Static catalogue (consumed by the dashboard "venue grid" card).
            "catalogue": catalogue_as_dict(),
            "missing_keys": missing_keys_all(),
            "health": [health.as_dict() for health in ping_all(timeout=0.5)],
        }

    def api_experiments(self) -> dict[str, Any]:
        return {
            "summary": self.system.experiments.summary(),
            "recent": [record.as_dict() for record in self.system.experiments.list()[-20:]],
        }

    def api_hardware(self) -> dict[str, Any]:
        if self.system.hardware_profile is None:
            self.system.snapshot_hardware()
        return {
            "hardware": self.system.hardware_profile.as_dict(),
            "tiers": {key: dict(value) for key, value in DEFAULT_TIERS.items()},
        }

    def api_market(self, prices: list[float] | None = None) -> dict[str, Any]:
        from dataclasses import asdict

        from ..data.contracts import Asset, AssetClass

        series = prices or [100, 101, 100.5, 102, 103, 104, 105]
        asset = Asset("DEMO", AssetClass.EQUITY)
        prediction = self.system.forecaster.predict(asset, series)
        return {"prices": series, "prediction": asdict(prediction)}

    # -------------------------------------------------------------- actions

    def run_cycle(self, symbol: str, prices: list[float]) -> dict[str, Any]:
        """Run one decision cycle through the safe simulated broker."""
        from ..data.contracts import Asset, AssetClass

        result = self.system.run(Asset(symbol, AssetClass.EQUITY), prices)
        backtest = result.get("backtest", {}) if isinstance(result, dict) else {}
        total_return = float(backtest.get("total_return", 0.0) or 0.0)
        with self._lock:
            self.trade_log.append(
                {
                    "kind": "cycle",
                    "symbol": symbol,
                    "decision": result.get("decision") if isinstance(result, dict) else None,
                    "total_return": total_return,
                }
            )
            base = self.equity_history[-1] if self.equity_history else 100_000.0
            self.equity_history.append(round(base * (1.0 + total_return / 10.0), 2))
        return result

    def place_trade(
        self,
        symbol: str,
        *,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: float | None = None,
        venue: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        result = self.registry.submit(
            symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            venue=venue,
            dry_run=dry_run,
        )
        with self._lock:
            self.trade_log.append({"kind": "order", **result})
        return result

    def set_kill_switch(self, engaged: bool, reason: str = "manual") -> dict[str, Any]:
        if engaged:
            self.registry.kill_switch.engage(reason)
        else:
            self.registry.kill_switch.disengage()
        return self.registry.kill_switch.as_dict()

    def reflect(self, outcome: TradeOutcome) -> dict[str, Any]:
        lessons = self.analyzer.analyze(outcome)
        return {"lessons": [lesson.as_dict() for lesson in lessons], "summary": self.analyzer.summary()}

    def deliberate(self, question: str) -> dict[str, Any]:
        from ..intelligence.peer_ai import PeerAICouncil

        council = PeerAICouncil(providers=self.cloud_providers)
        insights = council.deliberate(question)
        with self._lock:
            self.peer_insights.extend(insight.as_dict() for insight in insights)
        return {
            "insights": [insight.as_dict() for insight in insights],
            "failures": [failure.as_dict() for failure in council.failures],
            "consensus": council.consensus(),
        }


class _DashboardHandler(BaseHTTPRequestHandler):
    """JSON API + single-page UI handler. ``state`` is injected server-side."""

    state: DashboardState
    server_version = "OrionMissionControl/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep stdout clean
        pass

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object")
        return parsed

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        state = self.state
        if self.path in ("/", "/index.html"):
            from .page import render_page

            body = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/p4" or self.path == "/p4/index.html":
            from .page_p4 import render_p4_page

            body = render_p4_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            if self.path == "/api/status":
                self._send_json(state.api_status())
            elif self.path == "/api/brokers":
                self._send_json(state.api_brokers())
            elif self.path == "/api/peers":
                self._send_json(state.api_peers())
            elif self.path == "/api/lessons":
                self._send_json(state.api_lessons())
            elif self.path == "/api/strategies":
                self._send_json(state.api_strategies())
            elif self.path == "/api/experiments":
                self._send_json(state.api_experiments())
            elif self.path == "/api/hardware":
                self._send_json(state.api_hardware())
            elif self.path == "/api/brokers":
                self._send_json(state.api_brokers())
            elif self.path == "/api/market":
                self._send_json(state.api_market())
            else:
                self._send_error_json(404, f"unknown path {self.path}")
        except Exception as exc:  # noqa: BLE001 - the API never crashes the server
            self._send_error_json(500, str(exc))

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        state = self.state
        try:
            body = self._read_json_body()
            if self.path == "/api/cycle":
                symbol = str(body.get("symbol", "DEMO")).strip() or "DEMO"
                prices = [float(p) for p in body.get("prices", [])] or None
                if prices is None:
                    prices = state.api_market()["prices"]
                self._send_json({"result": state.run_cycle(symbol, prices)})
            elif self.path == "/api/trade":
                symbol = str(body.get("symbol", "")).strip()
                if not symbol:
                    raise ValueError("symbol is required")
                self._send_json(
                    state.place_trade(
                        symbol,
                        side=str(body.get("side", "BUY")),
                        quantity=float(body.get("quantity", 0)),
                        order_type=str(body.get("order_type", "MARKET")),
                        price=body.get("price"),
                        venue=body.get("venue") or None,
                        dry_run=bool(body.get("dry_run", True)),
                    )
                )
            elif self.path == "/api/killswitch":
                self._send_json(
                    {
                        "kill_switch": state.set_kill_switch(
                            bool(body.get("engaged", True)),
                            str(body.get("reason", "manual")),
                        )
                    }
                )
            elif self.path == "/api/reflect":
                outcome = TradeOutcome(
                    symbol=str(body.get("symbol", "DEMO")),
                    side=str(body.get("side", "buy")),
                    quantity=float(body.get("quantity", 0)),
                    entry_price=float(body.get("entry_price", 0)),
                    exit_price=float(body.get("exit_price", 0)),
                    predicted_return=float(body.get("predicted_return", 0)),
                    venue=str(body.get("venue", "simulated")),
                    mode=str(body.get("mode", "simulation")),
                    regime=str(body.get("regime", "unknown")),
                    equity=float(body.get("equity", 0)),
                    stop_loss_hit=bool(body.get("stop_loss_hit", False)),
                )
                self._send_json(state.reflect(outcome))
            elif self.path == "/api/deliberate":
                question = str(body.get("question", "")).strip()
                if not question:
                    raise ValueError("question is required")
                self._send_json(state.deliberate(question))
            elif self.path == "/api/start-experiment":
                name = str(body.get("name", "")).strip()
                if not name:
                    raise ValueError("name is required")
                tags = body.get("tags") or None
                params = body.get("params") or None
                self._send_json(
                    {"experiment": state.system.start_experiment(name, tags=tags, params=params)["experiment"]}
                )
            elif self.path == "/api/promote-strategy":
                name = str(body.get("name", "")).strip()
                target = str(body.get("target", "")).strip()
                if not name or not target:
                    raise ValueError("name and target are required")
                self._send_json(state.system.promote_strategy(name, target))
            elif self.path == "/api/register-strategy":
                name = str(body.get("name", "")).strip()
                rules = body.get("rules") or {}
                if not name or not rules:
                    raise ValueError("name and rules are required")
                self._send_json(
                    state.system.register_strategy(
                        name,
                        rules=rules,
                        universe=body.get("universe") or (),
                        risk_params=body.get("risk_params") or None,
                        cost_model=str(body.get("cost_model", "v1")),
                        regimes=body.get("regimes") or (),
                        lineage=body.get("lineage") or (),
                        backtest_ref=str(body.get("backtest_ref", "")),
                        walk_forward_ref=str(body.get("walk_forward_ref", "")),
                    )
                )
            elif self.path == "/api/select-model":
                self._send_json(
                    state.system.select_local_model(
                        str(body.get("complexity", "standard")),
                        context_tokens=int(body.get("context_tokens", 0) or 0),
                        latency_budget_s=body.get("latency_budget_s"),
                    )
                )
            else:
                self._send_error_json(404, f"unknown path {self.path}")
        except ValueError as exc:
            self._send_error_json(400, str(exc))
        except BrokerAdapterError as exc:
            self._send_error_json(409, str(exc))
        except Exception as exc:  # noqa: BLE001 - the API never crashes the server
            self._send_error_json(500, str(exc))


def create_server(
    state: DashboardState | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> ThreadingHTTPServer:
    """Build (not start) the dashboard HTTP server."""
    handler = type("_BoundHandler", (_DashboardHandler,), {"state": state or DashboardState()})
    return ThreadingHTTPServer((host, port), handler)


def serve(
    state: DashboardState | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> None:
    """Run the dashboard in the foreground (Ctrl+C to stop)."""
    httpd = create_server(state, host=host, port=port)
    print(f"[orion] mission control on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[orion] mission control stopped")
    finally:
        httpd.server_close()