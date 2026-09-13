from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/")
async def get_ai_council(request: Request, symbol: str = "NVDA", q: str = "Should Orion increase technology exposure?"):
    return request.app.state.orion.api_ai_council_deliberate(q, symbol)
