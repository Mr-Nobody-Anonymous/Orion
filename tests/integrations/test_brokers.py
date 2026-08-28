"""Tests for :mod:`orion.integrations.brokers`.

These tests confirm that:

* :class:`AlpacaAdapter` refuses to construct in live mode without
  ``live_trading_enabled``.
* :class:`AlpacaAdapter` health reflects credential presence.
* :class:`AlpacaAdapter.submit` returns a structured response from a
  local stub server.
* :class:`LiveBrokerAlerts` is a thread-safe bounded ring buffer.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from typing import Any

import pytest

from orion.infrastructure.configuration import AIMode, OrionConfig
from orion.integrations.brokers import (
    AlpacaAdapter,
    BaseBrokerAdapter,
    BrokerAdapterError,
    LiveBrokerAlert,
    LiveBrokerAlerts,
    LiveBrokerAlertKind,
    LiveTradingDisabledError,
)


# --------------------------------------------------------------------------- guards


def test_alpaca_paper_with_live_disabled_is_ok() -> None:
    cfg = OrionConfig(mode=AIMode.LOCAL, execution_mode="paper")
    adapter = AlpacaAdapter(cfg, api_key="ak", api_secret="sk", endpoint="http://x")
    assert adapter.config.execution_mode == "paper"


def test_alpaca_live_with_live_disabled_raises() -> None:
    cfg = OrionConfig(mode=AIMode.LOCAL, execution_mode="live", live_trading_enabled=False)
    with pytest.raises(LiveTradingDisabledError):
        AlpacaAdapter(cfg, api_key="ak", api_secret="sk")


def test_alpaca_paper_endpoint_default() -> None:
    cfg = OrionConfig(execution_mode="paper")
    adapter = AlpacaAdapter(cfg, api_key="ak", api_secret="sk")
    assert adapter.endpoint == AlpacaAdapter.PAPER_BASE


def test_alpaca_live_endpoint_default_requires_explicit_enable() -> None:
    cfg = OrionConfig(execution_mode="live", live_trading_enabled=True)
    adapter = AlpacaAdapter(cfg, api_key="ak", api_secret="sk")
    assert adapter.endpoint == AlpacaAdapter.LIVE_BASE


def test_alpaca_health_reports_credentials() -> None:
    cfg = OrionConfig(execution_mode="paper")
    adapter = AlpacaAdapter(cfg, api_key="ak", api_secret="sk", endpoint="http://x")
    h = adapter.health()
    assert h.available is True
    assert h.mode == "paper"

    adapter2 = AlpacaAdapter(cfg, api_key=None, api_secret=None, endpoint="http://x")
    h2 = adapter2.health()
    assert h2.available is False
    assert "credentials" in h2.detail


def test_alpaca_submit_without_credentials_raises() -> None:
    cfg = OrionConfig(execution_mode="paper")
    adapter = AlpacaAdapter(cfg, api_key=None, api_secret=None, endpoint="http://x")
    with pytest.raises(BrokerAdapterError, match="api_key and api_secret"):
        adapter.submit({"symbol": "AAPL", "qty": 1, "side": "buy", "type": "market", "time_in_force": "day"})


def test_alpaca_submit_round_trip() -> None:
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            captured["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            captured["auth_id"] = self.headers.get("APCA-API-KEY-ID")
            captured["auth_secret"] = self.headers.get("APCA-API-SECRET-KEY")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"id": "order-1", "status": "accepted"}).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        cfg = OrionConfig(execution_mode="paper")
        adapter = AlpacaAdapter(cfg, api_key="ak-1", api_secret="sk-1", endpoint=f"http://{host}:{port}", timeout_seconds=5.0)
        resp = adapter.submit(
            {"symbol": "AAPL", "qty": 1, "side": "buy", "type": "market", "time_in_force": "day"}
        )
    assert resp["id"] == "order-1"
    assert captured["auth_id"] == "ak-1"
    assert captured["auth_secret"] == "sk-1"
    assert captured["body"]["symbol"] == "AAPL"


# --------------------------------------------------------------------------- alerts


def test_alerts_buffer_is_bounded() -> None:
    alerts = LiveBrokerAlerts(capacity=3)
    for i in range(5):
        alerts.push(LiveBrokerAlert(LiveBrokerAlertKind.ORDER_FILLED, "alpaca", f"order-{i}"))
    items = alerts.recent()
    assert len(items) == 3
    assert items[0].message == "order-2"
    assert items[-1].message == "order-4"


def test_alerts_clear_and_len() -> None:
    alerts = LiveBrokerAlerts(capacity=10)
    alerts.push(LiveBrokerAlert(LiveBrokerAlertKind.CONNECTIVITY, "alpaca", "ok"))
    assert len(alerts) == 1
    alerts.clear()
    assert len(alerts) == 0


def test_alerts_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        LiveBrokerAlerts(capacity=0)


def test_alerts_thread_safety_smoke() -> None:
    alerts = LiveBrokerAlerts(capacity=1000)
    def push_many() -> None:
        for i in range(100):
            alerts.push(LiveBrokerAlert(LiveBrokerAlertKind.ORDER_FILLED, "x", f"m{i}"))
    threads = [threading.Thread(target=push_many) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(alerts) == 800


# --------------------------------------------------------------------------- helpers


def _start_server(handler_cls: type) -> Any:
    class _Reusable(socketserver.TCPServer):
        allow_reuse_address = True
    httpd = _Reusable(("127.0.0.1", 0), handler_cls)
    host, port = httpd.server_address
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    class _Ctx:
        def __enter__(self_inner) -> tuple[str, int]:
            return host, port

        def __exit__(self_inner, *exc: Any) -> None:
            httpd.shutdown()
            httpd.server_close()

    return _Ctx()
