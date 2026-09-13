from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/status")
async def get_status(request: Request):
    return request.app.state.orion.api_status()

@router.get("/brokers")
async def get_brokers(request: Request):
    return request.app.state.orion.api_brokers()

@router.get("/macro")
async def get_macro(request: Request):
    return request.app.state.orion.api_macro_economy()

@router.get("/search")
async def search(request: Request, q: str = ""):
    return request.app.state.orion.api_omni_search(q)
