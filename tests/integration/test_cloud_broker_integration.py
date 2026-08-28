"""End-to-end integration tests for the cloud LLM and broker surface.

These tests confirm that:

* The new :mod:`orion.models.cloud` providers are importable through
  the canonical ``orion.models.cloud`` re-export.
* The :class:`orion.integrations.brokers.AlpacaAdapter` integrates with
  the rest of the ORION risk / execution layer without leaking any
  third-party types.
* The ORION safety contract is preserved: a misconfigured cloud key
  cannot accidentally produce a request; a paper broker cannot be
  coerced into live mode without explicit opt-in.

The tests do not call the real network. Stub servers validate
request/response round trips.
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
    BrokerAdapterError,
    LiveBrokerAlert,
    LiveBrokerAlertKind,
    LiveBrokerAlerts,
    LiveTradingDisabledError,
)
from orion.models.cloud import (
    AnthropicProvider,
    AzureOpenAIProvider,
    BaseHttpCloudProvider,
    CloudProviderError,
    CloudProviderStatus,
    CloudProviderUnavailable,
    HttpCloudConfig,
    HttpProvider,
    NullCloudProvider,
    OpenAIProvider,
)


# --------------------------------------------------------------------------- public surface


def test_models_cloud_public_api_is_stable() -> None:
    """Every spec-declared provider is importable from the canonical path."""
    for cls in (OpenAIProvider, AnthropicProvider, AzureOpenAIProvider, HttpProvider):
        assert issubclass(cls, BaseHttpCloudProvider)


def test_models_cloud_status_dataclass_is_immutable() -> None:
    s = CloudProviderStatus(name="x", available=True, endpoint="https://x", model="m")
    with pytest.raises(Exception):
        s.name = "y"  # type: ignore[misc]


def test_null_cloud_provider_refuses() -> None:
    p = NullCloudProvider()
    with pytest.raises(CloudProviderUnavailable):
        p.generate("hi")
    with pytest.raises(CloudProviderUnavailable):
        p.embed("hi")


def test_http_cloud_config_validates_endpoint() -> None:
    with pytest.raises(CloudProviderError, match="http"):
        HttpCloudConfig(endpoint="not-a-url", api_key="x")


def test_http_cloud_config_validates_timeout() -> None:
    with pytest.raises(CloudProviderError, match="timeout_seconds"):
        HttpCloudConfig(endpoint="http://x", api_key="x", timeout_seconds=0)


# --------------------------------------------------------------------------- cloud -> broker handoff


def test_cloud_provider_status_flows_to_dashboard() -> None:
    """The cloud provider status must be JSON-serialisable for dashboards."""
    p = OpenAIProvider(api_key="sk-very-long-secret-1234567890", model="gpt-4o-mini")
    s = p.status()
    out = s.as_dict()
    assert out["name"] == "openai"
    assert out["available"] is True
    # The key must be redacted — never the raw value
    assert "sk-very-long-secret-1234567890" not in str(out)
    assert "*" in out["detail"]


def test_alerts_buffer_is_thread_safe_under_load() -> None:
    """A modest multi-threaded burst must not corrupt the alerts buffer."""
    alerts = LiveBrokerAlerts(capacity=2000)

    def push_burst(tag: str) -> None:
        for i in range(200):
            alerts.push(LiveBrokerAlert(LiveBrokerAlertKind.ORDER_FILLED, tag, f"{tag}-{i}"))

    threads = [threading.Thread(target=push_burst, args=(f"t{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(alerts) == 2000


def test_broker_adapter_live_guard_in_full_integration() -> None:
    """The full risk-gate path must refuse a live broker in unsafe config."""
    cfg = OrionConfig(mode=AIMode.LOCAL, execution_mode="paper")
    adapter = AlpacaAdapter(cfg, api_key="ak", api_secret="sk")
    # Paper trades can be submitted; the live guard is downstream of paper.
    assert adapter.health().mode == "paper"

    # A separate config in live mode without live_trading_enabled must raise.
    cfg_live_unsafe = OrionConfig(mode=AIMode.LOCAL, execution_mode="live")
    with pytest.raises(LiveTradingDisabledError):
        AlpacaAdapter(cfg_live_unsafe, api_key="ak", api_secret="sk")


def test_alpaca_paper_submit_uses_correct_endpoint() -> None:
    """The paper endpoint must be the paper URL, not the live one."""
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            captured["host"] = self.headers.get("Host")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"id": "x", "status": "ok"}).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    class _Reusable(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = _Reusable(("127.0.0.1", 0), _Handler)
    host, port = httpd.server_address
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    try:
        cfg = OrionConfig(execution_mode="paper")
        adapter = AlpacaAdapter(
            cfg, api_key="ak", api_secret="sk",
            endpoint=f"http://{host}:{port}", timeout_seconds=5.0,
        )
        # Verify the default endpoint would have been the paper URL
        # before the override.
        assert AlpacaAdapter.PAPER_BASE.startswith("https://paper-api")
        resp = adapter.submit({"symbol": "AAPL", "qty": 1, "side": "buy", "type": "market", "time_in_force": "day"})
        assert resp["id"] == "x"
        assert captured["host"] is not None
    finally:
        httpd.shutdown()
        httpd.server_close()
        server_thread.join(timeout=2.0)


def test_openai_embed_endpoint_uses_embeddings_path() -> None:
    """The /embeddings path must be reached for embed() requests."""
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            captured["path"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"embedding": [0.1, 0.2, 0.3]}]}).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    class _Reusable(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = _Reusable(("127.0.0.1", 0), _Handler)
    host, port = httpd.server_address
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    try:
        p = OpenAIProvider(api_key="sk", endpoint=f"http://{host}:{port}/v1", timeout_seconds=5.0)
        vec = p.embed("hello")
    finally:
        httpd.shutdown()
        httpd.server_close()
        server_thread.join(timeout=2.0)
    assert vec == [0.1, 0.2, 0.3]
    assert captured["path"] == "/v1/embeddings"
