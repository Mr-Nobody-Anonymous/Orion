import hashlib
import hmac
import os
import threading
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, model_validator

from orion.integrations.brokers.base import BrokerAdapterError, LiveTradingDisabledError

router = APIRouter()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class TradeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    symbol: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_./-]+$")]
    side: Literal["BUY", "SELL"]
    quantity: Annotated[StrictInt | StrictFloat, Field(gt=0, le=1_000_000)]
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: Annotated[StrictFloat | StrictInt | None, Field(gt=0)] = None
    venue: Annotated[str | None, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")] = None
    dry_run: StrictBool = True

    @model_validator(mode="after")
    def validate_order(self) -> "TradeIntent":
        if self.order_type == "LIMIT" and self.price is None:
            raise ValueError("price is required for LIMIT orders")
        if self.order_type == "MARKET" and self.price is not None:
            raise ValueError("price is not allowed for MARKET orders")
        return self


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _server_dry_run() -> bool:
    mode = os.getenv("ORION_EXECUTION_MODE", "paper").strip().lower()
    if mode not in {"paper", "live"}:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="invalid execution mode")
    return mode == "paper"


def _principal(api_key: str | None) -> str | None:
    """Return the role represented by a configured key (never accept a missing key)."""
    if not api_key:
        return None
    candidates = (("admin", os.getenv("ORION_ADMIN_API_KEY")), ("operator", os.getenv("ORION_API_KEY")))
    for role, configured in candidates:
        if configured and hmac.compare_digest(api_key, configured):
            return role
    return None


async def require_operator(api_key: str | None = Security(api_key_header)) -> str:
    role = _principal(api_key)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="valid API key required")
    return role


def _idempotency_store(request: Request) -> dict[str, tuple[str, dict]]:
    state = request.app.state
    if not hasattr(state, "execution_idempotency"):
        state.execution_idempotency = {}
        state.execution_idempotency_lock = threading.Lock()
    return state.execution_idempotency


def _error_status(exc: Exception) -> int:
    if isinstance(exc, LiveTradingDisabledError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(exc, BrokerAdapterError):
        message = str(exc).lower()
        return status.HTTP_409_CONFLICT if "kill switch" in message else status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_502_BAD_GATEWAY

@router.post("/trade")
async def place_trade(
    intent: TradeIntent,
    request: Request,
    role: str = Security(require_operator),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if not _enabled("ORION_EXECUTION_ENABLED"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="execution API is disabled")
    server_dry_run = _server_dry_run()
    if intent.dry_run != server_dry_run:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="requested execution mode does not match server mode",
        )
    if not server_dry_run:
        if role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required for live orders")
        if not _enabled("ORION_LIVE_TRADING_ENABLED") or not _enabled("ORION_ALLOW_LIVE_TRADING"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="live trading is disabled")

    key = idempotency_key.strip() if idempotency_key else None
    if key and (len(key) < 8 or len(key) > 128):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid Idempotency-Key")
    fingerprint = hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
    store = _idempotency_store(request)
    lock = request.app.state.execution_idempotency_lock
    with lock:
        if key:
            prior = store.get(key)
            if prior:
                if prior[0] != fingerprint:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency-Key was already used")
                return prior[1]
        try:
            result = request.app.state.orion.place_trade(
                intent.symbol, side=intent.side, quantity=float(intent.quantity),
                order_type=intent.order_type, price=float(intent.price) if intent.price is not None else None,
                venue=intent.venue, dry_run=server_dry_run,
            )
        except (BrokerAdapterError, LiveTradingDisabledError) as exc:
            raise HTTPException(status_code=_error_status(exc), detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if key:
            store[key] = (fingerprint, result)
    return result
