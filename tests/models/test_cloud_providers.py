"""Tests for the four cloud LLM providers in :mod:`orion.models.cloud`.

The tests cover:

* The credential guard (no request without an API key).
* The request shape for each provider.
* The response parser (no exception leak from vendor SDKs).
* The credential redaction in status output.
* A round-trip via a stub HTTP server (offline).

No real network calls are made.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from typing import Any

import pytest

from orion.models.cloud import (
    AnthropicProvider,
    AzureOpenAIProvider,
    CloudProviderError,
    CohereProvider,
    HttpProvider,
    MistralProvider,
    OpenAIProvider,
)
from orion.models.cloud.base import _redact


# --------------------------------------------------------------------------- redact


def test_redact_short_string_returns_marker() -> None:
    assert _redact("") == ""
    assert _redact(None) == ""
    assert _redact("ab") == "<redacted>"


def test_redact_masks_middle() -> None:
    redacted = _redact("sk-1234567890abcdef")
    assert redacted.startswith("sk")
    assert redacted.endswith("ef")
    assert "*" in redacted
    assert "1234567890abcd" not in redacted


# --------------------------------------------------------------------------- openai


def test_openai_status_reflects_credential_state() -> None:
    p = OpenAIProvider(api_key="sk-test-1234567890", model="gpt-4o-mini")
    status = p.status()
    assert status.available is True
    assert "sk-****90" in status.detail or "*" in status.detail


def test_openai_refuses_without_key() -> None:
    p = OpenAIProvider(api_key=None)  # No env var set in test runner
    with pytest.raises(CloudProviderError, match="api_key is not configured"):
        p.generate("hello")


def test_openai_generate_success_via_local_stub() -> None:
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body_raw = self.rfile.read(length) if length else b""
            captured["body"] = json.loads(body_raw.decode("utf-8"))
            captured["auth"] = self.headers.get("Authorization")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "choices": [
                            {"message": {"role": "assistant", "content": "stub-reply"}}
                        ]
                    }
                ).encode("utf-8")
            )

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        endpoint = f"http://{host}:{port}/v1"
        p = OpenAIProvider(api_key="sk-stub", endpoint=endpoint, timeout_seconds=5.0)
        reply = p.generate("hello", system="you are concise")
    assert reply == "stub-reply"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["messages"][1]["content"] == "hello"
    assert captured["auth"] == "Bearer sk-stub"


def test_openai_handles_malformed_response() -> None:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"choices": []}')

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        p = OpenAIProvider(api_key="sk-stub", endpoint=f"http://{host}:{port}/v1")
        with pytest.raises(CloudProviderError, match="malformed response"):
            p.generate("hello")


# --------------------------------------------------------------------------- anthropic


def test_anthropic_generate_success_via_local_stub() -> None:
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body_raw = self.rfile.read(length) if length else b""
            captured["body"] = json.loads(body_raw.decode("utf-8"))
            captured["x_api_key"] = self.headers.get("x-api-key")
            captured["anthropic_version"] = self.headers.get("anthropic-version")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"content": [{"type": "text", "text": "anthropic-reply"}]}
                ).encode("utf-8")
            )

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        endpoint = f"http://{host}:{port}/v1"
        p = AnthropicProvider(api_key="ak-test", endpoint=endpoint, timeout_seconds=5.0)
        reply = p.generate("explain ORION")
    assert reply == "anthropic-reply"
    assert captured["x_api_key"] == "ak-test"
    assert captured["anthropic_version"] == "2023-06-01"
    assert captured["body"]["messages"][0]["content"] == "explain ORION"


def test_anthropic_handles_no_text_content() -> None:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"content": [{"type": "tool_use"}]}).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        p = AnthropicProvider(api_key="ak", endpoint=f"http://{host}:{port}/v1")
        with pytest.raises(CloudProviderError, match="no text content"):
            p.generate("hello")


# --------------------------------------------------------------------------- azure


def test_azure_requires_resource_and_deployment() -> None:
    with pytest.raises(CloudProviderError, match="resource and deployment"):
        AzureOpenAIProvider(api_key="ak")


def test_azure_generate_success_via_local_stub() -> None:
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            captured["path"] = self.path
            captured["api_key"] = self.headers.get("api-key")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"choices": [{"message": {"role": "assistant", "content": "azure-reply"}}]}
                ).encode("utf-8")
            )

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        endpoint = f"http://{host}:{port}/openai/deployments/gpt-test"
        p = AzureOpenAIProvider(
            api_key="az",
            resource=None,
            deployment=None,
            endpoint=endpoint,
            api_version="2024-06-01",
            timeout_seconds=5.0,
        )
        reply = p.generate("hi")
    assert reply == "azure-reply"
    assert captured["api_key"] == "az"
    assert captured["path"].endswith("/chat/completions?api-version=2024-06-01")


# --------------------------------------------------------------------------- cohere (P4-4)


def test_cohere_refuses_without_key() -> None:
    p = CohereProvider(api_key=None)
    with pytest.raises(CloudProviderError, match="api_key is not configured"):
        p.generate("hello")


def test_cohere_status_reflects_credential_state() -> None:
    p = CohereProvider(api_key="co-test-1234567890abcdef")
    status = p.status()
    assert status.available is True
    assert status.name == "cohere"


def test_cohere_generate_success_via_local_stub() -> None:
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body_raw = self.rfile.read(length) if length else b""
            captured["body"] = json.loads(body_raw.decode("utf-8"))
            captured["auth"] = self.headers.get("Authorization")
            captured["path"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"text": "cohere-reply"}).encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        endpoint = f"http://{host}:{port}/v1"
        p = CohereProvider(api_key="co-stub", endpoint=endpoint, timeout_seconds=5.0)
        reply = p.generate("hello", system="be terse")
    assert reply == "cohere-reply"
    assert captured["auth"] == "Bearer co-stub"
    assert captured["path"].endswith("/chat")
    assert any(msg.get("role") == "user" for msg in captured["body"].get("chat_history", []))
    assert captured["body"]["preamble"] == "be terse"


def test_cohere_handles_malformed_response() -> None:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"unexpected": "shape"}')

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        p = CohereProvider(api_key="co-stub", endpoint=f"http://{host}:{port}/v1", timeout_seconds=5.0)
        with pytest.raises(CloudProviderError, match="malformed response"):
            p.generate("hi")


# --------------------------------------------------------------------------- mistral (P4-4)


def test_mistral_refuses_without_key() -> None:
    p = MistralProvider(api_key=None)
    with pytest.raises(CloudProviderError, match="api_key is not configured"):
        p.generate("hello")


def test_mistral_status_reflects_credential_state() -> None:
    p = MistralProvider(api_key="m-test-1234567890abcdef")
    status = p.status()
    assert status.available is True
    assert status.name == "mistral"


def test_mistral_generate_success_via_local_stub() -> None:
    captured: dict[str, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body_raw = self.rfile.read(length) if length else b""
            captured["body"] = json.loads(body_raw.decode("utf-8"))
            captured["auth"] = self.headers.get("Authorization")
            captured["path"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"choices": [{"message": {"role": "assistant", "content": "mistral-reply"}}]}
                ).encode("utf-8")
            )

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        endpoint = f"http://{host}:{port}/v1"
        p = MistralProvider(api_key="m-stub", endpoint=endpoint, timeout_seconds=5.0)
        reply = p.generate("hello", system="be terse")
    assert reply == "mistral-reply"
    assert captured["auth"] == "Bearer m-stub"
    assert captured["path"].endswith("/chat/completions")
    messages = captured["body"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "hello"


def test_mistral_handles_malformed_response() -> None:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"choices": []}')

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        p = MistralProvider(api_key="m-stub", endpoint=f"http://{host}:{port}/v1", timeout_seconds=5.0)
        with pytest.raises(CloudProviderError, match="malformed response"):
            p.generate("hi")


# --------------------------------------------------------------------------- http (generic)


def test_http_uses_custom_extractor() -> None:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"text": "from-custom"}')

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    def extractor(resp: dict[str, Any]) -> str:
        return str(resp.get("text", ""))

    with _start_server(_Handler) as (host, port):
        p = HttpProvider(
            endpoint=f"http://{host}:{port}/v1",
            api_key="tok",
            extractor=extractor,
            path="/generate",
            timeout_seconds=5.0,
        )
        reply = p.generate("hello")
    assert reply == "from-custom"


def test_http_openai_default_shape() -> None:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"choices": [{"message": {"content": "openai-shape"}}]}
                ).encode("utf-8")
            )

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    with _start_server(_Handler) as (host, port):
        p = HttpProvider(endpoint=f"http://{host}:{port}/v1", api_key="tok", timeout_seconds=5.0)
        reply = p.generate("hi")
    assert reply == "openai-shape"


def test_http_refuses_without_key() -> None:
    p = HttpProvider(endpoint="http://127.0.0.1:1/v1", api_key=None)
    with pytest.raises(CloudProviderError, match="api_key is not configured"):
        p.generate("hi")


# --------------------------------------------------------------------------- helpers


def _start_server(handler_cls: type) -> Any:
    """Start a local HTTP server on a free port; return (host, port)."""
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
