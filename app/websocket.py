#!/usr/bin/env python3
"""
WebSocket endpoints for real-time updates
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
import json
import asyncio
import os
import time
from collections import deque
from utils.logger import get_logger

# Lazy-load logger to avoid initialization issues
def get_websocket_logger():
    return get_logger('cmdarr.websocket')


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.command_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        get_websocket_logger().info(f"WebSocket connected: {client_id or 'unknown'}")
    
    def disconnect(self, websocket: WebSocket, client_id: str = None):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from command-specific connections
        for command_name, connections in self.command_connections.items():
            if websocket in connections:
                connections.remove(websocket)
        
        get_websocket_logger().info(f"WebSocket disconnected: {client_id or 'unknown'}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            get_websocket_logger().error(f"Failed to send personal message: {e}")
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                get_websocket_logger().error(f"Failed to broadcast message: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_command_update(self, command_name: str, data: Dict[str, Any]):
        """Broadcast command-specific updates"""
        message = json.dumps({
            "type": "command_update",
            "command_name": command_name,
            "data": data
        })
        
        # Send to all connections
        await self.broadcast(message)
        
        # Send to command-specific connections
        if command_name in self.command_connections:
            disconnected = []
            for connection in self.command_connections[command_name]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    get_websocket_logger().error(f"Failed to send command update: {e}")
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for connection in disconnected:
                self.command_connections[command_name].remove(connection)
    
    def subscribe_to_command(self, websocket: WebSocket, command_name: str):
        """Subscribe a connection to command-specific updates"""
        if command_name not in self.command_connections:
            self.command_connections[command_name] = []
        
        if websocket not in self.command_connections[command_name]:
            self.command_connections[command_name].append(websocket)
    
    
    


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str = None):
    """Main WebSocket endpoint"""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "subscribe_command":
                    command_name = message.get("command_name")
                    if command_name:
                        manager.subscribe_to_command(websocket, command_name)
                        get_websocket_logger().info(f"Client subscribed to {command_name} updates")
                
                
                elif message_type == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}), 
                        websocket
                    )
                
            except json.JSONDecodeError:
                get_websocket_logger().warning(f"Invalid JSON received: {data}")
            except Exception as e:
                get_websocket_logger().error(f"Error processing WebSocket message: {e}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
    except Exception as e:
        get_websocket_logger().error(f"WebSocket error: {e}")
        manager.disconnect(websocket, client_id)
