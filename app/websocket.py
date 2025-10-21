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

logger = get_logger('cmdarr.websocket')


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.command_connections: Dict[str, List[WebSocket]] = {}
        self.log_streaming_tasks: Dict[str, asyncio.Task] = {}
        self.log_file_position: Dict[str, int] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {client_id or 'unknown'}")
    
    def disconnect(self, websocket: WebSocket, client_id: str = None):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from command-specific connections
        for command_name, connections in self.command_connections.items():
            if websocket in connections:
                connections.remove(websocket)
        
        logger.info(f"WebSocket disconnected: {client_id or 'unknown'}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to broadcast message: {e}")
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
                    logger.error(f"Failed to send command update: {e}")
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
    
    async def start_log_streaming(self, command_name: str, execution_id: str):
        """Start streaming logs for a specific command execution"""
        if command_name in self.log_streaming_tasks:
            # Already streaming for this command
            return
        
        # Start the log streaming task
        task = asyncio.create_task(self._stream_command_logs(command_name, execution_id))
        self.log_streaming_tasks[command_name] = task
        logger.info(f"Started log streaming for command: {command_name}")
    
    async def stop_log_streaming(self, command_name: str):
        """Stop streaming logs for a specific command"""
        if command_name in self.log_streaming_tasks:
            task = self.log_streaming_tasks[command_name]
            task.cancel()
            del self.log_streaming_tasks[command_name]
            
            # Clean up file position tracking
            if command_name in self.log_file_position:
                del self.log_file_position[command_name]
            
            logger.info(f"Stopped log streaming for command: {command_name}")
    
    async def _stream_command_logs(self, command_name: str, execution_id: str):
        """Stream logs for a specific command execution"""
        log_file = "data/logs/cmdarr.log"
        
        if not os.path.exists(log_file):
            logger.warning(f"Log file not found: {log_file}")
            return
        
        # Initialize file position to current end of file (so we only capture new logs)
        if command_name not in self.log_file_position:
            self.log_file_position[command_name] = os.path.getsize(log_file)
        
        try:
            while True:
                await asyncio.sleep(0.5)  # Check for new logs every 500ms
                
                # Check if file has grown
                current_size = os.path.getsize(log_file)
                last_position = self.log_file_position[command_name]
                
                if current_size > last_position:
                    # Read new content
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        f.seek(last_position)
                        new_content = f.read()
                        self.log_file_position[command_name] = current_size
                    
                    # Filter logs for this command
                    filtered_logs = self._filter_command_logs(new_content, command_name, execution_id)
                    
                    if filtered_logs:
                        # Send logs to subscribed connections
                        await self._send_logs_to_subscribers(command_name, filtered_logs)
                
        except asyncio.CancelledError:
            logger.info(f"Log streaming cancelled for command: {command_name}")
        except Exception as e:
            logger.error(f"Error streaming logs for {command_name}: {e}")
    
    def _filter_command_logs(self, log_content: str, command_name: str, execution_id: str) -> List[str]:
        """Filter log content for command-specific entries by execution ID"""
        lines = log_content.strip().split('\n')
        filtered_lines = []
        
        # Create execution ID pattern for filtering
        execution_pattern = f"[EXEC:{execution_id}]"
        
        for line in lines:
            if line.strip():
                # Skip WebSocket debug messages to avoid infinite loops
                if 'cmdarr.websocket' in line and 'Filtering logs for' in line:
                    continue
                
                # Skip logs that contain sensitive information (tokens, passwords, etc.)
                if any(sensitive in line.lower() for sensitive in ['token=', 'password=', 'key=', 'secret=']):
                    continue
                
                # Skip noisy cache performance messages (keep the actual track results)
                if any(cache_noise in line for cache_noise in [
                    'Cache hit: ',
                    'Cache miss, using live API search: ',
                    'Cache hit for music libraries',
                    'Cache miss for music libraries'
                ]):
                    continue
                
                # Filter by execution ID - this ensures logs are separated by execution
                if execution_pattern in line:
                    formatted_line = self._format_log_line(line)
                    filtered_lines.append(formatted_line)
        
        return filtered_lines
    
    def _get_base_logger_pattern(self, command_name: str) -> str:
        """Map command names to their base logger patterns"""
        # Handle dynamic playlist sync commands (e.g., playlist_sync_00001 -> playlist_sync_listenbrainz)
        if command_name.startswith('playlist_sync_'):
            return 'playlist_sync_listenbrainz'
        
        # Handle discovery commands
        elif command_name.startswith('discovery_'):
            if 'lastfm' in command_name:
                return 'discovery_lastfm'
            elif 'listenbrainz' in command_name:
                return 'discovery_listenbrainz'
            else:
                return 'discovery'
        
        # Handle library cache builder
        elif command_name == 'library_cache_builder':
            return 'library_cache_builder'
        
        # Handle playlist sync discovery maintenance
        elif command_name == 'playlist_sync_discovery_maintenance':
            return 'playlist_sync_discovery_maintenance'
        
        # Default fallback - use the command name as-is
        else:
            return command_name
    
    def _format_log_line(self, log_line: str) -> str:
        """Format a log line for display in the UI"""
        try:
            # Extract timestamp and message from log line
            # Format: "2025-01-21 13:18:23 - cmdarr.playlist_sync_listenbrainz.00002 - INFO - [EXEC:123] Starting command..."
            parts = log_line.split(' - ', 3)
            if len(parts) >= 4:
                timestamp = parts[0]
                logger_name = parts[1]
                level = parts[2]
                message = parts[3]
                
                # Remove execution ID from message for cleaner display
                if '[EXEC:' in message:
                    # Find and remove [EXEC:123] pattern
                    import re
                    message = re.sub(r'\[EXEC:\d+\]\s*', '', message)
                
                # For cleaner display, just show the timestamp and message
                # Skip the logger name and level to reduce noise
                return f"[{timestamp}] {message}"
            else:
                return log_line
        except Exception:
            return log_line
    
    async def _send_logs_to_subscribers(self, command_name: str, log_lines: List[str]):
        """Send log lines to all subscribers of a command"""
        if command_name not in self.command_connections:
            return
        
        message = json.dumps({
            "type": "log_update",
            "command_name": command_name,
            "logs": log_lines
        })
        
        disconnected = []
        for connection in self.command_connections[command_name]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send log update: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.command_connections[command_name].remove(connection)


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
                        logger.info(f"Client subscribed to {command_name} updates")
                
                elif message_type == "start_log_streaming":
                    command_name = message.get("command_name")
                    execution_id = message.get("execution_id")
                    if command_name and execution_id:
                        await manager.start_log_streaming(command_name, execution_id)
                        logger.info(f"Client started log streaming for {command_name}")
                
                elif message_type == "stop_log_streaming":
                    command_name = message.get("command_name")
                    if command_name:
                        await manager.stop_log_streaming(command_name)
                        logger.info(f"Client stopped log streaming for {command_name}")
                
                elif message_type == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}), 
                        websocket
                    )
                
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, client_id)
