"""WebSocket endpoint for real-time updates"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.core.auth import get_current_websocket_user
from app.models.user import User
from app.services.websocket_manager import websocket_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user: Annotated[User, Depends(get_current_websocket_user)],
    client_id: str = Query(..., description="Unique client identifier"),
):
    """WebSocket endpoint for real-time setup state updates"""
    # A browser-supplied identifier is only unique inside the authenticated
    # account. Prefixing it prevents one account from replacing or controlling
    # another account's manager entry by guessing the same value.
    connection_id = f"{user.id}:{client_id}"
    await websocket_manager.connect(websocket, connection_id)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle subscription/unsubscription requests
            if data.get('action') == 'subscribe':
                channel = data.get('channel')
                if channel:
                    await websocket_manager.subscribe(connection_id, channel)
            elif data.get('action') == 'unsubscribe':
                channel = data.get('channel')
                if channel:
                    await websocket_manager.unsubscribe(connection_id, channel)
                    
    except WebSocketDisconnect:
        websocket_manager.disconnect(connection_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(connection_id)
