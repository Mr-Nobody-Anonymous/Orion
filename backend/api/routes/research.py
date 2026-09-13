from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/asset/{symbol}")
async def get_asset(request: Request, symbol: str):
    return request.app.state.orion.api_asset(symbol)

@router.get("/prediction")
async def get_prediction_markets(request: Request):
    return request.app.state.orion.api_prediction_markets()
