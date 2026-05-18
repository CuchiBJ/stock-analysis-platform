"""WebSocket Manager for real-time setup state updates"""

import json
import logging
from typing import Set, Dict
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Active connections: {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Subscriptions: {connection_id: Set[channels]}
        self.subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.subscriptions[connection_id] = set()
        logger.info(f"WebSocket connected: {connection_id}")
    
    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.subscriptions:
            del self.subscriptions[connection_id]
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def subscribe(self, connection_id: str, channel: str):
        """Subscribe a connection to a channel"""
        if connection_id in self.subscriptions:
            self.subscriptions[connection_id].add(channel)
            logger.info(f"Connection {connection_id} subscribed to {channel}")
    
    async def unsubscribe(self, connection_id: str, channel: str):
        """Unsubscribe a connection from a channel"""
        if connection_id in self.subscriptions:
            self.subscriptions[connection_id].discard(channel)
            logger.info(f"Connection {connection_id} unsubscribed from {channel}")
    
    async def broadcast(self, channel: str, message: dict):
        """Broadcast a message to all connections subscribed to a channel"""
        message_json = json.dumps(message)
        disconnected = []
        
        for connection_id, websocket in self.active_connections.items():
            # Check if connection is subscribed to this channel
            if connection_id in self.subscriptions and channel in self.subscriptions[connection_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to {connection_id}: {e}")
                    disconnected.append(connection_id)
        
        # Clean up disconnected clients
        for connection_id in disconnected:
            self.disconnect(connection_id)
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """Send a message to a specific connection"""
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending personal message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
