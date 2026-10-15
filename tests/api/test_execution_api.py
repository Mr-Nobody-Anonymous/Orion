from __future__ import annotations

import os
import pytest

# Skip gracefully if FastAPI is not installed in the current environment
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.routes.execution import TradeIntent, verify_api_key


def test_trade_intent_valid() -> None:
    intent = TradeIntent(
        symbol="nvda",
        side="BUY",
        quantity=10.0,
        order_type="MARKET",
        dry_run=True,
    )
    assert intent.symbol == "NVDA"
    assert intent.side == "BUY"
    assert intent.quantity == 10.0
    assert intent.order_type == "MARKET"
    assert intent.dry_run is True


def test_trade_intent_limit_order_requires_price() -> None:
    with pytest.raises(ValueError, match="Price must be specified"):
        TradeIntent(
            symbol="AAPL",
            side="SELL",
            quantity=5.0,
            order_type="LIMIT",
            price=None,
        )


def test_trade_intent_invalid_side() -> None:
    with pytest.raises(ValueError):
        TradeIntent(
            symbol="AAPL",
            side="HOLD",  # Invalid side
            quantity=5.0,
        )


def test_trade_intent_negative_quantity() -> None:
    with pytest.raises(ValueError):
        TradeIntent(
            symbol="AAPL",
            side="BUY",
            quantity=-10.0,
        )


def test_verify_api_key() -> None:
    os.environ["ORION_API_KEY"] = "test-secret-key"
    try:
        # Valid key
        assert verify_api_key("test-secret-key") == "test-secret-key"

        # Invalid key raises HTTPException with 401
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("wrong-key")
        assert exc_info.value.status_code == 401

        # Missing key raises HTTPException with 401
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None)
        assert exc_info.value.status_code == 401
    finally:
        os.environ.pop("ORION_API_KEY", None)


def test_endpoint_unauthorized_without_key() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/execution/trade", json={
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10.0,
        })
        assert resp.status_code == 401


def test_endpoint_live_mode_refusal_when_disabled() -> None:
    os.environ["ORION_API_KEY"] = "test-key"
    os.environ["ORION_LIVE_TRADING_ENABLED"] = "false"
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/execution/trade",
                headers={"X-ORION-API-KEY": "test-key"},
                json={
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": 10.0,
                    "dry_run": False,
                },
            )
            assert resp.status_code == 403
            assert resp.json()["detail"]["error_code"] == "LIVE_TRADING_DISABLED"
    finally:
        os.environ.pop("ORION_API_KEY", None)
        os.environ.pop("ORION_LIVE_TRADING_ENABLED", None)


def test_endpoint_dry_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["ORION_API_KEY"] = "test-key"
    try:
        with TestClient(app) as client:
            monkeypatch.setattr(
                client.app.state.orion,
                "place_trade",
                lambda *args, **kwargs: {"status": "DRY_RUN", "venue": "simulation", "order": {"status": "DRY_RUN"}},
            )
            resp = client.post(
                "/api/v1/execution/trade",
                headers={"X-ORION-API-KEY": "test-key"},
                json={
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": 10.0,
                    "dry_run": True,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "SUCCESS"
            assert data["order"]["status"] == "DRY_RUN"
    finally:
        os.environ.pop("ORION_API_KEY", None)

