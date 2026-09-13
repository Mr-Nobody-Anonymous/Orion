import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/market")
async def websocket_market_endpoint(websocket: WebSocket):
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
