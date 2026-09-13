from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

class DeliberationRequest(BaseModel):
    query: str
    symbol: str = "NVDA"

@router.get("/peers")
async def get_peers(request: Request):
    return request.app.state.orion.api_peers()

@router.post("/deliberate")
async def post_deliberate(payload: DeliberationRequest, request: Request):
    # In a real implementation this would stream. For now we use the sync deliberate
    # Note: the web.py deliberate signature is: deliberate(self, question: str) -> dict[str, Any]
    return request.app.state.orion.deliberate(payload.query)
