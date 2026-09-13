from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/")
async def get_portfolio(request: Request):
    # Just returns the risk aladdin for now as it contains portfolio PNL
    return request.app.state.orion.api_risk_aladdin()
