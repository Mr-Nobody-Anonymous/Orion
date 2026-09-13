from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/status")
async def get_status(request: Request):
    return request.app.state.orion.api_status()

@router.get("/brokers")
async def get_brokers(request: Request):
    return request.app.state.orion.api_brokers()
