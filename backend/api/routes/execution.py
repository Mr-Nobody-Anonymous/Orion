from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

class TradeIntent(BaseModel):
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: float | None = None
    venue: str | None = None
    dry_run: bool = True

@router.post("/trade")
async def place_trade(intent: TradeIntent, request: Request):
    return request.app.state.orion.place_trade(
        intent.symbol,
        side=intent.side,
        quantity=intent.quantity,
        order_type=intent.order_type,
        price=intent.price,
        venue=intent.venue,
        dry_run=intent.dry_run,
    )
