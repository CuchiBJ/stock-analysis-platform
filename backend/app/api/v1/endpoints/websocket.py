"""WebSocket endpoint for real-time updates"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import websocket_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier")
):
    """WebSocket endpoint for real-time setup state updates"""
    await websocket_manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle subscription/unsubscription requests
            if data.get('action') == 'subscribe':
                channel = data.get('channel')
                if channel:
                    await websocket_manager.subscribe(client_id, channel)
            elif data.get('action') == 'unsubscribe':
                channel = data.get('channel')
                if channel:
                    await websocket_manager.unsubscribe(client_id, channel)
                    
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(client_id)
