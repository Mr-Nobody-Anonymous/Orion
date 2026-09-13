from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/")
async def get_risk(request: Request):
    return request.app.state.orion.api_risk_aladdin()
