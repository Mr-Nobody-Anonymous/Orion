import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..routes.execution import _enabled, _principal

router = APIRouter()

@router.websocket("/market")
async def websocket_market_endpoint(websocket: WebSocket):
    if not _enabled("ORION_MARKET_STREAM_ENABLED"):
        await websocket.close(code=1008, reason="market stream is disabled")
        return
    if _principal(websocket.headers.get("x-api-key")) is None:
        await websocket.close(code=1008, reason="valid API key required")
        return
    await websocket.accept()
    state = websocket.app.state.orion
    try:
        while True:
            # Polling state from Orion Core every 2 seconds
            market_data = state.api_status()
            
            payload = {
                "event": "market.update",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": market_data
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
