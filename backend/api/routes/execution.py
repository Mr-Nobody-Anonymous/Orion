from __future__ import annotations

import hmac
import os
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

API_KEY_NAME = "X-ORION-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _principal(api_key: str | None) -> str | None:
    """Return the role represented by a configured key (never accept a missing key)."""
    if not api_key:
        return None
    candidates = (
        ("admin", os.getenv("ORION_ADMIN_API_KEY")),
        ("operator", os.getenv("ORION_API_KEY", "dev-local-orion-key")),
    )
    for role, configured in candidates:
        if configured and hmac.compare_digest(api_key, configured):
            return role
    return None


def verify_api_key(
    api_key: str | None = Security(api_key_header),
    request: Request = None,
) -> str:
    """Validate API key from request headers."""
    if not api_key and request:
        api_key = request.headers.get("X-ORION-API-KEY") or request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    role = _principal(api_key)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "UNAUTHORIZED",
                "message": "Invalid or missing X-ORION-API-KEY header",
            },
        )
    return api_key


class TradeIntent(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, description="Asset ticker symbol")
    side: Literal["BUY", "SELL"]
    quantity: float = Field(..., gt=0, description="Order quantity, must be positive")
    order_type: Literal["MARKET", "LIMIT", "STOP", "STOP_LIMIT"] = "MARKET"
    price: float | None = Field(default=None, gt=0, description="Required for LIMIT/STOP_LIMIT orders")
    venue: str | None = Field(default=None, max_length=50, description="Target execution venue")
    dry_run: bool = Field(default=True, description="Simulation / dry-run flag")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Symbol cannot be empty")
        return cleaned

    @field_validator("price")
    @classmethod
    def validate_price_for_limit_orders(cls, v: float | None, info) -> float | None:
        order_type = info.data.get("order_type")
        if order_type in ("LIMIT", "STOP_LIMIT") and v is None:
            raise ValueError(f"Price must be specified for {order_type} orders")
        return v


@router.post("/trade")
async def place_trade(
    intent: TradeIntent,
    request: Request,
    _auth: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Secure order submission endpoint with server-side safety gating."""
    live_enabled = os.getenv("ORION_LIVE_TRADING_ENABLED", "false").lower() in ("true", "1", "yes")

    # Enforce server-side execution mode: never trust a client to switch to live mode without server enablement
    if not intent.dry_run and not live_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "LIVE_TRADING_DISABLED",
                "message": "Live trading is disabled by system policy. Orders must have dry_run=True.",
            },
        )

    orion = getattr(request.app.state, "orion", None)
    if orion is None:
        from orion.dashboard.web import DashboardState
        orion = DashboardState()
        prices = [100.0 + i * 0.25 for i in range(40)]
        orion.run_cycle("NVDA", prices)
        orion.run_cycle("AAPL", [220.0 + i * 0.2 for i in range(40)])
        request.app.state.orion = orion

    try:
        result = orion.place_trade(
            intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            order_type=intent.order_type,
            price=intent.price,
            venue=intent.venue,
            dry_run=intent.dry_run,
        )
        return {"status": "SUCCESS", "order": result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "ORDER_EXECUTION_FAILED",
                "message": str(exc),
            },
        ) from exc
