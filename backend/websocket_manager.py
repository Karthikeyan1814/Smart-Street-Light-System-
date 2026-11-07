import logging
from typing import Any, Dict

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Simple WebSocket connection manager for broadcasting real-time events
    to all connected dashboard clients.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a JSON-serializable message to all connected clients.
        """
        stale_connections: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                stale_connections.append(connection)
            except Exception as exc:
                logger.exception("Failed to send WebSocket message: %s", exc)

        for conn in stale_connections:
            self.disconnect(conn)


ws_manager = WebSocketManager()

"""
WebSocket (Socket.IO) manager for real-time communication with the frontend.
"""

from typing import Any, Dict

from flask import Flask
from flask_socketio import SocketIO

# Global SocketIO instance used across the backend
# Using default threading async_mode to avoid extra dependencies.
socketio = SocketIO(cors_allowed_origins="*")


def init_socketio(app: Flask) -> SocketIO:
    """
    Initialize SocketIO with the given Flask app.

    Args:
        app: Flask application instance.

    Returns:
        Configured SocketIO instance.
    """
    socketio.init_app(app, cors_allowed_origins="*")
    return socketio


def broadcast_new_alert(alert_data: Dict[str, Any]) -> None:
    """
    Broadcast a newly received alert to all connected frontend clients.

    Args:
        alert_data: The complete alert/event payload to broadcast.
    """
    # Event name used on the frontend to subscribe to new alerts.
    socketio.emit("new_alert", alert_data, broadcast=True)


